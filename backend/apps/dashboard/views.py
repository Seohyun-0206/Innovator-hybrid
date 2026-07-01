from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasScreenAccess
from apps.catalog.connectivity import check_models_connectivity, check_ollama_status
from apps.catalog.health import evaluate_model_health, serialize_model_health_status
from apps.catalog.models import EvaluationResult, EvaluationRun, LLMModel, ModelHealthEvent
from apps.logs.models import RoutingLog
from apps.logs.serializers import RoutingLogSerializer


class DashboardMetricsView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "dashboard"

    def get_filtered_logs(self, request):
        logs = RoutingLog.objects.select_related("user").all()
        period = request.query_params.get("period", "7d")
        today = timezone.localdate()
        start_date = None
        end_date = None

        if period == "today":
            start_date = today
            end_date = today
        elif period == "30d":
            start_date = today - timedelta(days=29)
            end_date = today
        elif period == "custom":
            start_date = parse_date(request.query_params.get("start_date", ""))
            end_date = parse_date(request.query_params.get("end_date", ""))
        elif period == "all":
            return logs, {"period": period, "start_date": None, "end_date": None}
        else:
            period = "7d"
            start_date = today - timedelta(days=6)
            end_date = today

        if start_date:
            start_at = timezone.make_aware(
                datetime.combine(start_date, time.min)
            )
            logs = logs.filter(created_at__gte=start_at)
        if end_date:
            end_at = timezone.make_aware(
                datetime.combine(end_date + timedelta(days=1), time.min)
            )
            logs = logs.filter(created_at__lt=end_at)

        return logs, {
            "period": period,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }

    def get_filtered_runs(self, active_filter):
        runs = EvaluationRun.objects.select_related("dataset", "evaluation_method").all()
        start_date = active_filter.get("start_date")
        end_date = active_filter.get("end_date")
        if start_date:
            start_at = timezone.make_aware(datetime.combine(parse_date(start_date), time.min))
            runs = runs.filter(created_at__gte=start_at)
        if end_date:
            end_at = timezone.make_aware(datetime.combine(parse_date(end_date) + timedelta(days=1), time.min))
            runs = runs.filter(created_at__lt=end_at)
        return runs

    def build_experiment_metrics(self, active_filter):
        runs = self.get_filtered_runs(active_filter)
        run_ids = list(runs.values_list("id", flat=True))
        results = EvaluationResult.objects.select_related("model", "run", "dataset").filter(run_id__in=run_ids)
        completed_results = results.filter(status="completed")
        completed_runs = runs.filter(status="completed")

        avg_accuracy = completed_results.aggregate(value=Avg("overall_accuracy"))["value"]
        avg_latency = completed_results.aggregate(value=Avg("latency_p95_ms"))["value"]
        total_cost = completed_results.aggregate(value=Sum("estimated_cost_usd"))["value"] or 0
        avg_failure_rate = completed_results.aggregate(value=Avg("failure_rate"))["value"]

        model_performance = list(
            completed_results.values("model__provider", "model__name", "model__display_name")
            .annotate(
                result_count=Count("id"),
                average_accuracy=Avg("overall_accuracy"),
                average_latency_p95_ms=Avg("latency_p95_ms"),
                total_estimated_cost_usd=Sum("estimated_cost_usd"),
            )
            .order_by("-result_count")
        )
        for item in model_performance:
            item["average_accuracy"] = float(item["average_accuracy"] or 0)
            item["average_latency_p95_ms"] = round(item["average_latency_p95_ms"] or 0)
            item["total_estimated_cost_usd"] = item["total_estimated_cost_usd"] or 0

        recent_completed_runs = []
        for run in completed_runs.order_by("-completed_at", "-updated_at")[:5]:
            run_results = completed_results.filter(run_id=run.id)
            run_accuracy = run_results.aggregate(value=Avg("overall_accuracy"))["value"]
            run_latency = run_results.aggregate(value=Avg("latency_p95_ms"))["value"]
            recent_completed_runs.append(
                {
                    "id": run.id,
                    "name": run.name,
                    "dataset_name": run.dataset.name,
                    "evaluation_method_name": run.evaluation_method.display_name if run.evaluation_method else "",
                    "result_count": run_results.count(),
                    "average_accuracy": float(run_accuracy or 0),
                    "average_latency_p95_ms": round(run_latency or 0),
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
            )

        active_models = list(LLMModel.objects.filter(is_active=True).select_related("provider_credential"))
        connectivity = check_models_connectivity(active_models)
        ollama_models = [item for item in connectivity if item["provider"] == "ollama"]
        ollama_status = check_ollama_status()
        for item in ollama_models:
            item["installed"] = item["model"] in ollama_status["installed_models"]

        return {
            "runs": {
                "total": runs.count(),
                "completed": runs.filter(status="completed").count(),
                "running": runs.filter(status="running").count(),
                "failed": runs.filter(status="failed").count(),
                "pending": runs.filter(status="pending").count(),
            },
            "results": {
                "completed_count": completed_results.count(),
                "average_accuracy": float(avg_accuracy or 0),
                "average_latency_p95_ms": round(avg_latency or 0),
                "average_failure_rate": float(avg_failure_rate or 0),
                "total_estimated_cost_usd": total_cost,
            },
            "model_performance": model_performance,
            "recent_completed_runs": recent_completed_runs,
            "model_connectivity": connectivity,
            "connectivity_summary": {
                "online": sum(1 for item in connectivity if item["status"] == "online"),
                "offline": sum(1 for item in connectivity if item["status"] == "offline"),
                "error": sum(1 for item in connectivity if item["status"] == "error"),
                "skipped": sum(1 for item in connectivity if item["status"] == "skipped"),
            },
            "ollama_status": {
                **ollama_status,
                "registered_models": ollama_models,
            },
        }

    def get(self, request):
        logs, active_filter = self.get_filtered_logs(request)
        total_requests = logs.count()
        average_latency = logs.aggregate(value=Avg("latency_ms"))["value"] or 0
        total_estimated_cost = logs.aggregate(value=Sum("estimated_cost_usd"))["value"] or 0
        model_usage = list(
            logs.values("selected_provider", "selected_model")
            .annotate(count=Count("id"), estimated_cost_usd=Sum("estimated_cost_usd"))
            .order_by("-count")
        )
        provider_usage = list(
            logs.values("selected_provider")
            .annotate(count=Count("id"), estimated_cost_usd=Sum("estimated_cost_usd"))
            .order_by("-count")
        )
        user_usage = list(
            logs.values("user__username")
            .annotate(count=Count("id"), estimated_cost_usd=Sum("estimated_cost_usd"))
            .order_by("-count")
        )
        policy_usage = list(
            logs.values("policy")
            .annotate(count=Count("id"), estimated_cost_usd=Sum("estimated_cost_usd"))
            .order_by("-count")
        )
        failed_requests = logs.exclude(error_message="").count()
        fallback_attempts = logs.filter(routing_reason__icontains="fallback attempts").count()
        quota_blocks = logs.filter(error_message__icontains="quota").count()
        failure_rate = (failed_requests / total_requests) if total_requests else 0
        provider_health = list(
            logs.values("selected_provider")
            .annotate(
                count=Count("id"),
                failures=Count("id", filter=~Q(error_message="")),
                average_latency_ms=Avg("latency_ms"),
            )
            .order_by("-failures", "-count")
        )
        for item in provider_health:
            item["failure_rate"] = round((item["failures"] / item["count"]) if item["count"] else 0, 4)
            item["average_latency_ms"] = round(item["average_latency_ms"] or 0, 2)
        model_health = list(
            logs.values("selected_provider", "selected_model")
            .annotate(
                count=Count("id"),
                failures=Count("id", filter=~Q(error_message="")),
                average_latency_ms=Avg("latency_ms"),
            )
            .order_by("-failures", "-count")[:10]
        )
        for item in model_health:
            item["failure_rate"] = round((item["failures"] / item["count"]) if item["count"] else 0, 4)
            item["average_latency_ms"] = round(item["average_latency_ms"] or 0, 2)
        recent_errors = list(
            logs.exclude(error_message="")
            .values(
                "id",
                "prompt_summary",
                "selected_provider",
                "selected_model",
                "error_message",
                "created_at",
            )[:5]
        )
        unhealthy_models = []
        for model in LLMModel.objects.filter(is_active=True):
            health_status = evaluate_model_health(provider=model.provider, model_name=model.name, record_event=True)
            if health_status.status == "unhealthy":
                unhealthy_models.append(serialize_model_health_status(health_status))
        recent_health_events = list(
            ModelHealthEvent.objects.values(
                "id",
                "event_type",
                "provider",
                "model_name",
                "status",
                "rule_name",
                "reason",
                "request_count",
                "failures",
                "failure_rate",
                "average_latency_ms",
                "created_at",
            )[:5]
        )
        local_requests = logs.filter(selected_provider="ollama").count()
        local_ratio = (local_requests / total_requests) if total_requests else 0
        experiment_metrics = self.build_experiment_metrics(active_filter)

        return Response(
            {
                "total_requests": total_requests,
                "average_latency_ms": round(average_latency, 2),
                "total_estimated_cost_usd": total_estimated_cost,
                "local_routing_ratio": round(local_ratio, 4),
                "estimated_cost_savings_percent": round(local_ratio * 100, 2),
                "failed_requests": failed_requests,
                "failure_rate": round(failure_rate, 4),
                "fallback_attempts": fallback_attempts,
                "quota_blocks": quota_blocks,
                "filter": active_filter,
                "model_usage": model_usage,
                "provider_usage": provider_usage,
                "user_usage": user_usage,
                "policy_usage": policy_usage,
                "provider_health": provider_health,
                "model_health": model_health,
                "unhealthy_models": unhealthy_models,
                "recent_health_events": recent_health_events,
                "recent_errors": recent_errors,
                "recent_logs": RoutingLogSerializer(logs[:5], many=True).data,
                "experiment_metrics": experiment_metrics,
            }
        )
