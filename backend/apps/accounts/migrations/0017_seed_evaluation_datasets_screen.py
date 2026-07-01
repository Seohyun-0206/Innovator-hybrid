from django.db import migrations


def seed_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="evaluation-datasets",
        defaults={
            "label": "평가 데이터셋",
            "description": "MMLU 등 평가 데이터셋을 등록하고 모델 평가 실행을 생성합니다.",
            "sort_order": 29,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0016_update_short_menu_labels"),
    ]

    operations = [
        migrations.RunPython(seed_screen, migrations.RunPython.noop),
    ]
