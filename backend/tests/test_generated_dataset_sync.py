import pytest

from apps.catalog.models import EvaluationDataset, GeneratedDataset, ServiceFeature


def _make_service_feature(**overrides):
    defaults = {"name": "FAQ 기능"}
    defaults.update(overrides)
    return ServiceFeature.objects.create(**defaults)


@pytest.mark.django_db
def test_completed_generated_dataset_creates_evaluation_dataset():
    feature = _make_service_feature()
    generated = GeneratedDataset.objects.create(
        service_feature=feature,
        name="General FAQ 생성 데이터셋",
        dataset_type="qa",
        data_format="jsonl",
        status="completed",
        raw_content='{"question": "Q1"}',
        question_count=1,
    )

    evaluation_dataset = EvaluationDataset.objects.get(source_generated_dataset=generated)
    assert evaluation_dataset.name == "General FAQ 생성 데이터셋"
    assert evaluation_dataset.source == "generated"
    assert evaluation_dataset.question_count == 1


@pytest.mark.django_db
def test_pending_generated_dataset_does_not_create_evaluation_dataset():
    feature = _make_service_feature()
    generated = GeneratedDataset.objects.create(
        service_feature=feature,
        name="진행중 데이터셋",
        status="pending",
    )

    assert not EvaluationDataset.objects.filter(source_generated_dataset=generated).exists()


@pytest.mark.django_db
def test_updating_completed_generated_dataset_syncs_same_evaluation_dataset():
    feature = _make_service_feature()
    generated = GeneratedDataset.objects.create(
        service_feature=feature,
        name="FAQ v1",
        status="completed",
        raw_content='{"question": "Q1"}',
        question_count=1,
    )
    first_id = EvaluationDataset.objects.get(source_generated_dataset=generated).id

    generated.raw_content = '{"question": "Q1"}\n{"question": "Q2"}'
    generated.question_count = 2
    generated.name = "FAQ v2"
    generated.save()

    assert EvaluationDataset.objects.filter(source_generated_dataset=generated).count() == 1
    updated = EvaluationDataset.objects.get(source_generated_dataset=generated)
    assert updated.id == first_id
    assert updated.name == "FAQ v2"
    assert updated.question_count == 2
