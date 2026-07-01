from django.db import migrations


def split_evaluation_screens(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    ScreenDefinition.objects.update_or_create(
        screen_id="evaluation-datasets",
        defaults={
            "label": "데이터셋 관리",
            "description": "MMLU 등 평가 데이터셋의 출처, 원문, 문항 수를 관리합니다.",
            "sort_order": 29,
            "is_active": True,
        },
    )
    ScreenDefinition.objects.update_or_create(
        screen_id="evaluation-runs",
        defaults={
            "label": "평가 실행",
            "description": "등록된 데이터셋과 모델을 선택해 평가 실행과 파일럿 자동 평가를 수행합니다.",
            "sort_order": 30,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_seed_evaluation_datasets_screen"),
    ]

    operations = [
        migrations.RunPython(split_evaluation_screens, migrations.RunPython.noop),
    ]
