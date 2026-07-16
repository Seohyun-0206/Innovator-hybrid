from django.db import migrations


def seed_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    UserScreenAccess = apps.get_model("accounts", "UserScreenAccess")

    ScreenDefinition.objects.update_or_create(
        screen_id="generated-datasets",
        defaults={
            "label": "생성 데이터셋",
            "description": "대상 서비스별 LLM 생성 평가 데이터셋을 관리합니다.",
            "sort_order": 27,
            "is_active": True,
        },
    )

    for access in UserScreenAccess.objects.all():
        allowed = list(access.allowed_screens or [])
        if "evaluation-datasets" in allowed and "generated-datasets" not in allowed:
            allowed.append("generated-datasets")
            access.allowed_screens = allowed
            access.save(update_fields=["allowed_screens"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0020_seed_evaluation_expansion_screens"),
    ]

    operations = [
        migrations.RunPython(seed_screen, migrations.RunPython.noop),
    ]
