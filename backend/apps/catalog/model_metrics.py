import csv
import json
import random
import re
import threading
import time
from dataclasses import dataclass, replace
from decimal import Decimal
from io import StringIO
from typing import Optional

import requests


ANSWER_PATTERN = re.compile(r"\b([ABCD])\b", re.IGNORECASE)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
KV_CACHE_POLL_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class EvaluationQuestion:
    question: str
    choices: list[str]
    answer: str
    category: str = ""
    subject: str = ""
    difficulty: str = ""

    def to_payload(self) -> dict:
        return {
            "question": self.question,
            "choices": self.choices,
            "answer": self.answer,
            "category": self.category,
            "subject": self.subject,
            "difficulty": self.difficulty,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "EvaluationQuestion":
        return cls(
            question=payload.get("question", ""),
            choices=payload.get("choices", []),
            answer=payload.get("answer", ""),
            category=payload.get("category", ""),
            subject=payload.get("subject", ""),
            difficulty=payload.get("difficulty", ""),
        )


class LatencyStats:
    """호출별 latency/TTFT/TPOT/Throughput 표본을 모으는 누산기.

    모델 단독 평가와 (앞으로 추가될) 라우팅 실험이 동일한 계산 기준을 공유하도록
    이 로직을 한 곳에 둡니다."""

    def __init__(self):
        self.latencies: list[int] = []
        self.ttfts: list[int] = []
        self.tpots: list[float] = []
        self.throughputs: list[float] = []

    def record(self, *, ok: bool, latency_ms: Optional[int], ttft_ms: Optional[int], output_tokens: int):
        if not ok or latency_ms is None:
            return
        self.latencies.append(latency_ms)
        if output_tokens > 0 and latency_ms > 0:
            self.throughputs.append(output_tokens / (latency_ms / 1000))
        if ttft_ms is not None:
            self.ttfts.append(ttft_ms)
            if output_tokens > 1:
                self.tpots.append((latency_ms - ttft_ms) / (output_tokens - 1))


@dataclass(frozen=True)
class ModelCallResult:
    output_text: str
    latency_ms: Optional[int]
    ttft_ms: Optional[int]
    input_tokens: int
    output_tokens: int
    error: str


def execute_model_call(
    provider,
    *,
    model_name: str,
    prompt: str,
    options: dict,
    prompt_tokens_estimate: int,
) -> ModelCallResult:
    """모델 하나에 프롬프트를 보내고 지연/TTFT/토큰 usage를 측정합니다."""
    started = time.perf_counter()
    try:
        response = provider.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options=options,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        output_text = response.text.strip()
        usage = getattr(response, "usage", None)
        if usage and usage.get("completion_tokens") is not None:
            # 실제 API/vLLM usage가 있으면 텍스트 길이 기반 추정치 대신 그 값을 사용합니다.
            output_tokens = usage["completion_tokens"]
            input_tokens = usage.get("prompt_tokens", prompt_tokens_estimate)
        else:
            output_tokens = estimate_tokens(output_text)
            input_tokens = prompt_tokens_estimate
        return ModelCallResult(
            output_text=output_text,
            latency_ms=latency_ms,
            ttft_ms=getattr(response, "ttft_ms", None),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error="",
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelCallResult(
            output_text="",
            latency_ms=latency_ms,
            ttft_ms=None,
            input_tokens=prompt_tokens_estimate,
            output_tokens=0,
            error=str(exc),
        )


def poll_kv_cache_usage(provider, stop_event: threading.Event, samples: list[float]):
    # vLLM `/metrics`의 KV 캐시 사용률은 요청 단위가 아니라 서버의 현재 상태이므로,
    # 평가가 진행되는 동안 별도 스레드에서 주기적으로 폴링해 샘플을 모읍니다.
    while True:
        try:
            usage = provider.fetch_kv_cache_usage()
        except Exception:
            usage = None
        if usage is not None:
            samples.append(usage)
        if stop_event.wait(KV_CACHE_POLL_INTERVAL_SECONDS):
            return


def start_kv_cache_poller(provider, samples: list[float]):
    """provider가 KV 캐시 조회를 지원하면 폴링 스레드를 시작해 (thread, stop_event)를 반환하고,
    아니면 (None, None)을 반환합니다. 호출자는 작업이 끝나면 stop_kv_cache_poller로 정리해야 합니다."""
    if not hasattr(provider, "fetch_kv_cache_usage"):
        return None, None
    stop_event = threading.Event()
    thread = threading.Thread(
        target=poll_kv_cache_usage,
        args=(provider, stop_event, samples),
        daemon=True,
    )
    thread.start()
    return thread, stop_event


def stop_kv_cache_poller(thread, stop_event, timeout: float = 5.0):
    if thread is None:
        return
    stop_event.set()
    thread.join(timeout=timeout)


def build_mcq_prompt(question: EvaluationQuestion, config: dict) -> str:
    choices = question.choices[:4]
    if len(choices) < 4:
        choices = choices + [""] * (4 - len(choices))
    return (
        "다음 객관식 문제의 정답을 A, B, C, D 중 하나로만 출력하세요.\n\n"
        f"문제: {question.question}\n"
        f"A. {choices[0]}\n"
        f"B. {choices[1]}\n"
        f"C. {choices[2]}\n"
        f"D. {choices[3]}\n\n"
        "정답:"
    )


def build_generation_prompt(question: EvaluationQuestion, config: dict) -> str:
    return question.question


def is_generation_correct(output_text: str, reference_answer: str) -> bool:
    """생성형 채점 v1: 참조 정답 텍스트가 모델 출력에 부분 문자열로 포함되는지만 확인합니다."""
    reference = reference_answer.strip().lower()
    if not reference:
        return False
    return reference in strip_thinking_output(output_text).lower()


def build_provider_options(provider: str, config: dict) -> dict:
    temperature = config.get("temperature", 0)
    max_tokens = int(config.get("max_tokens") or 8)
    if provider == "ollama":
        return {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    if provider == "gemini":
        return {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
    if provider in ("openrouter", "vllm"):
        return {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    if provider == "openai":
        # Responses API(/v1/responses)는 temperature·max_output_tokens를
        # 모델에 따라 지원하지 않는 경우가 있어 파라미터를 보내지 않습니다.
        return {}
    return {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }


def strip_thinking_output(text: str) -> str:
    """Qwen3 등 reasoning 모델이 실제 답 앞에 내보내는 <think>...</think> 블록을 제거합니다.
    MCQ 평가는 max_tokens를 8 정도로 짧게 잡는데, 그 예산을 <think> 추론이 다 써버리면
    닫는 태그 없이 응답이 끝나버립니다 — 그 경우 실제 답은 아직 나오지 않은 것이므로,
    추론 내용 속 글자를 답으로 잘못 인식하지 않도록 빈 문자열을 돌려줍니다."""
    cleaned = THINK_BLOCK_PATTERN.sub("", text)
    open_index = cleaned.lower().find("<think>")
    if open_index != -1:
        cleaned = cleaned[:open_index]
    return cleaned.strip()


def extract_answer(text: str) -> str:
    match = ANSWER_PATTERN.search(strip_thinking_output(text))
    return match.group(1).upper() if match else ""


def is_strict_answer(text: str) -> bool:
    return bool(re.fullmatch(r"\s*[ABCD]\s*", strip_thinking_output(text), re.IGNORECASE))


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def estimate_cost(model, input_tokens: int, output_tokens: int) -> Decimal:
    input_cost = Decimal(input_tokens) * model.input_token_price_per_1m / Decimal(1_000_000)
    output_cost = Decimal(output_tokens) * model.output_token_price_per_1m / Decimal(1_000_000)
    return (input_cost + output_cost).quantize(Decimal("0.000001"))


def ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))


def percentile(values: list, pct: int):
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * (pct / 100))
    return ordered[index]


def decimal_percentile(values: list, pct: int) -> Optional[Decimal]:
    value = percentile(values, pct)
    if value is None:
        return None
    return Decimal(str(round(value, 3)))


def load_questions(dataset, method_type: str = "multiple_choice") -> list[EvaluationQuestion]:
    """EvaluationDataset 하나를 파싱해서 문항 목록을 만듭니다."""
    raw_content = dataset.raw_content.strip()
    if not raw_content and dataset.source_url:
        response = requests.get(dataset.source_url, timeout=30)
        response.raise_for_status()
        raw_content = response.text.strip()
    if not raw_content:
        return []
    data_format = getattr(dataset, "data_format", "") or dataset.dataset_type
    if data_format == "csv":
        questions = parse_csv(raw_content, method_type)
    else:
        questions = parse_jsonl(raw_content, method_type) or parse_csv(raw_content, method_type)
    if questions and dataset.question_count != len(questions):
        dataset.question_count = len(questions)
        dataset.save(update_fields=["question_count", "updated_at"])
    return questions


def parse_jsonl(raw_content: str, method_type: str = "multiple_choice") -> list[EvaluationQuestion]:
    questions = []
    for line in raw_content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return []
        question = payload.get("question") or payload.get("prompt") or payload.get("input") or ""
        answer_raw = str(payload.get("answer") or payload.get("target") or payload.get("label") or "").strip()
        # 생성형은 정답이 문장 전체이므로 한 글자로 자르지 않고 원문을 그대로 보존합니다.
        answer = answer_raw if method_type == "generation" else answer_raw.upper()[:1]
        choices = payload.get("choices") or payload.get("options") or []
        if isinstance(choices, dict):
            choices = [choices.get(key, "") for key in ("A", "B", "C", "D")]
        if question and answer:
            questions.append(
                EvaluationQuestion(
                    question=question,
                    choices=[str(choice) for choice in choices],
                    answer=answer,
                    category=str(payload.get("category") or ""),
                    subject=str(payload.get("subject") or ""),
                    difficulty=str(payload.get("difficulty") or "").strip().lower(),
                )
            )
    return questions


def parse_csv(raw_content: str, method_type: str = "multiple_choice") -> list[EvaluationQuestion]:
    rows = list(csv.reader(StringIO(raw_content)))
    if not rows:
        return []
    header = [column.strip().lower() for column in rows[0]]
    if {"question", "answer"}.issubset(set(header)):
        return parse_header_csv(rows, header, method_type)
    return parse_mmlu_csv(rows)


def parse_header_csv(rows: list[list[str]], header: list[str], method_type: str = "multiple_choice") -> list[EvaluationQuestion]:
    questions = []
    for row in rows[1:]:
        data = {header[index]: value for index, value in enumerate(row) if index < len(header)}
        question = data.get("question", "")
        answer_raw = data.get("answer", "").strip()
        answer = answer_raw if method_type == "generation" else answer_raw.upper()[:1]
        choices = [data.get(key, "") for key in ("a", "b", "c", "d")]
        if question and answer:
            questions.append(
                EvaluationQuestion(
                    question=question,
                    choices=choices,
                    answer=answer,
                    category=data.get("category", ""),
                    subject=data.get("subject", ""),
                    difficulty=data.get("difficulty", "").strip().lower(),
                )
            )
    return questions


def parse_mmlu_csv(rows: list[list[str]]) -> list[EvaluationQuestion]:
    questions = []
    for row in rows:
        if len(row) < 6:
            continue
        questions.append(
            EvaluationQuestion(
                question=row[0],
                choices=row[1:5],
                answer=row[5].strip().upper()[:1],
            )
        )
    return questions


def select_questions_by_difficulty(
    questions: list[EvaluationQuestion],
    easy_ratio,
    total: int,
    seed,
) -> list[EvaluationQuestion]:
    """easy_ratio가 없으면(난이도 미지정 데이터셋/기존 방식) 기존과 완전히 동일하게
    동작합니다 — seed가 있을 때만 시드 셔플하고, 없으면 데이터셋 순서 그대로 앞에서
    total개만 자릅니다. easy_ratio가 있으면 Easy/Hard 비율에 맞춰 각 풀에서 뽑습니다."""
    if easy_ratio is None:
        shuffled = questions[:]
        if seed is not None:
            random.Random(int(seed)).shuffle(shuffled)
        return shuffled[:total]

    rng = random.Random(int(seed)) if seed is not None else random.Random()
    easy_pool = [question for question in questions if question.difficulty == "easy"]
    hard_pool = [question for question in questions if question.difficulty == "hard"]
    rng.shuffle(easy_pool)
    rng.shuffle(hard_pool)

    target_easy = round(total * (int(easy_ratio) / 100))
    target_hard = total - target_easy
    selected = easy_pool[:target_easy] + hard_pool[:target_hard]
    rng.shuffle(selected)
    return selected


def select_questions_from_pools(
    easy_questions: list[EvaluationQuestion],
    hard_questions: list[EvaluationQuestion],
    easy_ratio,
    total: int,
    seed,
) -> list[EvaluationQuestion]:
    """Easy 데이터셋 + Hard 데이터셋을 각각 통째로 선택하는 조합 모드 전용 선택 함수입니다.
    문항별 difficulty 태그와 무관하게 easy_questions 전체를 Easy 풀로, hard_questions
    전체를 Hard 풀로 취급하고 easy_ratio에 맞춰 뽑습니다."""
    rng = random.Random(int(seed)) if seed is not None else random.Random()
    ratio_value = 50 if easy_ratio is None else int(easy_ratio)
    easy_pool = [replace(question, difficulty="easy") for question in easy_questions]
    hard_pool = [replace(question, difficulty="hard") for question in hard_questions]
    rng.shuffle(easy_pool)
    rng.shuffle(hard_pool)

    target_easy = round(total * (ratio_value / 100))
    target_hard = total - target_easy
    selected = easy_pool[:target_easy] + hard_pool[:target_hard]
    rng.shuffle(selected)
    return selected
