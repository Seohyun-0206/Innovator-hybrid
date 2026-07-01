from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0016_modelhealthevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelHealthOverride",
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
                ("model_name", models.CharField(blank=True, default="", max_length=120)),
                (
                    "override_type",
                    models.CharField(
                        choices=[("force_healthy", "Force healthy"), ("force_unhealthy", "Force unhealthy")],
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField(blank=True, default="")),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="model_health_overrides",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
