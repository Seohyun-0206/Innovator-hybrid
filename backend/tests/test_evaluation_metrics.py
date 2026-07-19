import time

import pytest

from apps.catalog.evaluation import PilotEvaluationRunner
from apps.catalog.model_metrics import EvaluationQuestion
from apps.catalog.models import (
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    LLMModel,
)
from apps.providers.base import LLMResponse


@pytest.mark.django_db
def test_tpot_and_throughput_are_computed_from_ttft_and_usage(monkeypatch):
    model = LLMModel.objects.create(
        provider="vllm",
        name="Qwen/Qwen3-8B",
        display_name="Qwen3 8B (vLLM)",
    )
    dataset = EvaluationDataset.objects.create(name="mini", question_count=2)
    run = EvaluationRun.objects.create(name="mini-run", dataset=dataset)
    result = EvaluationResult.objects.create(run=run, dataset=dataset, model=model)

    questions = [
        EvaluationQuestion(question="Q1", choices=["A", "B", "C", "D"], answer="A", subject="s", category="c"),
        EvaluationQuestion(question="Q2", choices=["A", "B", "C", "D"], answer="B", subject="s", category="c"),
    ]

    # 호출 순서: run_started, 문항1 started, 문항1 latency, 문항2 started, 문항2 latency, run_elapsed
    # -> 문항1 latency=0.5s, 문항2 latency=1.0s, 전체 run_elapsed=1.5s (전부 2진수로 정확히 표현되는 값이라
    # 부동소수점 오차 없이 결정적으로 검증할 수 있습니다).
    clock = iter([0.0, 0.0, 0.5, 0.5, 1.5, 1.5])
    monkeypatch.setattr("apps.catalog.evaluation.time.perf_counter", lambda: next(clock))

    responses = [
        LLMResponse(text="정답: A", raw={}, usage={"prompt_tokens": 10, "completion_tokens": 5}, ttft_ms=100),
        LLMResponse(text="정답: B", raw={}, usage={"prompt_tokens": 10, "completion_tokens": 9}, ttft_ms=200),
    ]

    class FakeProvider:
        def chat(self, *, model, messages, options):
            return responses.pop(0)

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    runner = PilotEvaluationRunner()
    runner.provider_registry = FakeRegistry()
    runner.evaluate_model_result(result, questions, config={})

    result.refresh_from_db()

    # item 1: latency 500ms, ttft 100ms, output 5 tok -> tpot=(500-100)/(5-1)=100ms, throughput=5/0.5=10 tok/s
    # item 2: latency 1000ms, ttft 200ms, output 9 tok -> tpot=(1000-200)/(9-1)=100ms, throughput=9/1.0=9 tok/s
    assert result.ttft_p50_ms == 100
    assert result.ttft_p95_ms == 200
    assert float(result.tpot_p50_ms) == pytest.approx(100.0, abs=0.001)
    assert float(result.tpot_p95_ms) == pytest.approx(100.0, abs=0.001)
    assert float(result.throughput_p50_tps) == pytest.approx(9.0, abs=0.001)
    assert float(result.throughput_p95_tps) == pytest.approx(10.0, abs=0.001)
    # 시스템 throughput = 전체 output_tokens(14) / 전체 wall-clock(1.5s)
    assert float(result.system_throughput_tps) == pytest.approx(14 / 1.5, abs=0.01)


@pytest.mark.django_db
def test_tpot_and_ttft_are_none_when_provider_has_no_streaming_signal(monkeypatch):
    model = LLMModel.objects.create(provider="ollama", name="llama3", display_name="Llama 3")
    dataset = EvaluationDataset.objects.create(name="mini", question_count=1)
    run = EvaluationRun.objects.create(name="mini-run", dataset=dataset)
    result = EvaluationResult.objects.create(run=run, dataset=dataset, model=model)

    questions = [EvaluationQuestion(question="Q1", choices=["A", "B", "C", "D"], answer="A", subject="s", category="c")]

    clock = iter([0.0, 0.0, 0.1, 0.1])
    monkeypatch.setattr("apps.catalog.evaluation.time.perf_counter", lambda: next(clock))

    class FakeProvider:
        def chat(self, *, model, messages, options):
            return LLMResponse(text="정답: A", raw={})

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    runner = PilotEvaluationRunner()
    runner.provider_registry = FakeRegistry()
    runner.evaluate_model_result(result, questions, config={})

    result.refresh_from_db()

    assert result.ttft_p50_ms is None
    assert result.tpot_p50_ms is None
    assert result.throughput_p50_tps is not None
    assert result.kv_cache_usage_avg is None


@pytest.mark.django_db
def test_kv_cache_usage_is_polled_when_provider_supports_it(monkeypatch):
    model = LLMModel.objects.create(provider="vllm", name="Qwen/Qwen3-8B", display_name="Qwen3 8B (vLLM)")
    dataset = EvaluationDataset.objects.create(name="mini", question_count=1)
    run = EvaluationRun.objects.create(name="mini-run", dataset=dataset)
    result = EvaluationResult.objects.create(run=run, dataset=dataset, model=model)

    questions = [EvaluationQuestion(question="Q1", choices=["A", "B", "C", "D"], answer="A", subject="s", category="c")]

    # 폴링 주기를 짧게 줄여 테스트가 실제로 걸리는 시간을 최소화합니다.
    monkeypatch.setattr("apps.catalog.model_metrics.KV_CACHE_POLL_INTERVAL_SECONDS", 0.01)

    kv_values = iter([0.1, 0.5, 0.9])

    class FakeProvider:
        def chat(self, *, model, messages, options):
            time.sleep(0.05)  # 폴러가 여러 번 샘플링할 시간을 준다
            return LLMResponse(text="정답: A", raw={})

        def fetch_kv_cache_usage(self):
            try:
                return next(kv_values)
            except StopIteration:
                return 0.9

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    runner = PilotEvaluationRunner()
    runner.provider_registry = FakeRegistry()
    runner.evaluate_model_result(result, questions, config={})

    result.refresh_from_db()

    assert result.kv_cache_usage_min is not None
    assert result.kv_cache_usage_max is not None
    assert float(result.kv_cache_usage_min) == pytest.approx(0.1, abs=0.001)
    assert float(result.kv_cache_usage_max) == pytest.approx(0.9, abs=0.001)
    assert float(result.kv_cache_usage_min) <= float(result.kv_cache_usage_avg) <= float(result.kv_cache_usage_max)
