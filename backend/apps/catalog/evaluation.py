import csv
import json
import random
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO

import requests
from django.utils import timezone

from apps.catalog.models import EvaluationItemResult, EvaluationRun
from apps.providers.registry import ProviderRegistry


ANSWER_PATTERN = re.compile(r"\b([ABCD])\b", re.IGNORECASE)


@dataclass(frozen=True)
class EvaluationQuestion:
    question: str
    choices: list[str]
    answer: str
    category: str = ""
    subject: str = ""


class PilotEvaluationRunner:
    def __init__(self):
        self.provider_registry = ProviderRegistry()

    def execute(self, run: EvaluationRun) -> EvaluationRun:
        run.status = "running"
        run.started_at = timezone.now()
        run.completed_at = None
        run.save(update_fields=["status", "started_at", "completed_at", "updated_at"])

        try:
            questions = self.load_questions(run)
            if not questions:
                raise ValueError("평가할 문항을 찾을 수 없습니다. raw_content 또는 접근 가능한 source_url을 확인하세요.")
            max_questions = int(run.config.get("total_questions") or run.config.get("max_questions") or 20)
            max_questions = max(1, min(max_questions, 500))
            seed = run.config.get("seed")
            if seed is not None:
                questions = questions[:]
                random.Random(int(seed)).shuffle(questions)
            questions = questions[:max_questions]

            for result in run.results.select_related("model"):
                self.evaluate_model_result(result, questions, run.config)

            run.status = "completed"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
        except Exception as exc:
            run.status = "failed"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
            run.results.update(status="failed", error_message=str(exc))
            raise
        return run

    def load_questions(self, run: EvaluationRun) -> list[EvaluationQuestion]:
        raw_content = run.dataset.raw_content.strip()
        if not raw_content and run.dataset.source_url:
            response = requests.get(run.dataset.source_url, timeout=30)
            response.raise_for_status()
            raw_content = response.text.strip()
        if not raw_content:
            return []
        data_format = getattr(run.dataset, "data_format", "") or run.dataset.dataset_type
        if data_format == "csv":
            questions = self.parse_csv(raw_content)
        else:
            questions = self.parse_jsonl(raw_content) or self.parse_csv(raw_content)
        if questions and run.dataset.question_count != len(questions):
            run.dataset.question_count = len(questions)
            run.dataset.save(update_fields=["question_count", "updated_at"])
        return questions

    def parse_jsonl(self, raw_content: str) -> list[EvaluationQuestion]:
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
            answer = str(payload.get("answer") or payload.get("target") or payload.get("label") or "").strip().upper()
            choices = payload.get("choices") or payload.get("options") or []
            if isinstance(choices, dict):
                choices = [choices.get(key, "") for key in ("A", "B", "C", "D")]
            if question and answer:
                questions.append(
                    EvaluationQuestion(
                        question=question,
                        choices=[str(choice) for choice in choices],
                        answer=answer[:1],
                        category=str(payload.get("category") or ""),
                        subject=str(payload.get("subject") or ""),
                    )
                )
        return questions

    def parse_csv(self, raw_content: str) -> list[EvaluationQuestion]:
        rows = list(csv.reader(StringIO(raw_content)))
        if not rows:
            return []
        header = [column.strip().lower() for column in rows[0]]
        if {"question", "answer"}.issubset(set(header)):
            return self.parse_header_csv(rows, header)
        return self.parse_mmlu_csv(rows)

    def parse_header_csv(self, rows: list[list[str]], header: list[str]) -> list[EvaluationQuestion]:
        questions = []
        for row in rows[1:]:
            data = {header[index]: value for index, value in enumerate(row) if index < len(header)}
            question = data.get("question", "")
            answer = data.get("answer", "").strip().upper()
            choices = [data.get(key, "") for key in ("a", "b", "c", "d")]
            if question and answer:
                questions.append(
                    EvaluationQuestion(
                        question=question,
                        choices=choices,
                        answer=answer[:1],
                        category=data.get("category", ""),
                        subject=data.get("subject", ""),
                    )
                )
        return questions

    def parse_mmlu_csv(self, rows: list[list[str]]) -> list[EvaluationQuestion]:
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

    def evaluate_model_result(self, result, questions: list[EvaluationQuestion], config: dict):
        model = result.model
        result.status = "running"
        result.error_message = ""
        result.save(update_fields=["status", "error_message", "updated_at"])

        try:
            provider = self.provider_registry.get(model.provider, credential=model.provider_credential)
        except Exception as exc:
            result.status = "failed"
            result.failure_rate = Decimal("1.0000")
            result.error_message = str(exc)
            result.save()
            return

        latencies = []
        correct = 0
        strict_ok = 0
        failures = 0
        parse_failures = 0
        input_tokens = 0
        output_tokens = 0
        category_stats = {}
        subject_stats = {}

        result.item_results.all().delete()
        max_retries = max(0, int(config.get("retry") or config.get("max_retries") or 0))

        for item_index, question in enumerate(questions, start=1):
            prompt = self.build_prompt(question, config)
            prompt_tokens = self.estimate_tokens(prompt)
            final_record = None

            for attempt in range(1, max_retries + 2):
                started = time.perf_counter()
                output_text = ""
                output_token_count = 0
                latency_ms = None
                extracted = ""
                strict_answer = False
                is_correct = False
                ok = False
                error = ""

                try:
                    response = provider.chat(
                        model=model.name,
                        messages=[{"role": "user", "content": prompt}],
                        options=self.build_provider_options(model.provider, config),
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    output_text = response.text.strip()
                    output_token_count = self.estimate_tokens(output_text)
                    extracted = self.extract_answer(output_text)
                    strict_answer = self.is_strict_answer(output_text)
                    is_correct = extracted == question.answer
                    ok = bool(extracted)
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    error = str(exc)
                    result.error_message = error

                final_record = EvaluationItemResult.objects.create(
                    result=result,
                    run=result.run,
                    dataset=result.dataset,
                    model=model,
                    item_index=item_index,
                    question=question.question,
                    choices=question.choices,
                    gold=question.answer,
                    predicted_choice=extracted,
                    strict_ok=strict_answer,
                    is_correct=is_correct,
                    ok=ok,
                    attempt=attempt,
                    error=error,
                    input_tokens=prompt_tokens,
                    output_tokens=output_token_count,
                    latency_ms=latency_ms,
                    raw_output=output_text,
                    subject=question.subject,
                    category=question.category,
                )
                if ok or attempt > max_retries:
                    break

            input_tokens += prompt_tokens
            if final_record is None:
                continue
            output_tokens += final_record.output_tokens
            if final_record.latency_ms is not None and final_record.ok:
                latencies.append(final_record.latency_ms)
            if not final_record.ok:
                if final_record.error:
                    failures += 1
                else:
                    parse_failures += 1
            if final_record.ok and not final_record.predicted_choice:
                parse_failures += 1
            if final_record.strict_ok:
                strict_ok += 1
            if final_record.is_correct:
                correct += 1
            self.add_group_stat(category_stats, question.category, final_record.is_correct)
            self.add_group_stat(subject_stats, question.subject, final_record.is_correct)

        total = len(questions)
        result.status = "completed" if failures < total else "failed"
        result.overall_accuracy = self.ratio(correct, total)
        result.strict_compliance_rate = self.ratio(strict_ok, total)
        result.failure_rate = self.ratio(failures, total)
        result.parse_failure_rate = self.ratio(parse_failures, total)
        result.latency_p50_ms = self.percentile(latencies, 50)
        result.latency_p95_ms = self.percentile(latencies, 95)
        result.input_tokens = input_tokens
        result.output_tokens = output_tokens
        result.estimated_cost_usd = self.estimate_cost(model, input_tokens, output_tokens)
        result.category_accuracy = self.serialize_group_stats(category_stats)
        result.subject_accuracy = self.serialize_group_stats(subject_stats)
        result.scorecard = self.build_scorecard(
            result=result,
            total=total,
            correct=correct,
            failures=failures,
            parse_failures=parse_failures,
            strict_ok=strict_ok,
        )
        result.save()

    def build_prompt(self, question: EvaluationQuestion, config: dict) -> str:
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

    def build_provider_options(self, provider: str, config: dict) -> dict:
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
        if provider == "openrouter":
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

    def extract_answer(self, text: str) -> str:
        match = ANSWER_PATTERN.search(text.strip())
        return match.group(1).upper() if match else ""

    def is_strict_answer(self, text: str) -> bool:
        return bool(re.fullmatch(r"\s*[ABCD]\s*", text.strip(), re.IGNORECASE))

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text.split()))

    def estimate_cost(self, model, input_tokens: int, output_tokens: int) -> Decimal:
        input_cost = Decimal(input_tokens) * model.input_token_price_per_1m / Decimal(1_000_000)
        output_cost = Decimal(output_tokens) * model.output_token_price_per_1m / Decimal(1_000_000)
        return (input_cost + output_cost).quantize(Decimal("0.000001"))

    def ratio(self, numerator: int, denominator: int) -> Decimal:
        if denominator == 0:
            return Decimal("0.0000")
        return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))

    def percentile(self, values: list[int], percentile: int) -> int | None:
        if not values:
            return None
        ordered = sorted(values)
        index = round((len(ordered) - 1) * (percentile / 100))
        return ordered[index]

    def add_group_stat(self, stats: dict, key: str, is_correct: bool):
        if not key:
            return
        if key not in stats:
            stats[key] = {"correct": 0, "total": 0}
        stats[key]["total"] += 1
        if is_correct:
            stats[key]["correct"] += 1

    def serialize_group_stats(self, stats: dict) -> dict:
        return {
            key: {
                **value,
                "accuracy": float(self.ratio(value["correct"], value["total"])),
            }
            for key, value in stats.items()
        }

    def build_scorecard(self, *, result, total: int, correct: int, failures: int, parse_failures: int, strict_ok: int) -> dict:
        accuracy = float(self.ratio(correct, total))
        strict_rate = float(self.ratio(strict_ok, total))
        failure_rate = float(self.ratio(failures, total))
        parse_failure_rate = float(self.ratio(parse_failures, total))
        reliability = max(0.0, 1.0 - failure_rate - parse_failure_rate)
        p95 = result.latency_p95_ms or result.model.average_latency_ms or 0
        cost = float(result.estimated_cost_usd or 0)
        tokens = max(1, result.input_tokens + result.output_tokens)

        performance_score = round((accuracy * 80.0) + (strict_rate * 20.0), 2)
        latency_score = max(0.0, 100.0 - min(p95 / 30.0, 100.0)) if p95 else 60.0
        token_score = min(100.0, (correct / tokens) * 10000.0)
        cost_score = max(0.0, 100.0 - min(cost * 5000.0, 100.0))
        efficiency_score = round((latency_score * 0.45) + (token_score * 0.25) + (cost_score * 0.30), 2)
        capability_score = round((reliability * 70.0) + (min(result.model.quality_level, 5) / 5.0 * 30.0), 2)
        total_score = round((performance_score * 0.55) + (efficiency_score * 0.25) + (capability_score * 0.20), 2)
        recommended_role = self.recommend_role(accuracy, p95, failure_rate, total_score)

        return {
            "evaluated_questions": total,
            "correct": correct,
            "failures": failures,
            "parse_failures": parse_failures,
            "performance_score": performance_score,
            "efficiency_score": efficiency_score,
            "capability_score": capability_score,
            "total_score": total_score,
            "reliability_score": round(reliability * 100.0, 2),
            "recommended_role": recommended_role,
            "role_reason": self.role_reason(recommended_role),
            "mode": "pilot_sync_item_logs",
        }

    def recommend_role(self, accuracy: float, p95: int, failure_rate: float, total_score: float) -> str:
        if failure_rate > 0.25:
            return "Escalation Candidate"
        if accuracy >= 0.8 and total_score >= 70:
            return "Accurate Path"
        if p95 and p95 <= 3000 and accuracy >= 0.55:
            return "Fast Path"
        return "Escalation Candidate"

    def role_reason(self, role: str) -> str:
        if role == "Accurate Path":
            return "정확도와 종합 점수가 높아 품질 우선 경로 후보입니다."
        if role == "Fast Path":
            return "지연시간이 낮고 기본 정확도를 만족해 빠른 경로 후보입니다."
        return "실패율, 정확도 또는 지연 조건을 보완한 뒤 정책에 편입하는 것이 안전합니다."
