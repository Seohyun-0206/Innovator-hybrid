from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0022_seed_pdf_routing_data"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EvaluationDataset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                (
                    "dataset_type",
                    models.CharField(
                        choices=[
                            ("mmlu", "MMLU"),
                            ("custom_mcq", "Custom Multiple Choice"),
                            ("jsonl", "JSONL"),
                            ("csv", "CSV"),
                        ],
                        default="mmlu",
                        max_length=32,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("upload", "Upload"), ("url", "URL"), ("huggingface", "Hugging Face")],
                        default="url",
                        max_length=32,
                    ),
                ),
                ("source_url", models.URLField(blank=True)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("raw_content", models.TextField(blank=True)),
                ("question_count", models.PositiveIntegerField(default=0)),
                ("category_schema", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evaluation_datasets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "name"]},
        ),
        migrations.CreateModel(
            name="EvaluationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evaluation_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dataset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="catalog.evaluationdataset",
                    ),
                ),
                ("models", models.ManyToManyField(related_name="evaluation_runs", to="catalog.llmmodel")),
            ],
            options={"ordering": ["-created_at", "name"]},
        ),
        migrations.CreateModel(
            name="EvaluationResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("overall_accuracy", models.DecimalField(blank=True, decimal_places=4, max_digits=6, null=True)),
                ("strict_compliance_rate", models.DecimalField(blank=True, decimal_places=4, max_digits=6, null=True)),
                ("failure_rate", models.DecimalField(blank=True, decimal_places=4, max_digits=6, null=True)),
                ("parse_failure_rate", models.DecimalField(blank=True, decimal_places=4, max_digits=6, null=True)),
                ("latency_p50_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("latency_p95_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("estimated_cost_usd", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("category_accuracy", models.JSONField(blank=True, default=dict)),
                ("subject_accuracy", models.JSONField(blank=True, default=dict)),
                ("scorecard", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "dataset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="catalog.evaluationdataset",
                    ),
                ),
                (
                    "model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluation_results",
                        to="catalog.llmmodel",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="catalog.evaluationrun",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("run", "model")}},
        ),
    ]
