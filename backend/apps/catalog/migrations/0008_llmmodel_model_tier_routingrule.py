from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_modelhealthrule"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmmodel",
            name="model_tier",
            field=models.CharField(
                choices=[
                    ("lightweight", "Lightweight"),
                    ("standard", "Standard"),
                    ("advanced", "Advanced"),
                    ("long_context", "Long Context"),
                    ("structured", "Structured"),
                ],
                default="standard",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="RoutingRule",
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
                        default="general",
                        max_length=32,
                    ),
                ),
                (
                    "target_tier",
                    models.CharField(
                        choices=[
                            ("lightweight", "Lightweight"),
                            ("standard", "Standard"),
                            ("advanced", "Advanced"),
                            ("long_context", "Long Context"),
                            ("structured", "Structured"),
                        ],
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
