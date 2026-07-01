from django.db import migrations


def seed_threshold_rules_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="threshold-rules",
        defaults={
            "label": "Threshold Rules",
            "description": "토큰, latency, timeout 등 정책 발동 임계치 관리",
            "sort_order": 60,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_seed_routing_rules_screen"),
    ]

    operations = [
        migrations.RunPython(seed_threshold_rules_screen, migrations.RunPython.noop),
    ]
