from django.db import migrations, models
import django.db.models.deletion


def seed_mmlu_method(apps, schema_editor):
    EvaluationMethod = apps.get_model("catalog", "EvaluationMethod")
    EvaluationMethod.objects.update_or_create(
        name="mmlu_multiple_choice",
        defaults={
            "display_name": "MMLU 객관식 평가",
            "method_type": "multiple_choice",
            "description": "A/B/C/D 객관식 정답 추출, strict 응답 준수율, 정확도, 지연, 토큰, 비용을 함께 집계합니다.",
            "compatible_dataset_types": ["mmlu", "custom_mcq", "jsonl", "csv"],
            "default_config": {
                "seed": 42,
                "total_questions": 20,
                "few_shot": 0,
                "temperature": 0,
                "max_tokens": 8,
                "timeout_seconds": 120,
                "retry": 0,
            },
            "metric_schema": {
                "overall_accuracy": "0..1",
                "strict_compliance_rate": "0..1",
                "failure_rate": "0..1",
                "parse_failure_rate": "0..1",
                "latency_p50_ms": "milliseconds",
                "latency_p95_ms": "milliseconds",
                "input_tokens": "count",
                "output_tokens": "count",
                "estimated_cost_usd": "usd",
                "scorecard": ["performance_score", "efficiency_score", "capability_score", "total_score"],
            },
            "artifact_schema": {
                "eval_manifest": "run/dataset/method/config metadata",
                "model_summary": "aggregated result metrics",
                "scorecard": "routing-oriented score card",
                "jsonl_like_logs": "per-item execution logs",
                "report_markdown": "human-readable report",
            },
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0023_evaluation_dataset_run_result"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvaluationMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.SlugField(max_length=80, unique=True)),
                ("display_name", models.CharField(max_length=160)),
                (
                    "method_type",
                    models.CharField(
                        choices=[
                            ("multiple_choice", "Multiple Choice"),
                            ("generation", "Generation"),
                            ("retrieval", "Retrieval"),
                            ("custom", "Custom"),
                        ],
                        default="multiple_choice",
                        max_length=32,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("compatible_dataset_types", models.JSONField(blank=True, default=list)),
                ("default_config", models.JSONField(blank=True, default=dict)),
                ("metric_schema", models.JSONField(blank=True, default=dict)),
                ("artifact_schema", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["display_name", "name"]},
        ),
        migrations.AddField(
            model_name="evaluationrun",
            name="evaluation_method",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="runs",
                to="catalog.evaluationmethod",
            ),
        ),
        migrations.CreateModel(
            name="EvaluationItemResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("item_index", models.PositiveIntegerField(default=0)),
                ("question", models.TextField()),
                ("choices", models.JSONField(blank=True, default=list)),
                ("gold", models.CharField(blank=True, max_length=16)),
                ("predicted_choice", models.CharField(blank=True, max_length=16)),
                ("strict_ok", models.BooleanField(default=False)),
                ("is_correct", models.BooleanField(default=False)),
                ("ok", models.BooleanField(default=False)),
                ("attempt", models.PositiveIntegerField(default=1)),
                ("error", models.TextField(blank=True)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("raw_output", models.TextField(blank=True)),
                ("subject", models.CharField(blank=True, max_length=160)),
                ("category", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "dataset",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="item_results", to="catalog.evaluationdataset"),
                ),
                (
                    "model",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evaluation_item_results", to="catalog.llmmodel"),
                ),
                (
                    "result",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="item_results", to="catalog.evaluationresult"),
                ),
                (
                    "run",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="item_results", to="catalog.evaluationrun"),
                ),
            ],
            options={"ordering": ["result_id", "item_index", "attempt"]},
        ),
        migrations.AddIndex(
            model_name="evaluationitemresult",
            index=models.Index(fields=["run", "model"], name="catalog_eva_run_id_fed8de_idx"),
        ),
        migrations.AddIndex(
            model_name="evaluationitemresult",
            index=models.Index(fields=["result", "item_index"], name="catalog_eva_result__45eea1_idx"),
        ),
        migrations.RunPython(seed_mmlu_method, migrations.RunPython.noop),
    ]
