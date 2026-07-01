from django.db import migrations


def seed_routing_simulator_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="simulator",
        defaults={
            "label": "Routing Simulator",
            "description": "프롬프트별 모델 선택 점수 시뮬레이션",
            "sort_order": 25,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_screendefinition"),
    ]

    operations = [
        migrations.RunPython(seed_routing_simulator_screen, migrations.RunPython.noop),
    ]
