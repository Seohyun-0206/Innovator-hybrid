from django.db import migrations


def get_existing_columns(connection, table_name):
    with connection.cursor() as cursor:
        return {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }


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


def repair_dataset_metadata_columns(apps, schema_editor):
    EvaluationDataset = apps.get_model("catalog", "EvaluationDataset")
    EvaluationMethod = apps.get_model("catalog", "EvaluationMethod")
    table_name = EvaluationDataset._meta.db_table
    connection = schema_editor.connection
    if table_name not in connection.introspection.table_names():
        return

    existing_columns = get_existing_columns(connection, table_name)
    for field_name in ("dataset_family", "data_format"):
        if field_name not in existing_columns:
            schema_editor.add_field(EvaluationDataset, EvaluationDataset._meta.get_field(field_name))

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
        dataset.data_format = dataset.data_format or infer_format(dataset, legacy_type)
        dataset.save(update_fields=["dataset_type", "dataset_family", "data_format", "updated_at"])

    method = EvaluationMethod.objects.filter(name="mmlu_multiple_choice").first()
    if method:
        compatible_types = set(method.compatible_dataset_types or [])
        compatible_types.update({"multiple_choice", "mmlu", "custom_mcq", "jsonl", "csv"})
        method.compatible_dataset_types = sorted(compatible_types)
        method.save(update_fields=["compatible_dataset_types", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0025_dataset_family_data_format"),
    ]

    operations = [
        migrations.RunPython(repair_dataset_metadata_columns, migrations.RunPython.noop),
    ]
