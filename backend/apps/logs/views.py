from rest_framework import filters, generics
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import HasScreenAccess
from apps.logs.models import RoutingLog
from apps.logs.serializers import RoutingLogSerializer


class RoutingLogPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class RoutingLogListView(generics.ListAPIView):
    queryset = RoutingLog.objects.select_related("user").all()
    serializer_class = RoutingLogSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "logs"
    pagination_class = RoutingLogPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "prompt_summary",
        "policy",
        "selected_provider",
        "selected_model",
        "routing_reason",
        "response_text",
        "error_message",
        "user__username",
    ]
    ordering_fields = [
        "created_at",
        "latency_ms",
        "estimated_tokens",
        "estimated_cost_usd",
        "policy",
        "selected_provider",
        "selected_model",
    ]
    ordering = ["-created_at"]
