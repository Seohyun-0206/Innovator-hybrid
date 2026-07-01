from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0013_seed_default_response_validation_rules"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecoveryStrategy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("strategy_id", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "trigger_event",
                    models.CharField(
                        choices=[
                            ("validation_fail", "Validation failure"),
                            ("timeout", "Timeout"),
                            ("api_fail", "API failure"),
                            ("parse_fail", "Parse failure"),
                            ("low_confidence", "Low confidence"),
                        ],
                        default="validation_fail",
                        max_length=32,
                    ),
                ),
                (
                    "action",
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
                "ordering": ["priority", "strategy_id"],
            },
        ),
        migrations.AddField(
            model_name="responsevalidationrule",
            name="recovery_strategy",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="validation_rules",
                to="catalog.recoverystrategy",
            ),
        ),
    ]
