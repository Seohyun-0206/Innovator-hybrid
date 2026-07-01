from django.db import migrations


def grant_evaluation_runs_access(apps, schema_editor):
    UserScreenAccess = apps.get_model("accounts", "UserScreenAccess")
    for access in UserScreenAccess.objects.all():
        allowed_screens = list(access.allowed_screens or [])
        should_add = (
            "evaluation-runs" not in allowed_screens
            and (
                "evaluation-datasets" in allowed_screens
                or "model-evaluation" in allowed_screens
            )
        )
        if should_add:
            insert_index = len(allowed_screens)
            if "model-evaluation" in allowed_screens:
                insert_index = allowed_screens.index("model-evaluation")
            allowed_screens.insert(insert_index, "evaluation-runs")
            access.allowed_screens = allowed_screens
            access.save(update_fields=["allowed_screens"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0018_split_evaluation_runs_screen"),
    ]

    operations = [
        migrations.RunPython(grant_evaluation_runs_access, migrations.RunPython.noop),
    ]
