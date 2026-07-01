import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db.models import Q, Sum
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasScreenAccess
from apps.catalog.health import evaluate_model_health
from apps.catalog.models import (
    LLMModel,
    ResponseValidationRule,
    RoutingPolicy,
    RoutingRule,
    ThresholdRule,
    UsageQuota,
)
from apps.catalog.usage import current_month_start
from apps.logs.models import RoutingLog
from apps.logs.serializers import RoutingLogSerializer
from apps.providers.registry import ProviderRegistry
from apps.routing.analyzer import PromptAnalyzer
from apps.routing.policy_engine import PolicyEngine


class ChatRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(allow_blank=False)
    policy = serializers.SlugField(default="cost-first")


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    action: str
    reason: str


@dataclass(frozen=True)
class HealthDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ValidationDecision:
    passed: bool
    status: str
    error: str


class RoutingSimulatorView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "simulator"

    analyzer = PromptAnalyzer()
    policy_engine = PolicyEngine()

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prompt = serializer.validated_data["prompt"]
        policy = serializer.validated_data["policy"]

        policy_record = RoutingPolicy.objects.filter(name=policy, is_active=True).first()
        if not policy_record:
            return Response(
                {"detail": f"Routing policy '{policy}' is not active or does not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_models = list(LLMModel.objects.filter(is_active=True))
        analysis = self.analyzer.analyze(prompt)
        matched_rules = get_matching_routing_rules(analysis)
        matched_threshold_rules = get_matching_threshold_rules(analysis)
        matched_validation_rules = get_matching_validation_rules(analysis)
        policy_config = build_policy_config(policy_record.priority_config, matched_rules, matched_threshold_rules)
        simulation = self.policy_engine.simulate(
            policy_name=policy,
            policy_config=policy_config,
            analysis=analysis,
            candidates=[model.to_candidate() for model in active_models],
        )
        model_lookup = {
            (model.provider, model.name): model
            for model in active_models
        }

        return Response(
            {
                "policy": policy,
                "selected_provider": simulation.selected.provider,
                "selected_model": simulation.selected.name,
                "routing_reason": simulation.reason,
                "analysis": {
                    "has_sensitive_data": analysis.has_sensitive_data,
                    "is_code": analysis.is_code,
                    "is_structured_output": analysis.is_structured_output,
                    "is_long_context": analysis.is_long_context,
                    "requires_reasoning": analysis.requires_reasoning,
                    "estimated_tokens": analysis.estimated_tokens,
                },
                "matched_rules": serialize_matched_rules(matched_rules),
                "matched_threshold_rules": serialize_matched_threshold_rules(matched_threshold_rules),
                "matched_validation_rules": serialize_matched_validation_rules(matched_validation_rules),
                "candidates": [
                    {
                        "provider": score.model.provider,
                        "name": score.model.name,
                        "model_tier": score.model.model_tier,
                        "display_name": model_lookup[(score.model.provider, score.model.name)].display_name,
                        "role": score.model.role,
                        "privacy_level": score.model.privacy_level,
                        "context_window": score.model.context_window,
                        "input_token_price_per_1m": score.model.input_token_price_per_1m,
                        "output_token_price_per_1m": score.model.output_token_price_per_1m,
                        "average_latency_ms": score.model.average_latency_ms,
                        "timeout_seconds": score.model.timeout_seconds,
                        "estimated_input_cost_usd": score.estimated_input_cost_usd,
                        "estimated_output_cost_usd": score.estimated_output_cost_usd,
                        "estimated_total_cost_usd": score.estimated_total_cost_usd,
                        "eligible": score.eligible,
                        "rank": score.rank,
                        "score": score.score,
                        "score_breakdown": score.score_breakdown,
                        "reasons": score.reasons,
                    }
                    for score in simulation.candidates
                ],
            }
        )


class ChatView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "playground"

    # 이 객체들은 요청별 상태를 갖지 않습니다. view class에 한 번만 만들어두면
    # 매 요청마다 새로 생성하지 않아도 되고, 요청 상태가 섞일 위험도 없습니다.
    analyzer = PromptAnalyzer()
    policy_engine = PolicyEngine()
    provider_registry = ProviderRegistry()

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prompt = serializer.validated_data["prompt"]
        policy = serializer.validated_data["policy"]

        # 정책은 관리자 화면에서 수정됩니다. chat endpoint는 항상 DB의 active 정책을
        # 읽기 때문에 서버 재시작 없이 변경 사항이 바로 적용됩니다.
        policy_record = RoutingPolicy.objects.filter(name=policy, is_active=True).first()
        if not policy_record:
            return Response(
                {"detail": f"Routing policy '{policy}' is not active or does not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_models = list(
            LLMModel.objects.select_related("provider_credential").filter(is_active=True)
        )
        analysis = self.analyzer.analyze(prompt)
        matched_rules = get_matching_routing_rules(analysis)
        matched_threshold_rules = get_matching_threshold_rules(analysis)
        matched_validation_rules = get_matching_validation_rules(analysis)
        policy_config = build_policy_config(policy_record.priority_config, matched_rules, matched_threshold_rules)

        # 먼저 모델 메타데이터로 후보 순위를 계산합니다. 실제 provider 호출이 실패하면
        # 같은 순위표에서 다음 eligible 후보로 fallback합니다.
        simulation = self.policy_engine.simulate(
            policy_name=policy,
            policy_config=policy_config,
            analysis=analysis,
            candidates=[model.to_candidate() for model in active_models],
        )
        model_lookup = {
            (model.provider, model.name): model
            for model in active_models
        }
        fallback_candidates = [
            score
            for score in simulation.candidates
            if score.eligible and score.rank is not None
        ]

        started = time.perf_counter()
        response_text = ""
        error_message = ""
        selected_provider = simulation.selected.provider
        selected_model_name = simulation.selected.name
        estimated_cost_usd = 0
        routing_reason = simulation.reason
        if matched_rules:
            routing_reason = (
                f"{routing_reason}; matched routing rules: "
                + ", ".join(f"{rule.rule_id}->{rule.target_tier}" for rule in matched_rules)
            )
        if matched_threshold_rules:
            routing_reason = (
                f"{routing_reason}; matched threshold rules: "
                + ", ".join(f"{rule.rule_id}:{rule.metric_key}{rule.operator}{rule.threshold_value}" for rule in matched_threshold_rules)
            )
        response_status = status.HTTP_200_OK
        attempts = []
        health_blocked_reasons = []
        quota_blocked_reasons = []
        validation_status = "not_required" if not matched_validation_rules else ""
        validation_errors = []
        stopped_by_block_quota = False
        succeeded = False

        for candidate in fallback_candidates:
            # provider 구현체는 벤더별 HTTP 형식을 공통 chat interface 뒤로 숨깁니다.
            # 모델에 credential이 지정되어 있으면 해당 credential로 provider를 생성합니다.
            # 지정되지 않은 경우에는 provider별 활성 credential 또는 환경변수 fallback을 사용합니다.
            db_model = model_lookup.get((candidate.model.provider, candidate.model.name))
            selected_provider = candidate.model.provider
            selected_model_name = candidate.model.name
            estimated_cost_usd = candidate.estimated_total_cost_usd
            health_decision = self.check_model_health(
                provider=candidate.model.provider,
                model_name=candidate.model.name,
            )
            if not health_decision.allowed:
                attempts.append(
                    f"{candidate.model.provider}/{candidate.model.name} skipped: {health_decision.reason}"
                )
                health_blocked_reasons.append(health_decision.reason)
                continue
            quota_decision = self.check_quota(
                user=request.user,
                provider=candidate.model.provider,
                estimated_cost_usd=estimated_cost_usd,
            )
            if not quota_decision.allowed:
                attempts.append(
                    f"{candidate.model.provider}/{candidate.model.name} skipped: {quota_decision.reason}"
                )
                quota_blocked_reasons.append(quota_decision.reason)
                if quota_decision.action == "block":
                    response_status = status.HTTP_429_TOO_MANY_REQUESTS
                    error_message = quota_decision.reason
                    stopped_by_block_quota = True
                    break
                continue
            try:
                provider = self.provider_registry.get(
                    candidate.model.provider,
                    credential=db_model.provider_credential if db_model else None,
                )
                llm_response = provider.chat(
                    model=candidate.model.name,
                    messages=[{"role": "user", "content": prompt}],
                    options={},
                )
                response_text = llm_response.text
                validation_decision = self.validate_response(
                    response_text=response_text,
                    validation_rules=matched_validation_rules,
                )
                validation_status = validation_decision.status
                if not validation_decision.passed:
                    validation_errors.append(validation_decision.error)
                    attempts.append(
                        f"{candidate.model.provider}/{candidate.model.name} validation failed: {validation_decision.error}"
                    )
                    recovery_rule = matched_validation_rules[0] if matched_validation_rules else None
                    recovery_action = get_recovery_action(recovery_rule)
                    if recovery_action == "strict_retry":
                        retry_prompt = build_retry_prompt(prompt, recovery_rule)
                        for retry_index in range(get_recovery_max_retries(recovery_rule)):
                            retry_response = provider.chat(
                                model=candidate.model.name,
                                messages=[{"role": "user", "content": retry_prompt}],
                                options={},
                            )
                            response_text = retry_response.text
                            retry_validation = self.validate_response(
                                response_text=response_text,
                                validation_rules=matched_validation_rules,
                            )
                            validation_status = retry_validation.status
                            if retry_validation.passed:
                                attempts.append(
                                    f"{candidate.model.provider}/{candidate.model.name} strict retry #{retry_index + 1} passed validation"
                                )
                                succeeded = True
                                break
                            validation_errors.append(retry_validation.error)
                            attempts.append(
                                f"{candidate.model.provider}/{candidate.model.name} strict retry #{retry_index + 1} failed validation: {retry_validation.error}"
                            )
                        if not succeeded:
                            continue
                    elif recovery_action == "block":
                        response_status = status.HTTP_422_UNPROCESSABLE_ENTITY
                        error_message = validation_decision.error
                        stopped_by_block_quota = True
                        break
                    elif recovery_action == "escalate":
                        attempts.append(
                            f"{candidate.model.provider}/{candidate.model.name} escalation requested to {get_recovery_target_tier(recovery_rule) or 'next tier'}"
                        )
                        continue
                    else:
                        continue
                attempts.append(f"{candidate.model.provider}/{candidate.model.name} succeeded")
                succeeded = True
                break
            except Exception as exc:
                error_message = str(exc)
                attempts.append(f"{candidate.model.provider}/{candidate.model.name} failed: {exc}")
        if stopped_by_block_quota:
            pass
        elif not succeeded:
            if quota_blocked_reasons:
                response_status = status.HTTP_429_TOO_MANY_REQUESTS
                error_message = quota_blocked_reasons[-1]
            elif health_blocked_reasons:
                response_status = status.HTTP_503_SERVICE_UNAVAILABLE
                error_message = health_blocked_reasons[-1]
            else:
                response_status = status.HTTP_502_BAD_GATEWAY

        if attempts:
            routing_reason = f"{routing_reason}; fallback attempts: {' | '.join(attempts)}"

        latency_ms = int((time.perf_counter() - started) * 1000)

        # provider 호출 성공/실패를 모두 기록합니다. catalog에는 등록됐지만 Ollama에
        # 설치되지 않은 모델을 찾을 때 실패 로그가 특히 유용합니다.
        log = RoutingLog.objects.create(
            user=request.user,
            prompt_summary=prompt[:240],
            policy=policy,
            selected_provider=selected_provider,
            selected_model=selected_model_name,
            routing_reason=routing_reason,
            latency_ms=latency_ms,
            estimated_tokens=analysis.estimated_tokens,
            estimated_cost_usd=estimated_cost_usd,
            response_text=response_text,
            error_message=error_message,
            validation_status=validation_status,
            validation_errors="\n".join(validation_errors),
        )

        payload = RoutingLogSerializer(log).data
        payload["analysis"] = {
            "has_sensitive_data": analysis.has_sensitive_data,
            "is_code": analysis.is_code,
            "is_structured_output": analysis.is_structured_output,
            "is_long_context": analysis.is_long_context,
            "requires_reasoning": analysis.requires_reasoning,
            "estimated_tokens": analysis.estimated_tokens,
        }
        payload["matched_rules"] = serialize_matched_rules(matched_rules)
        payload["matched_threshold_rules"] = serialize_matched_threshold_rules(matched_threshold_rules)
        payload["matched_validation_rules"] = serialize_matched_validation_rules(matched_validation_rules)
        return Response(payload, status=response_status)

    def validate_response(self, *, response_text: str, validation_rules: list[ResponseValidationRule]) -> ValidationDecision:
        if not validation_rules:
            return ValidationDecision(True, "not_required", "")
        for rule in validation_rules:
            decision = validate_response_text(response_text, rule.validation_type)
            if not decision.passed:
                return ValidationDecision(False, "failed", f"{rule.rule_id} {rule.validation_type}: {decision.error}")
        return ValidationDecision(True, "passed", "")

    def check_model_health(self, *, provider: str, model_name: str) -> HealthDecision:
        status = evaluate_model_health(provider=provider, model_name=model_name, record_event=True)
        if status.status == "unhealthy":
            return HealthDecision(False, status.reason)
        return HealthDecision(True, "")

    def check_quota(self, *, user, provider: str, estimated_cost_usd: Decimal) -> QuotaDecision:
        quotas = UsageQuota.objects.filter(is_active=True).filter(
            Q(user__isnull=True) | Q(user=user),
            Q(provider="") | Q(provider=provider),
        )
        if not quotas.exists():
            return QuotaDecision(True, "", "")

        month_start = current_month_start()
        for quota in quotas:
            usage = RoutingLog.objects.filter(created_at__gte=month_start)
            if quota.user_id is not None:
                usage = usage.filter(user=user)
            if quota.provider:
                usage = usage.filter(selected_provider=provider)
            request_count = usage.count()
            cost_sum = usage.aggregate(value=Sum("estimated_cost_usd"))["value"] or Decimal("0")
            if quota.monthly_request_limit is not None and request_count >= quota.monthly_request_limit:
                return QuotaDecision(
                    False,
                    quota.action_on_exceed,
                    f"monthly request quota exceeded for {provider}: {request_count}/{quota.monthly_request_limit}",
                )
            if quota.monthly_cost_limit_usd is not None and cost_sum + estimated_cost_usd > quota.monthly_cost_limit_usd:
                return QuotaDecision(
                    False,
                    quota.action_on_exceed,
                    f"monthly cost quota exceeded for {provider}: {cost_sum + estimated_cost_usd}/{quota.monthly_cost_limit_usd}",
                )
        return QuotaDecision(True, "", "")


def get_matching_routing_rules(analysis):
    rules = []
    for rule in RoutingRule.objects.filter(is_active=True):
        if routing_rule_matches(rule.condition_key, analysis):
            rules.append(rule)
    return rules


def get_matching_threshold_rules(analysis):
    rules = []
    for rule in ThresholdRule.objects.filter(is_active=True):
        if threshold_rule_matches(rule, analysis):
            rules.append(rule)
    return rules


def get_matching_validation_rules(analysis):
    rules = []
    for rule in ResponseValidationRule.objects.filter(is_active=True):
        if routing_rule_matches(rule.condition_key, analysis):
            rules.append(rule)
    return rules


def routing_rule_matches(condition_key: str, analysis) -> bool:
    if condition_key == "always":
        return True
    if condition_key == "sensitive":
        return analysis.has_sensitive_data
    if condition_key == "code":
        return analysis.is_code
    if condition_key == "structured_output":
        return analysis.is_structured_output
    if condition_key == "long_context":
        return analysis.is_long_context
    if condition_key == "reasoning":
        return analysis.requires_reasoning
    if condition_key == "general":
        return not (
            analysis.has_sensitive_data
            or analysis.is_code
            or analysis.is_structured_output
            or analysis.is_long_context
            or analysis.requires_reasoning
        )
    return False


def threshold_rule_matches(rule: ThresholdRule, analysis) -> bool:
    if rule.metric_key != "estimated_tokens":
        return False
    current_value = Decimal(analysis.estimated_tokens)
    if rule.operator == "gte":
        return current_value >= rule.threshold_value
    if rule.operator == "lte":
        return current_value <= rule.threshold_value
    return False


def validate_response_text(response_text: str, validation_type: str) -> ValidationDecision:
    if validation_type == "non_empty":
        if response_text.strip():
            return ValidationDecision(True, "passed", "")
        return ValidationDecision(False, "failed", "response is empty")
    if validation_type == "json":
        candidate = extract_json_candidate(response_text)
        try:
            json.loads(candidate)
            return ValidationDecision(True, "passed", "")
        except ValueError as exc:
            return ValidationDecision(False, "failed", f"invalid JSON: {exc}")
    if validation_type == "sql":
        normalized = response_text.strip().strip(";").lower()
        if re.match(r"^(select|with|insert|update|delete)\b", normalized):
            return ValidationDecision(True, "passed", "")
        return ValidationDecision(False, "failed", "SQL must start with SELECT, WITH, INSERT, UPDATE, or DELETE")
    return ValidationDecision(True, "not_required", "")


def extract_json_candidate(response_text: str) -> str:
    stripped = response_text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return stripped


def get_recovery_action(validation_rule: Optional[ResponseValidationRule]) -> str:
    if validation_rule and validation_rule.recovery_strategy and validation_rule.recovery_strategy.is_active:
        return validation_rule.recovery_strategy.action
    return validation_rule.action_on_fail if validation_rule else "fallback"


def get_recovery_max_retries(validation_rule: Optional[ResponseValidationRule]) -> int:
    if validation_rule and validation_rule.recovery_strategy and validation_rule.recovery_strategy.is_active:
        return validation_rule.recovery_strategy.max_retries
    return validation_rule.max_retries if validation_rule else 0


def get_recovery_target_tier(validation_rule: Optional[ResponseValidationRule]) -> str:
    if validation_rule and validation_rule.recovery_strategy and validation_rule.recovery_strategy.is_active:
        return validation_rule.recovery_strategy.target_tier
    return validation_rule.target_tier if validation_rule else ""


def build_retry_prompt(prompt: str, validation_rule: Optional[ResponseValidationRule]) -> str:
    instruction = ""
    if validation_rule and validation_rule.recovery_strategy and validation_rule.recovery_strategy.is_active:
        instruction = validation_rule.recovery_strategy.retry_prompt.strip()
    if not instruction and validation_rule:
        instruction = validation_rule.retry_prompt.strip()
    if not instruction:
        instruction = "Fix the previous response so it passes the required output validation."
    return f"{prompt}\n\nValidation instruction: {instruction}"


def build_policy_config(base_config: dict, matched_rules: list[RoutingRule], matched_threshold_rules: list[ThresholdRule]) -> dict:
    policy_config = dict(base_config or {})
    threshold_tiers = [
        rule.target_tier
        for rule in matched_threshold_rules
        if rule.action_on_trigger == "prefer_tier" and rule.target_tier
    ]
    routing_tiers = [rule.target_tier for rule in matched_rules]
    if threshold_tiers:
        policy_config["preferred_model_tiers"] = threshold_tiers
    elif routing_tiers:
        policy_config["preferred_model_tiers"] = routing_tiers
    max_token_limits = [
        rule.max_tokens
        for rule in matched_threshold_rules
        if rule.action_on_trigger == "set_max_tokens" and rule.max_tokens is not None
    ]
    if max_token_limits:
        policy_config["max_tokens"] = min(max_token_limits)
    return policy_config


def serialize_matched_rules(matched_rules: list[RoutingRule]) -> list[dict]:
    return [
        {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "condition_key": rule.condition_key,
            "target_tier": rule.target_tier,
            "priority": rule.priority,
        }
        for rule in matched_rules
    ]


def serialize_matched_threshold_rules(matched_rules: list[ThresholdRule]) -> list[dict]:
    return [
        {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "metric_key": rule.metric_key,
            "operator": rule.operator,
            "threshold_value": rule.threshold_value,
            "action_on_trigger": rule.action_on_trigger,
            "target_tier": rule.target_tier,
            "max_tokens": rule.max_tokens,
            "priority": rule.priority,
        }
        for rule in matched_rules
    ]


def serialize_matched_validation_rules(matched_rules: list[ResponseValidationRule]) -> list[dict]:
    return [
        {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "condition_key": rule.condition_key,
            "validation_type": rule.validation_type,
            "action_on_fail": rule.action_on_fail,
            "recovery_strategy": rule.recovery_strategy_id,
            "recovery_strategy_display_name": rule.recovery_strategy.name if rule.recovery_strategy else None,
            "max_retries": rule.max_retries,
            "target_tier": rule.target_tier,
            "priority": rule.priority,
        }
        for rule in matched_rules
    ]
