from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_seed_default_routing_rules"),
    ]

    operations = [
        migrations.CreateModel(
            name="ThresholdRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_id", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "metric_key",
                    models.CharField(
                        choices=[
                            ("estimated_tokens", "Estimated tokens"),
                            ("p95_latency_ms", "p95 latency ms"),
                            ("timeout_seconds", "Timeout seconds"),
                            ("parse_fail_rate", "Parse fail rate"),
                            ("failure_rate", "Failure rate"),
                        ],
                        default="estimated_tokens",
                        max_length=32,
                    ),
                ),
                ("operator", models.CharField(choices=[("gte", ">="), ("lte", "<=")], default="gte", max_length=8)),
                ("threshold_value", models.DecimalField(decimal_places=4, max_digits=12)),
                (
                    "action_on_trigger",
                    models.CharField(
                        choices=[("prefer_tier", "Prefer model tier"), ("set_max_tokens", "Set max tokens")],
                        default="prefer_tier",
                        max_length=32,
                    ),
                ),
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
                ("max_tokens", models.PositiveIntegerField(blank=True, null=True)),
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
