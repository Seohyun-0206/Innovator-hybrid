import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0019_add_ollama_provider_credentials"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceFeature",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("required_tier", models.CharField(
                    choices=[("lightweight", "Lightweight"), ("standard", "Standard"), ("advanced", "Advanced"), ("long_context", "Long Context"), ("structured", "Structured")],
                    default="standard", max_length=32,
                )),
                ("routing_path", models.CharField(
                    choices=[("lightweight", "Lightweight Path"), ("standard", "Standard Path"), ("advanced", "Advanced Path"), ("long_context", "Long Context Path"), ("structured", "Structured Path"), ("escalation", "Escalation Path"), ("fallback", "Fallback Path")],
                    default="standard", max_length=32,
                )),
                ("condition_key", models.CharField(
                    choices=[("general", "General/simple query"), ("code", "Code or technical request"), ("reasoning", "Reasoning request"), ("long_context", "Long context request"), ("structured_output", "SQL/JSON structured output"), ("sensitive", "Sensitive data request"), ("always", "Always")],
                    default="general", max_length=32,
                )),
                ("main_metrics", models.JSONField(blank=True, default=list)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="PolicyDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("preset", models.CharField(
                    choices=[("cost-first", "Cost First"), ("quality-first", "Quality First"), ("balanced", "Balanced"), ("privacy-first", "Privacy First")],
                    default="balanced", max_length=32,
                )),
                ("selected_model_ids", models.JSONField(default=list)),
                ("tier_assignments", models.JSONField(default=dict)),
                ("feature_model_map", models.JSONField(default=dict)),
                ("routing_rules", models.JSONField(default=list)),
                ("threshold_rules", models.JSONField(default=list)),
                ("validation_rules", models.JSONField(default=list)),
                ("recovery_strategies", models.JSONField(default=list)),
                ("summary_text", models.TextField(blank=True)),
                ("missing_coverage", models.JSONField(default=list)),
                ("is_saved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="policy_drafts",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
