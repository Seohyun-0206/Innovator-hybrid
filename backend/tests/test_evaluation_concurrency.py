import re
import time

import pytest

from apps.catalog.evaluation import PilotEvaluationRunner
from apps.catalog.model_metrics import EvaluationQuestion
from apps.catalog.models import (
    EvaluationDataset,
    EvaluationResult,
    EvaluationRoutingCandidate,
    EvaluationRun,
    LLMModel,
)
from apps.providers.base import LLMResponse
from apps.providers.registry import ProviderRegistry


QUESTION_NUMBER_PATTERN = re.compile(r"Q(\d+)")


def _question_number(prompt: str) -> int:
    match = QUESTION_NUMBER_PATTERN.search(prompt)
    return int(match.group(1)) if match else 0


class DeterministicFakeProvider:
    """호출 순서나 스레드에 의존하지 않고, 프롬프트 속 문항 번호만 보고 결정적으로
    응답을 계산하는 fake provider — concurrency>1에서도 안전하게 동시 호출 가능합니다.
    (기존 RoutingFakeProvider의 list.pop(0) 방식은 호출 순서에 의존해 동시 실행에서 안전하지 않습니다.)"""

    def __init__(self, delay_by_question: dict | None = None):
        self.delay_by_question = delay_by_question or {}

    def chat(self, *, model, messages, options):
        prompt = messages[0]["content"]
        qnum = _question_number(prompt)
        delay = self.delay_by_question.get(qnum, 0)
        if delay:
            time.sleep(delay)
        letter = "A" if qnum % 2 == 0 else "B"
        return LLMResponse(text=f"정답: {letter}", raw={})


class DeterministicRoutingFakeProvider:
    """라우팅 실험용 — 라우터 프롬프트와 채점 프롬프트(객관식 문제)를 구분하고,
    둘 다 문항 번호만으로 결정적으로 응답합니다."""

    def __init__(self, delay_by_question: dict | None = None):
        self.delay_by_question = delay_by_question or {}

    def chat(self, *, model, messages, options):
        prompt = messages[0]["content"]
        qnum = _question_number(prompt)
        delay = self.delay_by_question.get(qnum, 0)
        if delay:
            time.sleep(delay)
        if "객관식 문제" in prompt:
            letter = "A" if qnum % 2 == 0 else "B"
            return LLMResponse(text=f"정답: {letter}", raw={})
        return LLMResponse(text="large" if qnum % 2 == 0 else "small", raw={})


def _make_questions(count: int) -> list[EvaluationQuestion]:
    # 짝수 문항은 fake provider가 "A"를 답하도록 되어 있고, 홀수는 "B" — 문항 1~4는
    # gold를 fake의 답과 맞춰 정답으로, 5~6은 일부러 틀리게 만들어 정확도가 100%가
    # 아니게(0.6667) 해서 정확도 계산 자체가 제대로 되는지도 함께 확인합니다.
    questions = []
    for n in range(1, count + 1):
        matching_answer = "A" if n % 2 == 0 else "B"
        answer = matching_answer if n <= 4 else "Z"
        questions.append(
            EvaluationQuestion(
                question=f"Q{n} 무슨 문제인가요",
                choices=["1", "2", "3", "4"],
                answer=answer,
                subject="s",
                category="c",
            )
        )
    return questions


def _make_dataset(**overrides):
    defaults = {"name": "concurrency-ds", "raw_content": "", "data_format": "jsonl"}
    defaults.update(overrides)
    return EvaluationDataset.objects.create(**defaults)


@pytest.mark.django_db
def test_concurrency_produces_same_aggregate_results_for_single_model(monkeypatch):
    dataset = _make_dataset()
    model = LLMModel.objects.create(provider="vllm", name="concurrency-model", display_name="Concurrency Model")
    questions = _make_questions(6)
    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: DeterministicFakeProvider())
    runner = PilotEvaluationRunner()

    run_seq = EvaluationRun.objects.create(name="concurrency-seq-run", dataset=dataset, config={})
    result_seq = EvaluationResult.objects.create(run=run_seq, dataset=dataset, model=model, result_type="single_model", status="pending")
    runner.evaluate_model_result(result_seq, questions, {})
    result_seq.refresh_from_db()

    run_par = EvaluationRun.objects.create(name="concurrency-par-run", dataset=dataset, config={"concurrency": 4})
    result_par = EvaluationResult.objects.create(run=run_par, dataset=dataset, model=model, result_type="single_model", status="pending")
    runner.evaluate_model_result(result_par, questions, {"concurrency": 4})
    result_par.refresh_from_db()

    assert float(result_seq.overall_accuracy) == pytest.approx(2 / 3, abs=0.0001)
    assert result_par.overall_accuracy == result_seq.overall_accuracy
    assert result_par.strict_compliance_rate == result_seq.strict_compliance_rate
    assert result_par.failure_rate == result_seq.failure_rate
    assert result_par.category_accuracy == result_seq.category_accuracy
    assert result_par.subject_accuracy == result_seq.subject_accuracy
    assert result_par.item_results.count() == result_seq.item_results.count() == 6


@pytest.mark.django_db
def test_concurrency_produces_same_aggregate_results_for_routing(monkeypatch):
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="concurrency-small", display_name="Concurrency Small")
    large_model = LLMModel.objects.create(provider="vllm", name="concurrency-large", display_name="Concurrency Large")
    questions = _make_questions(6)
    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: DeterministicRoutingFakeProvider())
    runner = PilotEvaluationRunner()

    def make_routing_result(run):
        result = EvaluationResult.objects.create(
            run=run, dataset=dataset, model=None, result_type="routing", candidate_label="Routing: Small/Large", status="pending"
        )
        EvaluationRoutingCandidate.objects.create(
            result=result,
            routing_prompt="다음 질문을 보고 small 또는 large 중 하나만 답하세요.\n질문: {question}",
            small_model=small_model,
            large_model=large_model,
        )
        return result

    run_seq = EvaluationRun.objects.create(name="concurrency-routing-seq-run", dataset=dataset, config={})
    result_seq = make_routing_result(run_seq)
    runner.evaluate_routing_result(result_seq, questions, {})
    result_seq.refresh_from_db()

    run_par = EvaluationRun.objects.create(name="concurrency-routing-par-run", dataset=dataset, config={"concurrency": 4})
    result_par = make_routing_result(run_par)
    runner.evaluate_routing_result(result_par, questions, {"concurrency": 4})
    result_par.refresh_from_db()

    assert result_par.overall_accuracy == result_seq.overall_accuracy
    assert result_par.routing_model_distribution == result_seq.routing_model_distribution
    assert result_seq.routing_model_distribution == {
        "small": {"count": 3, "percent": 50.0},
        "large": {"count": 3, "percent": 50.0},
    }
    assert result_par.item_results.count() == result_seq.item_results.count() == 6


@pytest.mark.django_db
def test_item_index_complete_and_unique_under_out_of_order_completion(monkeypatch):
    dataset = _make_dataset()
    model = LLMModel.objects.create(provider="vllm", name="reorder-model", display_name="Reorder Model")
    questions = _make_questions(6)
    # 문항 번호가 클수록 지연이 짧아서, 나중 문항이 먼저 끝나도록 일부러 순서를 뒤집습니다.
    delay_by_question = {1: 0.05, 2: 0.04, 3: 0.03, 4: 0.02, 5: 0.01, 6: 0.0}
    fake_provider = DeterministicFakeProvider(delay_by_question=delay_by_question)
    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: fake_provider)
    runner = PilotEvaluationRunner()

    run = EvaluationRun.objects.create(name="reorder-run", dataset=dataset, config={"concurrency": 6})
    result = EvaluationResult.objects.create(run=run, dataset=dataset, model=model, result_type="single_model", status="pending")
    runner.evaluate_model_result(result, questions, {"concurrency": 6})
    result.refresh_from_db()

    item_indexes = sorted(item.item_index for item in result.item_results.all())
    assert item_indexes == [1, 2, 3, 4, 5, 6]
    assert len(item_indexes) == len(set(item_indexes))


def test_concurrency_clamped_to_at_least_one():
    runner = PilotEvaluationRunner()
    assert runner._resolve_concurrency({"concurrency": 0}) == 1
    assert runner._resolve_concurrency({"concurrency": -5}) == 1
    assert runner._resolve_concurrency({"concurrency": "not-a-number"}) == 1
    assert runner._resolve_concurrency({"concurrency": None}) == 1
    assert runner._resolve_concurrency({}) == 1


def test_concurrency_clamped_to_max():
    runner = PilotEvaluationRunner()
    assert runner._resolve_concurrency({"concurrency": 999}) == PilotEvaluationRunner.MAX_CONCURRENCY
    assert runner._resolve_concurrency({"concurrency": PilotEvaluationRunner.MAX_CONCURRENCY}) == PilotEvaluationRunner.MAX_CONCURRENCY
