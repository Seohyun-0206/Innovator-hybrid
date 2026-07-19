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


RAW_JSONL = "\n".join(
    [
        '{"question": "Q1", "choices": ["1", "2", "3", "4"], "answer": "A"}',
        '{"question": "Q2", "choices": ["1", "2", "3", "4"], "answer": "B"}',
        '{"question": "Q3", "choices": ["1", "2", "3", "4"], "answer": "C"}',
        '{"question": "Q4", "choices": ["1", "2", "3", "4"], "answer": "D"}',
        '{"question": "Q5", "choices": ["1", "2", "3", "4"], "answer": "A"}',
        '{"question": "Q6", "choices": ["1", "2", "3", "4"], "answer": "B"}',
    ]
)

ROUTING_PROMPT = "다음 질문을 보고 small 또는 large 중 하나만 답하세요.\n질문: {question}"


class RoutingFakeProvider:
    """라우터 호출(객관식 문제가 아닌 프롬프트)과 실제 채점 호출(객관식 문제 프롬프트)을
    프롬프트 내용으로 구분해서 서로 다른 응답을 돌려주는 테스트용 fake provider."""

    def __init__(self, router_outputs, answer_text="정답: A"):
        self.router_outputs = list(router_outputs)
        self.answer_text = answer_text
        self.answer_calls = []

    def chat(self, *, model, messages, options):
        prompt = messages[0]["content"]
        if "객관식 문제" in prompt:
            self.answer_calls.append(model)
            return LLMResponse(text=self.answer_text, raw={})
        return LLMResponse(text=self.router_outputs.pop(0), raw={})


def _make_dataset(**overrides):
    defaults = {"name": "routing-exec-ds", "raw_content": RAW_JSONL, "data_format": "jsonl"}
    defaults.update(overrides)
    return EvaluationDataset.objects.create(**defaults)


def _make_routing_result(run, dataset, small_model, large_model):
    result = EvaluationResult.objects.create(
        run=run,
        dataset=dataset,
        model=None,
        result_type="routing",
        candidate_label="Routing: Small/Large",
        status="pending",
    )
    EvaluationRoutingCandidate.objects.create(
        result=result,
        routing_prompt=ROUTING_PROMPT,
        small_model=small_model,
        large_model=large_model,
    )
    return result


@pytest.mark.django_db
def test_evaluate_routing_result_uses_exact_match_only(monkeypatch):
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="small-exec", display_name="Small Exec")
    large_model = LLMModel.objects.create(provider="vllm", name="large-exec", display_name="Large Exec")
    run = EvaluationRun.objects.create(name="routing-exec-run", dataset=dataset, config={"total_questions": 6})

    result = _make_routing_result(run, dataset, small_model, large_model)

    runner = PilotEvaluationRunner()
    snapshot = runner.build_dataset_snapshot(run=run, dataset=dataset, easy_ratio=None, seed=1, total_questions=6)
    questions = [EvaluationQuestion.from_payload(item) for item in snapshot.questions_payload]

    # exact "large"(대소문자 무시)만 large로 라우팅되고, 나머지(부연 설명·다른 언어·"small")는 small로 처리됩니다.
    router_outputs = ["small", "large", "  large  ", "the answer is large", "Small", "라지"]
    fake_provider = RoutingFakeProvider(router_outputs=router_outputs)
    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: fake_provider)

    runner.evaluate_routing_result(result, questions, run.config)

    result.refresh_from_db()
    item_results = list(result.item_results.order_by("item_index"))
    assert len(item_results) == 6

    expected_models = [small_model.id, large_model.id, large_model.id, small_model.id, small_model.id, small_model.id]
    assert [item.model_id for item in item_results] == expected_models
    assert [item.router_output for item in item_results] == ["small", "large", "large", "the answer is large", "Small", "라지"]

    assert result.routing_model_distribution == {
        "small": {"count": 4, "percent": 66.67},
        "large": {"count": 2, "percent": 33.33},
    }
    assert result.status == "completed"
    assert result.router_latency_p50_ms is not None
    assert result.router_latency_p95_ms is not None


@pytest.mark.django_db
def test_execute_dispatches_routing_and_single_model_results(monkeypatch):
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="small-disp", display_name="Small Disp")
    large_model = LLMModel.objects.create(provider="vllm", name="large-disp", display_name="Large Disp")
    single_model = LLMModel.objects.create(provider="vllm", name="single-disp", display_name="Single Disp")

    run = EvaluationRun.objects.create(name="dispatch-run", dataset=dataset, config={"total_questions": 6, "seed": 1})
    run.models.set([single_model])

    single_result = EvaluationResult.objects.create(
        run=run, dataset=dataset, model=single_model, result_type="single_model", status="pending"
    )
    routing_result = _make_routing_result(run, dataset, small_model, large_model)

    fake_provider = RoutingFakeProvider(router_outputs=["small", "large", "large", "small", "small", "small"])
    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: fake_provider)

    PilotEvaluationRunner().execute(run)

    single_result.refresh_from_db()
    routing_result.refresh_from_db()

    assert single_result.status == "completed"
    assert single_result.item_results.count() == 6

    assert routing_result.status == "completed"
    assert routing_result.item_results.count() == 6
    assert routing_result.routing_model_distribution["small"]["count"] == 4
    assert routing_result.routing_model_distribution["large"]["count"] == 2


@pytest.mark.django_db
def test_evaluate_routing_result_fails_gracefully_without_models(monkeypatch):
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="small-missing", display_name="Small Missing")
    run = EvaluationRun.objects.create(name="routing-missing-run", dataset=dataset, config={"total_questions": 6})

    result = EvaluationResult.objects.create(
        run=run, dataset=dataset, model=None, result_type="routing", candidate_label="Routing", status="pending"
    )
    EvaluationRoutingCandidate.objects.create(
        result=result, routing_prompt=ROUTING_PROMPT, small_model=small_model, large_model=None
    )

    runner = PilotEvaluationRunner()
    snapshot = runner.build_dataset_snapshot(run=run, dataset=dataset, easy_ratio=None, seed=1, total_questions=6)
    questions = [EvaluationQuestion.from_payload(item) for item in snapshot.questions_payload]

    runner.evaluate_routing_result(result, questions, run.config)

    result.refresh_from_db()
    assert result.status == "failed"
    assert "Small/Large 모델이 설정되지 않았습니다." in result.error_message
