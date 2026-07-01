from django.db import models
from django.conf import settings


class RoutingLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="routing_logs",
    )
    prompt_summary = models.CharField(max_length=240)
    policy = models.CharField(max_length=64)
    selected_provider = models.CharField(max_length=32)
    selected_model = models.CharField(max_length=120)
    routing_reason = models.TextField()
    latency_ms = models.PositiveIntegerField()
    estimated_tokens = models.PositiveIntegerField()
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    response_text = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    validation_status = models.CharField(max_length=32, blank=True, default="")
    validation_errors = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.policy} -> {self.selected_provider}/{self.selected_model}"
