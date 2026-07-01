from django.db import migrations


def seed_health_events_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="health-events",
        defaults={
            "label": "Health Events",
            "description": "Model health transition history.",
            "sort_order": 125,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_seed_recovery_strategies_screen"),
    ]

    operations = [
        migrations.RunPython(seed_health_events_screen, migrations.RunPython.noop),
    ]
