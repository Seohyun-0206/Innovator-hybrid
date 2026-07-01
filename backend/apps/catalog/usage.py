from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.logs.models import RoutingLog


def current_month_start():
    return timezone.make_aware(datetime.combine(timezone.localdate().replace(day=1), datetime.min.time()))


def get_quota_usage(quota):
    month_start = current_month_start()
    usage = RoutingLog.objects.filter(created_at__gte=month_start)
    if quota.user_id is not None:
        usage = usage.filter(user_id=quota.user_id)
    if quota.provider:
        usage = usage.filter(selected_provider=quota.provider)

    request_count = usage.count()
    cost_sum = usage.aggregate(value=Sum("estimated_cost_usd"))["value"] or Decimal("0")
    request_ratio = None
    cost_ratio = None
    if quota.monthly_request_limit:
        request_ratio = min(Decimal(request_count) / Decimal(quota.monthly_request_limit), Decimal("1"))
    if quota.monthly_cost_limit_usd:
        cost_ratio = min(cost_sum / quota.monthly_cost_limit_usd, Decimal("1"))

    request_exceeded = quota.monthly_request_limit is not None and request_count >= quota.monthly_request_limit
    cost_exceeded = quota.monthly_cost_limit_usd is not None and cost_sum >= quota.monthly_cost_limit_usd
    return {
        "period_start": month_start.date().isoformat(),
        "current_month_requests": request_count,
        "current_month_cost_usd": cost_sum,
        "request_usage_ratio": request_ratio,
        "cost_usage_ratio": cost_ratio,
        "is_exceeded": request_exceeded or cost_exceeded,
    }
