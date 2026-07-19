import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.catalog.evaluation import PilotEvaluationRunner
from apps.catalog.model_metrics import load_questions, select_questions_by_difficulty, select_questions_from_pools
from apps.catalog.models import (
    EvaluationDataset,
    EvaluationDatasetSnapshot,
    EvaluationResult,
    EvaluationRoutingCandidate,
    EvaluationRun,
    LLMModel,
)
from apps.catalog.serializers import EvaluationRunSerializer
from apps.providers.base import LLMResponse
from apps.providers.registry import ProviderRegistry


RAW_JSONL_WITH_DIFFICULTY = "\n".join(
    [
        '{"question": "Q1", "choices": ["1", "2", "3", "4"], "answer": "A", "difficulty": "easy"}',
        '{"question": "Q2", "choices": ["1", "2", "3", "4"], "answer": "B", "difficulty": "easy"}',
        '{"question": "Q3", "choices": ["1", "2", "3", "4"], "answer": "C", "difficulty": "easy"}',
        '{"question": "Q4", "choices": ["1", "2", "3", "4"], "answer": "D", "difficulty": "hard"}',
        '{"question": "Q5", "choices": ["1", "2", "3", "4"], "answer": "A", "difficulty": "hard"}',
        '{"question": "Q6", "choices": ["1", "2", "3", "4"], "answer": "B", "difficulty": "hard"}',
    ]
)


def _make_dataset(**overrides):
    defaults = {"name": "snapshot-ds", "raw_content": RAW_JSONL_WITH_DIFFICULTY, "data_format": "jsonl"}
    defaults.update(overrides)
    return EvaluationDataset.objects.create(**defaults)


RAW_EASY_JSONL = "\n".join(
    [
        '{"question": "E1", "choices": ["1", "2", "3", "4"], "answer": "A"}',
        '{"question": "E2", "choices": ["1", "2", "3", "4"], "answer": "B"}',
        '{"question": "E3", "choices": ["1", "2", "3", "4"], "answer": "C"}',
    ]
)
RAW_HARD_JSONL = "\n".join(
    [
        '{"question": "H1", "choices": ["1", "2", "3", "4"], "answer": "D"}',
        '{"question": "H2", "choices": ["1", "2", "3", "4"], "answer": "A"}',
        '{"question": "H3", "choices": ["1", "2", "3", "4"], "answer": "B"}',
    ]
)


@pytest.mark.django_db
def test_select_questions_by_difficulty_respects_ratio_and_is_deterministic():
    dataset = _make_dataset()
    questions = load_questions(dataset)

    selected_first = select_questions_by_difficulty(questions, easy_ratio=67, total=3, seed=42)
    selected_second = select_questions_by_difficulty(questions, easy_ratio=67, total=3, seed=42)

    easy_count = sum(1 for q in selected_first if q.difficulty == "easy")
    hard_count = sum(1 for q in selected_first if q.difficulty == "hard")
    assert len(selected_first) == 3
    assert easy_count == 2
    assert hard_count == 1
    # 같은 seed면 항상 같은 결과 (재현성)
    assert [q.question for q in selected_first] == [q.question for q in selected_second]


@pytest.mark.django_db
def test_select_questions_by_difficulty_none_matches_legacy_behavior_without_seed():
    dataset = _make_dataset()
    questions = load_questions(dataset)

    # easy_ratio=None + seed=None 이면 셔플 없이 데이터셋 순서 그대로 앞에서 N개 (기존 동작과 동일)
    selected = select_questions_by_difficulty(questions, easy_ratio=None, total=2, seed=None)
    assert [q.question for q in selected] == ["Q1", "Q2"]


@pytest.mark.django_db
def test_preview_snapshot_counts_matches_actual_snapshot_creation():
    runner = PilotEvaluationRunner()
    dataset = _make_dataset()

    preview = runner.preview_snapshot_counts(dataset=dataset, easy_ratio=67, seed=42, total_questions=3)
    assert preview == {"total_questions": 3, "easy_count": 2, "hard_count": 1}

    run = EvaluationRun.objects.create(name="snapshot-run", dataset=dataset, config={})
    snapshot = runner.build_dataset_snapshot(
        run=run, dataset=dataset, easy_ratio=67, seed=42, total_questions=3
    )
    saved_easy = sum(1 for item in snapshot.questions_payload if item["difficulty"] == "easy")
    saved_hard = sum(1 for item in snapshot.questions_payload if item["difficulty"] == "hard")
    assert preview["total_questions"] == len(snapshot.questions_payload)
    assert preview["easy_count"] == saved_easy
    assert preview["hard_count"] == saved_hard


@pytest.mark.django_db
def test_execute_uses_snapshot_even_if_dataset_changes_afterwards(monkeypatch):
    dataset = _make_dataset()
    model = LLMModel.objects.create(provider="vllm", name="snap-model", display_name="Snap Model")
    run = EvaluationRun.objects.create(name="reproducible-run", dataset=dataset, config={"total_questions": 6})
    run.models.set([model])

    result = EvaluationResult.objects.create(run=run, dataset=dataset, model=model, status="pending")

    runner = PilotEvaluationRunner()
    runner.build_dataset_snapshot(
        run=run, dataset=dataset, easy_ratio=None, seed=1, total_questions=6
    )

    # 스냅샷을 만든 뒤 원본 데이터셋 내용을 완전히 바꿔치기합니다.
    dataset.raw_content = '{"question": "changed", "choices": ["1","2","3","4"], "answer": "A"}'
    dataset.save(update_fields=["raw_content"])

    class FakeProvider:
        def chat(self, *, model, messages, options):
            return LLMResponse(text="정답: A", raw={})

    monkeypatch.setattr(ProviderRegistry, "get", lambda self, provider_name, credential=None: FakeProvider())
    runner.execute(run)

    result.refresh_from_db()
    questions_in_log = list(result.item_results.values_list("question", flat=True))
    # 원본이 "changed" 하나로 바뀌었어도, 스냅샷에 저장된 원래 6문항 그대로 채점됨
    assert "changed" not in questions_in_log
    assert len(questions_in_log) == 6


@pytest.mark.django_db
def test_evaluation_run_serializer_creates_snapshot_with_ratio():
    dataset = _make_dataset()
    model = LLMModel.objects.create(provider="vllm", name="ser-model", display_name="Ser Model")

    serializer = EvaluationRunSerializer(
        data={
            "name": "svc-run",
            "dataset": dataset.id,
            "easy_ratio": 67,
            "model_ids": [model.id],
            "config": {"seed": 42, "total_questions": 3},
            "notes": "",
        }
    )
    assert serializer.is_valid(), serializer.errors
    run = serializer.save()

    snapshot = EvaluationDatasetSnapshot.objects.get(run=run)
    assert snapshot.easy_ratio == 67
    assert snapshot.total_questions == 3


@pytest.mark.django_db
def test_evaluation_run_serializer_without_ratio_still_creates_snapshot():
    dataset = _make_dataset()
    model = LLMModel.objects.create(provider="vllm", name="plain-model", display_name="Plain Model")

    serializer = EvaluationRunSerializer(
        data={
            "name": "plain-run",
            "dataset": dataset.id,
            "model_ids": [model.id],
            "config": {"total_questions": 4},
            "notes": "",
        }
    )
    assert serializer.is_valid(), serializer.errors
    run = serializer.save()

    snapshot = EvaluationDatasetSnapshot.objects.get(run=run)
    assert snapshot.easy_ratio is None
    assert snapshot.total_questions == 4


@pytest.mark.django_db
def test_snapshot_preview_api_returns_counts():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    dataset = _make_dataset()
    staff_user = User.objects.create_user(username="preview-admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get(
        "/api/evaluation-datasets/snapshot-preview/",
        {"dataset": dataset.id, "easy_ratio": 67, "seed": 42, "total_questions": 3},
    )

    assert response.status_code == 200
    assert response.data == {"total_questions": 3, "easy_count": 2, "hard_count": 1}


@pytest.mark.django_db
def test_evaluation_run_serializer_creates_routing_candidate():
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="small-model", display_name="Small Model")
    large_model = LLMModel.objects.create(provider="vllm", name="large-model", display_name="Large Model")

    serializer = EvaluationRunSerializer(
        data={
            "name": "routing-run",
            "dataset": dataset.id,
            "routing_candidates": [
                {
                    "routing_prompt": "다음 질문을 보고 small 또는 large 중 하나만 답하세요.\n질문: {question}",
                    "small_model": small_model.id,
                    "large_model": large_model.id,
                }
            ],
            "config": {"total_questions": 4},
            "notes": "",
        }
    )
    assert serializer.is_valid(), serializer.errors
    run = serializer.save()

    result = EvaluationResult.objects.get(run=run)
    assert result.result_type == "routing"
    assert result.model_id is None
    assert result.candidate_label == "Routing: Small Model / Large Model"

    routing_config = EvaluationRoutingCandidate.objects.get(result=result)
    assert routing_config.small_model_id == small_model.id
    assert routing_config.large_model_id == large_model.id


@pytest.mark.django_db
def test_evaluation_run_serializer_requires_at_least_one_candidate():
    dataset = _make_dataset()

    serializer = EvaluationRunSerializer(
        data={
            "name": "empty-run",
            "dataset": dataset.id,
            "config": {},
            "notes": "",
        }
    )
    assert not serializer.is_valid()
    assert "단일 모델 후보 또는 라우팅 후보를 1개 이상 지정해야 합니다." in str(serializer.errors)


@pytest.mark.django_db
def test_evaluation_run_serializer_allows_routing_only_without_single_model():
    dataset = _make_dataset()
    small_model = LLMModel.objects.create(provider="vllm", name="only-small", display_name="Only Small")
    large_model = LLMModel.objects.create(provider="vllm", name="only-large", display_name="Only Large")

    serializer = EvaluationRunSerializer(
        data={
            "name": "routing-only-run",
            "dataset": dataset.id,
            "routing_candidates": [
                {
                    "display_name": "커스텀 라우팅",
                    "routing_prompt": "small 또는 large만 답하세요: {question}",
                    "small_model": small_model.id,
                    "large_model": large_model.id,
                }
            ],
            "config": {},
            "notes": "",
        }
    )
    assert serializer.is_valid(), serializer.errors
    run = serializer.save()

    assert run.results.count() == 1
    result = run.results.get()
    assert result.candidate_label == "커스텀 라우팅"


@pytest.mark.django_db
def test_select_questions_from_pools_respects_ratio_and_is_deterministic():
    easy_dataset = _make_dataset(name="easy-ds", raw_content=RAW_EASY_JSONL)
    hard_dataset = _make_dataset(name="hard-ds", raw_content=RAW_HARD_JSONL)
    easy_questions = load_questions(easy_dataset)
    hard_questions = load_questions(hard_dataset)

    selected_first = select_questions_from_pools(easy_questions, hard_questions, easy_ratio=67, total=3, seed=42)
    selected_second = select_questions_from_pools(easy_questions, hard_questions, easy_ratio=67, total=3, seed=42)

    assert len(selected_first) == 3
    assert sum(1 for q in selected_first if q.difficulty == "easy") == 2
    assert sum(1 for q in selected_first if q.difficulty == "hard") == 1
    assert [q.question for q in selected_first] == [q.question for q in selected_second]


@pytest.mark.django_db
def test_preview_snapshot_counts_supports_easy_hard_dataset_combo():
    easy_dataset = _make_dataset(name="easy-ds", raw_content=RAW_EASY_JSONL)
    hard_dataset = _make_dataset(name="hard-ds", raw_content=RAW_HARD_JSONL)
    runner = PilotEvaluationRunner()

    preview = runner.preview_snapshot_counts(
        dataset=None, easy_dataset=easy_dataset, hard_dataset=hard_dataset, easy_ratio=67, seed=42, total_questions=3
    )
    assert preview == {"total_questions": 3, "easy_count": 2, "hard_count": 1}


@pytest.mark.django_db
def test_evaluation_run_serializer_creates_run_with_easy_hard_dataset_combo():
    easy_dataset = _make_dataset(name="easy-ds", raw_content=RAW_EASY_JSONL)
    hard_dataset = _make_dataset(name="hard-ds", raw_content=RAW_HARD_JSONL)
    model = LLMModel.objects.create(provider="vllm", name="combo-model", display_name="Combo Model")

    serializer = EvaluationRunSerializer(
        data={
            "name": "combo-run",
            "easy_dataset": easy_dataset.id,
            "hard_dataset": hard_dataset.id,
            "easy_ratio": 67,
            "model_ids": [model.id],
            "config": {"seed": 42, "total_questions": 3},
            "notes": "",
        }
    )
    assert serializer.is_valid(), serializer.errors
    run = serializer.save()

    assert run.dataset_id == easy_dataset.id
    assert run.easy_dataset_id == easy_dataset.id
    assert run.hard_dataset_id == hard_dataset.id

    snapshot = EvaluationDatasetSnapshot.objects.get(run=run)
    assert snapshot.easy_dataset_id == easy_dataset.id
    assert snapshot.hard_dataset_id == hard_dataset.id
    assert snapshot.easy_ratio == 67
    assert snapshot.total_questions == 3
    easy_count = sum(1 for item in snapshot.questions_payload if item["difficulty"] == "easy")
    hard_count = sum(1 for item in snapshot.questions_payload if item["difficulty"] == "hard")
    assert easy_count == 2
    assert hard_count == 1


@pytest.mark.django_db
def test_evaluation_run_serializer_rejects_partial_easy_hard_combo():
    easy_dataset = _make_dataset(name="easy-ds", raw_content=RAW_EASY_JSONL)
    model = LLMModel.objects.create(provider="vllm", name="partial-model", display_name="Partial Model")

    serializer = EvaluationRunSerializer(
        data={
            "name": "partial-run",
            "easy_dataset": easy_dataset.id,
            "model_ids": [model.id],
            "config": {},
            "notes": "",
        }
    )
    assert not serializer.is_valid()
    assert "Easy 데이터셋과 Hard 데이터셋을 모두 지정해야 합니다." in str(serializer.errors)


@pytest.mark.django_db
def test_evaluation_run_serializer_requires_dataset_or_combo():
    model = LLMModel.objects.create(provider="vllm", name="no-dataset-model", display_name="No Dataset Model")

    serializer = EvaluationRunSerializer(
        data={
            "name": "no-dataset-run",
            "model_ids": [model.id],
            "config": {},
            "notes": "",
        }
    )
    assert not serializer.is_valid()
    assert "데이터셋 또는 Easy/Hard 데이터셋 조합을 지정해야 합니다." in str(serializer.errors)
