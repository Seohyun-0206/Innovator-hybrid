from django.db import migrations


def seed_usage_quotas_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="quotas",
        defaults={
            "label": "Usage Quotas",
            "description": "Manage monthly request and cost limits.",
            "sort_order": 65,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_seed_routing_simulator_screen"),
    ]

    operations = [
        migrations.RunPython(seed_usage_quotas_screen, migrations.RunPython.noop),
    ]
