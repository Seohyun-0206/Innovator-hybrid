from django.db import migrations, models


def infer_format(dataset, legacy_type):
    filename = (dataset.original_filename or "").lower()
    if filename.endswith(".csv"):
        return "csv"
    if filename.endswith(".jsonl"):
        return "jsonl"
    if filename.endswith(".json"):
        return "json"
    if filename.endswith(".txt"):
        return "txt"
    if legacy_type in {"jsonl", "csv"}:
        return legacy_type
    return "jsonl"


def backfill_dataset_metadata(apps, schema_editor):
    EvaluationDataset = apps.get_model("catalog", "EvaluationDataset")
    EvaluationMethod = apps.get_model("catalog", "EvaluationMethod")
    legacy_map = {
        "mmlu": ("multiple_choice", "mmlu"),
        "custom_mcq": ("multiple_choice", "custom"),
        "jsonl": ("multiple_choice", "custom"),
        "csv": ("multiple_choice", "custom"),
    }
    for dataset in EvaluationDataset.objects.all():
        legacy_type = dataset.dataset_type
        next_type, next_family = legacy_map.get(
            legacy_type,
            (dataset.dataset_type or "multiple_choice", dataset.dataset_family or "custom"),
        )
        dataset.dataset_type = next_type
        dataset.dataset_family = next_family if legacy_type in legacy_map else dataset.dataset_family or next_family
        dataset.data_format = infer_format(dataset, legacy_type)
        dataset.save(update_fields=["dataset_type", "dataset_family", "data_format", "updated_at"])

    method = EvaluationMethod.objects.filter(name="mmlu_multiple_choice").first()
    if method:
        compatible_types = set(method.compatible_dataset_types or [])
        compatible_types.update({"multiple_choice", "mmlu", "custom_mcq", "jsonl", "csv"})
        method.compatible_dataset_types = sorted(compatible_types)
        method.save(update_fields=["compatible_dataset_types", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0024_evaluation_method_item_results"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evaluationdataset",
            name="dataset_type",
            field=models.CharField(
                choices=[
                    ("multiple_choice", "Multiple Choice"),
                    ("qa", "Question Answering"),
                    ("generation", "Generation/Summarization"),
                    ("rag", "Retrieval-Augmented Generation"),
                    ("safety_classification", "Safety/Classification"),
                    ("custom", "Custom"),
                    ("mmlu", "MMLU (legacy)"),
                    ("custom_mcq", "Custom Multiple Choice (legacy)"),
                    ("jsonl", "JSONL (legacy)"),
                    ("csv", "CSV (legacy)"),
                ],
                default="multiple_choice",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="evaluationdataset",
            name="dataset_family",
            field=models.CharField(
                choices=[
                    ("mmlu", "MMLU"),
                    ("custom", "Custom"),
                    ("humaneval", "HumanEval"),
                    ("gsm8k", "GSM8K"),
                    ("other", "Other"),
                ],
                default="custom",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="evaluationdataset",
            name="data_format",
            field=models.CharField(
                choices=[
                    ("jsonl", "JSONL"),
                    ("csv", "CSV"),
                    ("json", "JSON"),
                    ("txt", "TXT"),
                    ("unknown", "Unknown"),
                ],
                default="jsonl",
                max_length=32,
            ),
        ),
        migrations.RunPython(backfill_dataset_metadata, migrations.RunPython.noop),
    ]
