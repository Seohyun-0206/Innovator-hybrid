from django.db import migrations


def seed_health_overrides_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="health-overrides",
        defaults={
            "label": "Health Overrides",
            "description": "Manual model health override management.",
            "sort_order": 126,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_seed_health_events_screen"),
    ]

    operations = [
        migrations.RunPython(seed_health_overrides_screen, migrations.RunPython.noop),
    ]
