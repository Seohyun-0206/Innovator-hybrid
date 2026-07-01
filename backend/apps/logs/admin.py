from django.contrib import admin

from apps.logs.models import RoutingLog


@admin.register(RoutingLog)
class RoutingLogAdmin(admin.ModelAdmin):
    list_display = ("policy", "selected_provider", "selected_model", "latency_ms", "created_at")
    list_filter = ("policy", "selected_provider", "selected_model")
    search_fields = ("prompt_summary", "routing_reason", "response_text")
