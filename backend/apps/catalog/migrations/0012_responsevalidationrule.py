from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0011_seed_default_threshold_rules"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResponseValidationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_id", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "condition_key",
                    models.CharField(
                        choices=[
                            ("general", "General/simple query"),
                            ("code", "Code or technical request"),
                            ("reasoning", "Reasoning request"),
                            ("long_context", "Long context request"),
                            ("structured_output", "SQL/JSON structured output"),
                            ("sensitive", "Sensitive data request"),
                            ("always", "Always"),
                        ],
                        default="structured_output",
                        max_length=32,
                    ),
                ),
                (
                    "validation_type",
                    models.CharField(
                        choices=[
                            ("non_empty", "Non-empty response"),
                            ("json", "JSON parse validation"),
                            ("sql", "SQL format validation"),
                        ],
                        default="json",
                        max_length=32,
                    ),
                ),
                (
                    "action_on_fail",
                    models.CharField(
                        choices=[
                            ("strict_retry", "Strict retry"),
                            ("fallback", "Fallback"),
                            ("escalate", "Escalate to tier"),
                            ("block", "Block response"),
                        ],
                        default="strict_retry",
                        max_length=32,
                    ),
                ),
                ("retry_prompt", models.TextField(blank=True)),
                ("max_retries", models.PositiveIntegerField(default=1)),
                (
                    "target_tier",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("lightweight", "Lightweight"),
                            ("standard", "Standard"),
                            ("advanced", "Advanced"),
                            ("long_context", "Long Context"),
                            ("structured", "Structured"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("priority", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["priority", "rule_id"],
            },
        ),
    ]
