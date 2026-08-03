from django.db import migrations


SCREEN_ID = "model-evaluation-chart"


def seed_screen(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    UserScreenAccess = apps.get_model("accounts", "UserScreenAccess")

    ScreenDefinition.objects.update_or_create(
        screen_id=SCREEN_ID,
        defaults={
            "label": "결과 분석 (Chart)",
            "description": "단독 모델과 라우팅 정책의 품질, 지연, 토큰 사용량 차이를 차트로 비교합니다.",
            "sort_order": 31,
            "is_active": True,
        },
    )

    # 기존 결과 분석 사용자는 새 시각화 화면도 바로 사용할 수 있게 권한을 이어받습니다.
    for access in UserScreenAccess.objects.all():
        allowed = list(access.allowed_screens or [])
        if "model-evaluation" in allowed and SCREEN_ID not in allowed:
            insert_at = allowed.index("model-evaluation") + 1
            allowed.insert(insert_at, SCREEN_ID)
            access.allowed_screens = allowed
            access.save(update_fields=["allowed_screens"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_seed_generated_datasets_screen"),
    ]

    operations = [
        migrations.RunPython(seed_screen, migrations.RunPython.noop),
    ]
