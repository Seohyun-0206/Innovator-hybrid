from django.db import migrations


def seed_health_rules_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="health-rules",
        defaults={
            "label": "Health Rules",
            "description": "모델 장애 임계치와 자동 라우팅 제외 규칙 관리",
            "sort_order": 75,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_seed_usage_quotas_screen"),
    ]

    operations = [
        migrations.RunPython(seed_health_rules_screen, migrations.RunPython.noop),
    ]
