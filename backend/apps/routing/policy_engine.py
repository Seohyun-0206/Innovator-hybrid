from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from apps.catalog.entities import LLMModelCandidate
from apps.routing.analyzer import PromptAnalysis


@dataclass(frozen=True)
class RoutingDecision:
    model: LLMModelCandidate
    reason: str


@dataclass(frozen=True)
class ModelScore:
    model: LLMModelCandidate
    eligible: bool
    rank: Optional[int]
    score: float
    estimated_input_cost_usd: Decimal
    estimated_output_cost_usd: Decimal
    estimated_total_cost_usd: Decimal
    score_breakdown: dict
    reasons: list[str]


@dataclass(frozen=True)
class RoutingSimulation:
    selected: LLMModelCandidate
    reason: str
    candidates: list[ModelScore]


class PolicyEngine:
    # 정책 엔진은 의도적으로 provider에 의존하지 않습니다. 모델 메타데이터만 보고
    # 판단하므로, 나중에 OpenAI/Gemini를 추가해도 라우팅 규칙은 크게 바뀌지 않습니다.
    def select_model(
        self,
        *,
        policy_name: str,
        policy_config: Optional[dict] = None,
        analysis: PromptAnalysis,
        candidates: Iterable[LLMModelCandidate],
    ) -> RoutingDecision:
        policy_config = policy_config or {}
        available = list(candidates)
        if not available:
            raise ValueError("No active LLM models are available.")

        filtered = available
        reasons = []

        # 개인정보 제약은 capability 점수 계산보다 먼저 적용합니다. 민감한 프롬프트가
        # 점수가 높다는 이유만으로 외부 모델에 전달되는 일을 막기 위해서입니다.
        requires_local = analysis.has_sensitive_data or policy_name == "privacy-first" or policy_config.get("local_only")
        if requires_local:
            local_models = [model for model in filtered if model.privacy_level == "local"]
            if local_models:
                filtered = local_models
                if analysis.has_sensitive_data:
                    reasons.append("sensitive data requires a local model")
                elif policy_config.get("local_only"):
                    reasons.append("policy config requires a local model")
                else:
                    reasons.append("privacy-first policy requires a local model")

        # 프롬프트 신호로 후보군을 먼저 좁힙니다. 이후 ranking은 서로 무관한 모델을
        # 비교하지 않고, 필요한 capability 범위 안에서 최적 모델을 고릅니다.
        if analysis.is_code:
            coding_models = [model for model in filtered if model.role == "coding"]
            if coding_models and policy_config.get("prefer_coding_models", True):
                filtered = coding_models
                reasons.append("coding prompt matched coding-specialized models")

        preferred_tiers = policy_config.get("preferred_model_tiers") or []
        if preferred_tiers:
            tier_models = [model for model in filtered if model.model_tier in preferred_tiers]
            if tier_models:
                filtered = tier_models
                reasons.append(f"routing rule matched model tier: {', '.join(preferred_tiers)}")

        if analysis.is_long_context:
            required_window = max(analysis.estimated_tokens * 2, 8192)
            long_context_models = [
                model for model in filtered if model.context_window >= required_window
            ]
            if long_context_models:
                filtered = long_context_models
                reasons.append("long prompt matched models with larger context windows")

        if analysis.requires_reasoning:
            reasoning_models = [model for model in filtered if model.role == "reasoning"]
            if reasoning_models and policy_config.get("prefer_reasoning_models", True):
                filtered = reasoning_models
                reasons.append("reasoning prompt matched reasoning-specialized models")

        min_context_window = int(policy_config.get("min_context_window", 0) or 0)
        if min_context_window > 0:
            min_context_models = [
                model for model in filtered if model.context_window >= min_context_window
            ]
            if min_context_models:
                filtered = min_context_models
                reasons.append(f"policy requires context window >= {min_context_window}")

        max_estimated_cost_usd = self._optional_decimal(policy_config.get("max_estimated_cost_usd"))
        if max_estimated_cost_usd is not None:
            affordable_models = [
                model
                for model in filtered
                if self._estimate_total_cost(model, analysis.estimated_tokens) <= max_estimated_cost_usd
            ]
            if affordable_models:
                filtered = affordable_models
                reasons.append(f"policy requires estimated cost <= {max_estimated_cost_usd}")
            elif policy_config.get("fallback_to_local_on_budget"):
                local_models = [model for model in available if model.privacy_level == "local"]
                if local_models:
                    filtered = local_models
                    reasons.append("budget limit exceeded; fallback to local models")

        selected = self._rank(policy_name, filtered, policy_config)[0]
        if not reasons:
            if policy_config:
                reasons.append(f"{policy_name} custom policy config selected the best ranked active model")
            else:
                reasons.append(f"{policy_name} selected the best ranked active model")
        else:
            if policy_config:
                reasons.append(f"{policy_name} custom policy config selected the final model")
            else:
                reasons.append(f"{policy_name} ranking selected the final model")

        return RoutingDecision(model=selected, reason="; ".join(reasons))

    def simulate(
        self,
        *,
        policy_name: str,
        policy_config: Optional[dict] = None,
        analysis: PromptAnalysis,
        candidates: Iterable[LLMModelCandidate],
    ) -> RoutingSimulation:
        policy_config = policy_config or {}
        available = list(candidates)
        if not available:
            raise ValueError("No active LLM models are available.")

        filtered = available
        excluded_reasons: dict[tuple[str, str], list[str]] = {}
        applied_reasons = []

        def exclude(models: list[LLMModelCandidate], reason: str):
            kept_keys = {(model.provider, model.name) for model in models}
            for model in filtered:
                if (model.provider, model.name) not in kept_keys:
                    excluded_reasons.setdefault((model.provider, model.name), []).append(reason)

        requires_local = analysis.has_sensitive_data or policy_name == "privacy-first" or policy_config.get("local_only")
        if requires_local:
            local_models = [model for model in filtered if model.privacy_level == "local"]
            if local_models:
                reason = "privacy/local constraint"
                previous = filtered
                filtered = local_models
                for model in previous:
                    if model not in local_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)

        if analysis.is_code:
            coding_models = [model for model in filtered if model.role == "coding"]
            if coding_models and policy_config.get("prefer_coding_models", True):
                reason = "coding-specialized filter"
                previous = filtered
                filtered = coding_models
                for model in previous:
                    if model not in coding_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)

        preferred_tiers = policy_config.get("preferred_model_tiers") or []
        if preferred_tiers:
            tier_models = [model for model in filtered if model.model_tier in preferred_tiers]
            if tier_models:
                reason = f"model tier in {', '.join(preferred_tiers)}"
                previous = filtered
                filtered = tier_models
                for model in previous:
                    if model not in tier_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)

        if analysis.is_long_context:
            required_window = max(analysis.estimated_tokens * 2, 8192)
            long_context_models = [
                model for model in filtered if model.context_window >= required_window
            ]
            if long_context_models:
                reason = f"context window >= {required_window}"
                previous = filtered
                filtered = long_context_models
                for model in previous:
                    if model not in long_context_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)

        if analysis.requires_reasoning:
            reasoning_models = [model for model in filtered if model.role == "reasoning"]
            if reasoning_models and policy_config.get("prefer_reasoning_models", True):
                reason = "reasoning-specialized filter"
                previous = filtered
                filtered = reasoning_models
                for model in previous:
                    if model not in reasoning_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)

        min_context_window = int(policy_config.get("min_context_window", 0) or 0)
        if min_context_window > 0:
            min_context_models = [model for model in filtered if model.context_window >= min_context_window]
            if min_context_models:
                reason = f"context window >= {min_context_window}"
                previous = filtered
                filtered = min_context_models
                for model in previous:
                    if model not in min_context_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)

        max_estimated_cost_usd = self._optional_decimal(policy_config.get("max_estimated_cost_usd"))
        if max_estimated_cost_usd is not None:
            affordable_models = [
                model
                for model in filtered
                if self._estimate_total_cost(model, analysis.estimated_tokens) <= max_estimated_cost_usd
            ]
            if affordable_models:
                reason = f"estimated cost <= {max_estimated_cost_usd}"
                previous = filtered
                filtered = affordable_models
                for model in previous:
                    if model not in affordable_models:
                        excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                applied_reasons.append(reason)
            elif policy_config.get("fallback_to_local_on_budget"):
                local_models = [model for model in available if model.privacy_level == "local"]
                if local_models:
                    reason = "budget exceeded; local fallback"
                    previous = filtered
                    filtered = local_models
                    for model in available:
                        if model not in local_models:
                            excluded_reasons.setdefault((model.provider, model.name), []).append(reason)
                    applied_reasons.append(reason)

        ranked = self._rank(policy_name, filtered, policy_config)
        selected = ranked[0]
        rank_lookup = {(model.provider, model.name): index + 1 for index, model in enumerate(ranked)}

        model_scores = []
        for model in available:
            key = (model.provider, model.name)
            rank = rank_lookup.get(key)
            eligible = rank is not None
            breakdown = self._score_breakdown(policy_name, model, policy_config)
            model_scores.append(
                ModelScore(
                    model=model,
                    eligible=eligible,
                    rank=rank,
                    score=breakdown["total"] if eligible else 0,
                    estimated_input_cost_usd=self._estimate_input_cost(model, analysis.estimated_tokens),
                    estimated_output_cost_usd=self._estimate_output_cost(model, analysis.estimated_tokens),
                    estimated_total_cost_usd=self._estimate_total_cost(model, analysis.estimated_tokens),
                    score_breakdown=breakdown,
                    reasons=(
                        [f"ranked #{rank} by {policy_name}"] if eligible else excluded_reasons.get(key, ["filtered out"])
                    ),
                )
            )

        model_scores.sort(key=lambda item: (item.rank is None, item.rank or 9999, -item.score))
        reason = "; ".join(applied_reasons + [f"{policy_name} selected the top ranked model"])
        return RoutingSimulation(selected=selected, reason=reason, candidates=model_scores)

    def _rank(self, policy_name: str, models: list[LLMModelCandidate], policy_config: dict):
        if policy_config:
            # 관리자 화면에서 입력한 가중치로 custom policy 점수를 계산합니다.
            # quality/speed/context는 점수를 올리고, cost는 점수를 낮춥니다.
            quality_weight = int(policy_config.get("quality_weight", 1))
            speed_weight = int(policy_config.get("speed_weight", 1))
            cost_weight = int(policy_config.get("cost_weight", 1))
            context_weight = int(policy_config.get("context_weight", 0))
            return sorted(
                models,
                key=lambda model: -(
                    (model.quality_level * quality_weight)
                    + (model.speed_level * speed_weight)
                    - (model.cost_level * cost_weight)
                    + ((model.context_window // 8192) * context_weight)
                ),
            )

        # 기본 정책은 초기 실행 시에도 예측 가능한 결과를 주기 위한 fallback입니다.
        if policy_name == "quality-first":
            return sorted(
                models,
                key=lambda model: (
                    -model.quality_level,
                    model.cost_level,
                    -model.speed_level,
                    -model.context_window,
                ),
            )
        if policy_name == "privacy-first":
            return sorted(
                models,
                key=lambda model: (
                    model.privacy_level != "local",
                    model.cost_level,
                    -model.quality_level,
                    -model.speed_level,
                ),
            )
        return sorted(
            models,
            key=lambda model: (
                model.cost_level,
                -model.speed_level,
                -model.quality_level,
                -model.context_window,
            ),
        )

    def _score_breakdown(self, policy_name: str, model: LLMModelCandidate, policy_config: dict) -> dict:
        context_score = model.context_window // 8192
        if policy_config:
            quality_weight = int(policy_config.get("quality_weight", 1))
            speed_weight = int(policy_config.get("speed_weight", 1))
            cost_weight = int(policy_config.get("cost_weight", 1))
            context_weight = int(policy_config.get("context_weight", 0))
            quality = model.quality_level * quality_weight
            speed = model.speed_level * speed_weight
            cost = -(model.cost_level * cost_weight)
            context = context_score * context_weight
            return {
                "quality": quality,
                "speed": speed,
                "cost": cost,
                "context": context,
                "privacy": 0,
                "total": quality + speed + cost + context,
            }

        privacy = 100 if model.privacy_level == "local" else 0
        if policy_name == "quality-first":
            quality = model.quality_level * 100
            speed = model.speed_level * 5
            cost = -model.cost_level * 10
            context = context_score
            privacy = 0
        elif policy_name == "privacy-first":
            quality = model.quality_level * 5
            speed = model.speed_level * 5
            cost = -model.cost_level * 10
            context = 0
        else:
            quality = model.quality_level * 5
            speed = model.speed_level * 10
            cost = (6 - model.cost_level) * 100
            context = context_score
            privacy = 0
        return {
            "quality": quality,
            "speed": speed,
            "cost": cost,
            "context": context,
            "privacy": privacy,
            "total": quality + speed + cost + context + privacy,
        }

    def _estimate_input_cost(self, model: LLMModelCandidate, input_tokens: int) -> Decimal:
        return (model.input_token_price_per_1m * Decimal(input_tokens)) / Decimal(1_000_000)

    def _estimate_output_cost(self, model: LLMModelCandidate, input_tokens: int) -> Decimal:
        # 시뮬레이터 단계에서는 실제 응답이 없으므로 출력 토큰을 입력 토큰과 동일하게 추정합니다.
        return (model.output_token_price_per_1m * Decimal(input_tokens)) / Decimal(1_000_000)

    def _estimate_total_cost(self, model: LLMModelCandidate, input_tokens: int) -> Decimal:
        return self._estimate_input_cost(model, input_tokens) + self._estimate_output_cost(model, input_tokens)

    def _optional_decimal(self, value) -> Optional[Decimal]:
        if value in (None, ""):
            return None
        return Decimal(str(value))
