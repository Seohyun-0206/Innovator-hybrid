from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_model_cost_performance_metadata"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UsageQuota",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                (
                    "provider",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "All providers"),
                            ("ollama", "Ollama"),
                            ("openai", "OpenAI"),
                            ("gemini", "Gemini"),
                            ("openrouter", "OpenRouter"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("monthly_request_limit", models.PositiveIntegerField(blank=True, null=True)),
                ("monthly_cost_limit_usd", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                (
                    "action_on_exceed",
                    models.CharField(
                        choices=[("block", "Block request"), ("local_fallback", "Fallback to local")],
                        default="local_fallback",
                        max_length=32,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_quotas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
    ]
