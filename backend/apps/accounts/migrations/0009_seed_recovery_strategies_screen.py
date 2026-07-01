from django.db import migrations


def seed_recovery_strategies_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="recovery-strategies",
        defaults={
            "label": "Recovery Strategies",
            "description": "Retry, fallback, escalation 복구 전략 관리",
            "sort_order": 66,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_seed_validation_rules_screen"),
    ]

    operations = [
        migrations.RunPython(seed_recovery_strategies_screen, migrations.RunPython.noop),
    ]
