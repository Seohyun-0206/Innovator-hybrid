import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.catalog import connectivity, views
from apps.catalog.connectivity import collect_run_models
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
    ]
)


def _make_dataset(**overrides):
    defaults = {"name": "exec-api-ds", "raw_content": RAW_JSONL, "data_format": "jsonl"}
    defaults.update(overrides)
    return EvaluationDataset.objects.create(**defaults)


def _make_client():
    User = get_user_model()
    staff_user = User.objects.create_user(username="exec-admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    return client


@pytest.mark.django_db
def test_collect_run_models_includes_routing_candidate_models_when_no_single_models():
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="collect-small", display_name="Collect Small")
    large_model = LLMModel.objects.create(provider="vllm", name="collect-large", display_name="Collect Large")
    run = EvaluationRun.objects.create(name="collect-run", dataset=dataset, config={})
    # run.models(단일 모델 M2M)는 비워둔 채 라우팅 후보만 연결합니다.
    result = EvaluationResult.objects.create(
        run=run, dataset=dataset, model=None, result_type="routing", candidate_label="Routing", status="pending"
    )
    EvaluationRoutingCandidate.objects.create(
        result=result, routing_prompt="{question}", small_model=small_model, large_model=large_model
    )

    models = collect_run_models(run)
    assert {model.id for model in models} == {small_model.id, large_model.id}


@pytest.mark.django_db
def test_execute_view_runs_routing_only_run_without_single_model_candidates(monkeypatch):
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="exec-small", display_name="Exec Small")
    large_model = LLMModel.objects.create(provider="vllm", name="exec-large", display_name="Exec Large")
    run = EvaluationRun.objects.create(name="exec-routing-run", dataset=dataset, config={"total_questions": 2, "seed": 1})
    result = EvaluationResult.objects.create(
        run=run, dataset=dataset, model=None, result_type="routing", candidate_label="Routing", status="pending"
    )
    EvaluationRoutingCandidate.objects.create(
        result=result,
        routing_prompt="small 또는 large 중 하나만 답하세요.\n질문: {question}",
        small_model=small_model,
        large_model=large_model,
    )
    from apps.catalog.evaluation import PilotEvaluationRunner

    PilotEvaluationRunner().build_dataset_snapshot(run=run, dataset=dataset, easy_ratio=None, seed=1, total_questions=2)

    # 실제 provider 가용성 네트워크 호출은 건너뛰고(이미 별도로 테스트됨), 실행 뷰가
    # 라우팅 전용 run을 "평가 대상 모델이 없습니다"로 잘못 거절하지 않는지만 확인합니다.
    monkeypatch.setattr(views, "validate_models_available", lambda models: (True, []))

    class FakeProvider:
        def chat(self, *, model, messages, options):
            prompt = messages[0]["content"]
            if "객관식 문제" in prompt:
                return LLMResponse(text="정답: A", raw={})
            return LLMResponse(text="small", raw={})

    fake = FakeProvider()
    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: fake)

    client = _make_client()
    response = client.post(f"/api/evaluation-runs/{run.id}/execute/")

    assert response.status_code == 200, response.data
    assert response.data["status"] == "completed"


@pytest.mark.django_db
def test_model_availability_view_uses_routing_candidate_models_for_run_id(monkeypatch):
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="avail-small", display_name="Avail Small", is_active=True)
    large_model = LLMModel.objects.create(provider="vllm", name="avail-large", display_name="Avail Large", is_active=True)
    run = EvaluationRun.objects.create(name="avail-routing-run", dataset=dataset, config={})
    result = EvaluationResult.objects.create(
        run=run, dataset=dataset, model=None, result_type="routing", candidate_label="Routing", status="pending"
    )
    EvaluationRoutingCandidate.objects.create(
        result=result, routing_prompt="{question}", small_model=small_model, large_model=large_model
    )

    def fake_check_models_connectivity(models):
        return [
            {
                "model_id": model.id,
                "provider": model.provider,
                "model": model.name,
                "display_name": model.display_name,
                "status": "online",
                "latency_ms": 5,
                "checked_at": "2026-01-01T00:00:00Z",
                "message": "ok",
            }
            for model in models
        ]

    monkeypatch.setattr(views, "check_models_connectivity", fake_check_models_connectivity)

    client = _make_client()
    response = client.get(f"/api/evaluation-runs/model-availability/?run_id={run.id}")

    assert response.status_code == 200, response.data
    assert response.data["ready"] is True
    assert {item["model_id"] for item in response.data["models"]} == {small_model.id, large_model.id}
