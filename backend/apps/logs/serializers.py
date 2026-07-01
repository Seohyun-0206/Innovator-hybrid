from rest_framework import serializers

from apps.logs.models import RoutingLog


class RoutingLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True, allow_null=True)

    class Meta:
        model = RoutingLog
        fields = [
            "id",
            "username",
            "prompt_summary",
            "policy",
            "selected_provider",
            "selected_model",
            "routing_reason",
            "latency_ms",
            "estimated_tokens",
            "estimated_cost_usd",
            "response_text",
            "error_message",
            "validation_status",
            "validation_errors",
            "created_at",
        ]
