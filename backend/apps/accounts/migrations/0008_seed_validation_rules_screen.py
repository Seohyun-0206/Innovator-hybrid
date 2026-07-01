from django.db import migrations


def seed_validation_rules_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="validation-rules",
        defaults={
            "label": "Validation Rules",
            "description": "응답 형식 검증과 실패 시 retry/fallback/escalation 정책 관리",
            "sort_order": 65,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_seed_threshold_rules_screen"),
    ]

    operations = [
        migrations.RunPython(seed_validation_rules_screen, migrations.RunPython.noop),
    ]
