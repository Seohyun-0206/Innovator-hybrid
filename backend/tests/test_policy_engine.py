from decimal import Decimal

from apps.catalog.entities import LLMModelCandidate
from apps.routing.analyzer import PromptAnalysis
from apps.routing.policy_engine import PolicyEngine


def test_privacy_first_routes_to_local_model_when_sensitive_data_is_detected():
    models = [
        LLMModelCandidate(
            provider="openai",
            name="gpt-4.1-mini",
            role="general",
            quality_level=5,
            speed_level=4,
            cost_level=3,
            privacy_level="external",
            context_window=128000,
        ),
        LLMModelCandidate(
            provider="ollama",
            name="llama3.1:8b",
            role="general",
            quality_level=3,
            speed_level=5,
            cost_level=1,
            privacy_level="local",
            context_window=8192,
        ),
    ]

    result = PolicyEngine().select_model(
        policy_name="privacy-first",
        analysis=PromptAnalysis(
            has_sensitive_data=True,
            is_code=False,
            is_long_context=False,
            requires_reasoning=False,
            estimated_tokens=120,
        ),
        candidates=models,
    )

    assert result.model.provider == "ollama"
    assert result.model.privacy_level == "local"
    assert "sensitive data" in result.reason


def test_quality_first_prefers_highest_quality_reasoning_model():
    models = [
        LLMModelCandidate("ollama", "llama3.1:8b", "general", 3, 5, 1, "local", 8192),
        LLMModelCandidate("ollama", "deepseek-r1:8b", "reasoning", 5, 2, 1, "local", 32768),
    ]

    result = PolicyEngine().select_model(
        policy_name="quality-first",
        analysis=PromptAnalysis(
            has_sensitive_data=False,
            is_code=False,
            is_long_context=False,
            requires_reasoning=True,
            estimated_tokens=200,
        ),
        candidates=models,
    )

    assert result.model.name == "deepseek-r1:8b"
    assert "quality-first" in result.reason


def test_code_prompt_prefers_coding_role_model():
    models = [
        LLMModelCandidate("ollama", "llama3.1:8b", "general", 3, 5, 1, "local", 8192),
        LLMModelCandidate("ollama", "qwen2.5-coder:7b", "coding", 4, 4, 1, "local", 32768),
    ]

    result = PolicyEngine().select_model(
        policy_name="cost-first",
        analysis=PromptAnalysis(
            has_sensitive_data=False,
            is_code=True,
            is_long_context=False,
            requires_reasoning=False,
            estimated_tokens=160,
        ),
        candidates=models,
    )

    assert result.model.name == "qwen2.5-coder:7b"
    assert "coding" in result.reason


def test_policy_config_weights_change_model_ranking():
    models = [
        LLMModelCandidate("ollama", "slow-high-quality", "general", 5, 1, 1, "local", 8192),
        LLMModelCandidate("ollama", "fast-medium-quality", "general", 3, 5, 1, "local", 8192),
    ]

    result = PolicyEngine().select_model(
        policy_name="custom-speed",
        policy_config={
            "quality_weight": 1,
            "speed_weight": 10,
            "cost_weight": 1,
            "context_weight": 0,
            "local_only": False,
        },
        analysis=PromptAnalysis(
            has_sensitive_data=False,
            is_code=False,
            is_long_context=False,
            requires_reasoning=False,
            estimated_tokens=40,
        ),
        candidates=models,
    )

    assert result.model.name == "fast-medium-quality"
    assert "custom policy config" in result.reason


def test_simulation_returns_ranked_candidate_scores():
    models = [
        LLMModelCandidate("openai", "gpt-4.1-mini", "general", 5, 4, 3, "external", 128000),
        LLMModelCandidate(
            "ollama",
            "qwen2.5-coder:7b",
            "coding",
            4,
            4,
            1,
            "local",
            32768,
            Decimal("0.1000"),
            Decimal("0.2000"),
            1500,
            90,
        ),
        LLMModelCandidate("ollama", "llama3.1:8b", "general", 3, 5, 1, "local", 8192),
    ]

    result = PolicyEngine().simulate(
        policy_name="cost-first",
        analysis=PromptAnalysis(
            has_sensitive_data=False,
            is_code=True,
            is_long_context=False,
            requires_reasoning=False,
            estimated_tokens=160,
        ),
        candidates=models,
    )

    assert result.selected.name == "qwen2.5-coder:7b"
    assert result.candidates[0].rank == 1
    assert result.candidates[0].score_breakdown["total"] > 0
    assert result.candidates[0].estimated_total_cost_usd == Decimal("0.000048")
    assert result.candidates[0].model.average_latency_ms == 1500
    assert result.candidates[0].model.timeout_seconds == 90
    assert any(not candidate.eligible for candidate in result.candidates)


def test_policy_rule_builder_budget_can_fallback_to_local_models():
    models = [
        LLMModelCandidate(
            "openai",
            "expensive-coder",
            "coding",
            5,
            5,
            1,
            "external",
            128000,
            Decimal("1000.0000"),
            Decimal("1000.0000"),
        ),
        LLMModelCandidate("ollama", "local-general", "general", 3, 3, 1, "local", 8192),
    ]

    result = PolicyEngine().simulate(
        policy_name="cost-first",
        policy_config={
            "prefer_coding_models": True,
            "max_estimated_cost_usd": "0.000001",
            "fallback_to_local_on_budget": True,
        },
        analysis=PromptAnalysis(
            has_sensitive_data=False,
            is_code=True,
            is_long_context=False,
            requires_reasoning=False,
            estimated_tokens=1000,
        ),
        candidates=models,
    )

    assert result.selected.name == "local-general"
    assert "budget exceeded" in result.reason
