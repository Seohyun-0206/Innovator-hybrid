from django.db import migrations


def seed_routing_rules_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="routing-rules",
        defaults={
            "label": "Routing Rules",
            "description": "서비스 기능과 요청 조건별 모델 Tier 라우팅 규칙 관리",
            "sort_order": 55,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_seed_health_rules_screen"),
    ]

    operations = [
        migrations.RunPython(seed_routing_rules_screen, migrations.RunPython.noop),
    ]
