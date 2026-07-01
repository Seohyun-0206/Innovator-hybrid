from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Avg, Q
from django.utils import timezone

from apps.catalog.models import ModelHealthEvent, ModelHealthOverride, ModelHealthRule
from apps.logs.models import RoutingLog


@dataclass(frozen=True)
class ModelHealthStatus:
    provider: str
    model_name: str
    status: str
    reason: str
    rule_id: Optional[int]
    rule_name: str
    request_count: int
    failures: int
    failure_rate: Decimal
    average_latency_ms: int
    window_minutes: Optional[int]


def evaluate_model_health(*, provider: str, model_name: str, record_event: bool = False) -> ModelHealthStatus:
    override_status = get_manual_override_status(provider=provider, model_name=model_name)
    if override_status is not None:
        if record_event:
            record_health_transition(override_status)
        return override_status

    rules = ModelHealthRule.objects.filter(is_active=True).filter(
        Q(provider="") | Q(provider=provider),
        Q(model_name="") | Q(model_name=model_name),
    )
    if not rules.exists():
        status = healthy_status(provider=provider, model_name=model_name)
        if record_event:
            record_health_transition(status)
        return status

    now = timezone.now()
    latest_status = healthy_status(provider=provider, model_name=model_name)
    for rule in rules:
        window_start = now - timedelta(minutes=rule.window_minutes)
        logs = RoutingLog.objects.filter(
            created_at__gte=window_start,
            selected_provider=provider,
            selected_model=model_name,
        )
        request_count = logs.count()
        if request_count < rule.min_requests:
            latest_status = ModelHealthStatus(
                provider=provider,
                model_name=model_name,
                status="healthy",
                reason=f"not enough samples for '{rule.name}': {request_count}/{rule.min_requests}",
                rule_id=rule.id,
                rule_name=rule.name,
                request_count=request_count,
                failures=logs.exclude(error_message="").count(),
                failure_rate=Decimal("0"),
                average_latency_ms=int(logs.aggregate(value=Avg("latency_ms"))["value"] or 0),
                window_minutes=rule.window_minutes,
            )
            continue

        failures = logs.exclude(error_message="").count()
        failure_rate = (Decimal(failures) / Decimal(request_count)) * Decimal("100")
        average_latency = int(logs.aggregate(value=Avg("latency_ms"))["value"] or 0)

        if rule.max_failure_rate_percent is not None and failure_rate >= rule.max_failure_rate_percent:
            status = ModelHealthStatus(
                provider=provider,
                model_name=model_name,
                status="unhealthy",
                reason=f"health rule '{rule.name}' triggered: failure rate {failure_rate:.2f}% >= {rule.max_failure_rate_percent}%",
                rule_id=rule.id,
                rule_name=rule.name,
                request_count=request_count,
                failures=failures,
                failure_rate=failure_rate,
                average_latency_ms=average_latency,
                window_minutes=rule.window_minutes,
            )
            if record_event:
                record_health_transition(status)
            return status
        if rule.max_average_latency_ms is not None and average_latency >= rule.max_average_latency_ms:
            status = ModelHealthStatus(
                provider=provider,
                model_name=model_name,
                status="unhealthy",
                reason=f"health rule '{rule.name}' triggered: average latency {average_latency}ms >= {rule.max_average_latency_ms}ms",
                rule_id=rule.id,
                rule_name=rule.name,
                request_count=request_count,
                failures=failures,
                failure_rate=failure_rate,
                average_latency_ms=average_latency,
                window_minutes=rule.window_minutes,
            )
            if record_event:
                record_health_transition(status)
            return status
        latest_status = ModelHealthStatus(
            provider=provider,
            model_name=model_name,
            status="healthy",
            reason=f"health rule '{rule.name}' within thresholds",
            rule_id=rule.id,
            rule_name=rule.name,
            request_count=request_count,
            failures=failures,
            failure_rate=failure_rate,
            average_latency_ms=average_latency,
            window_minutes=rule.window_minutes,
        )
    if record_event:
        record_health_transition(latest_status)
    return latest_status


def healthy_status(*, provider: str, model_name: str) -> ModelHealthStatus:
    return ModelHealthStatus(
        provider=provider,
        model_name=model_name,
        status="healthy",
        reason="no active health rule matched",
        rule_id=None,
        rule_name="",
        request_count=0,
        failures=0,
        failure_rate=Decimal("0"),
        average_latency_ms=0,
        window_minutes=None,
    )


def get_manual_override_status(*, provider: str, model_name: str) -> Optional[ModelHealthStatus]:
    now = timezone.now()
    override = (
        ModelHealthOverride.objects.filter(is_active=True)
        .filter(Q(provider="") | Q(provider=provider), Q(model_name="") | Q(model_name=model_name))
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-created_at")
        .first()
    )
    if override is None:
        return None

    status = "healthy" if override.override_type == "force_healthy" else "unhealthy"
    action_label = "forced healthy" if status == "healthy" else "forced unhealthy"
    reason = f"manual override '{override.name}' {action_label}"
    if override.reason:
        reason = f"{reason}: {override.reason}"
    return ModelHealthStatus(
        provider=provider,
        model_name=model_name,
        status=status,
        reason=reason,
        rule_id=None,
        rule_name="manual override",
        request_count=0,
        failures=0,
        failure_rate=Decimal("0"),
        average_latency_ms=0,
        window_minutes=None,
    )


def serialize_model_health_status(status: ModelHealthStatus) -> dict:
    return {
        "provider": status.provider,
        "model_name": status.model_name,
        "status": status.status,
        "reason": status.reason,
        "rule_id": status.rule_id,
        "rule_name": status.rule_name,
        "request_count": status.request_count,
        "failures": status.failures,
        "failure_rate": round(float(status.failure_rate) / 100, 4),
        "average_latency_ms": status.average_latency_ms,
        "window_minutes": status.window_minutes,
    }


def record_health_transition(status: ModelHealthStatus):
    last_event = ModelHealthEvent.objects.filter(
        provider=status.provider,
        model_name=status.model_name,
    ).first()

    if last_event and last_event.status == status.status:
        return None
    if status.status == "healthy" and not last_event:
        return None

    event_type = "triggered" if status.status == "unhealthy" else "recovered"
    return ModelHealthEvent.objects.create(
        event_type=event_type,
        provider=status.provider,
        model_name=status.model_name,
        status=status.status,
        rule_id=status.rule_id,
        rule_name=status.rule_name,
        reason=status.reason,
        request_count=status.request_count,
        failures=status.failures,
        failure_rate=(status.failure_rate / Decimal("100")),
        average_latency_ms=status.average_latency_ms,
    )
