from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_usagequota"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelHealthRule",
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
                ("window_minutes", models.PositiveIntegerField(default=60)),
                ("min_requests", models.PositiveIntegerField(default=5)),
                ("max_failure_rate_percent", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("max_average_latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "action_on_trigger",
                    models.CharField(choices=[("exclude", "Exclude from routing")], default="exclude", max_length=32),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
