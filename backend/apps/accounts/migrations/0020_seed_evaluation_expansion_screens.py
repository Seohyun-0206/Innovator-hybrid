from django.db import migrations


SCREENS = [
    ("evaluation-methods", "평가방식", "모델/데이터셋과 조합할 평가방식을 관리합니다.", 28),
    ("evaluation-item-results", "문항별 로그", "평가 실행의 문항별 응답, 정답, 지연, 오류 로그를 확인합니다.", 31),
    ("evaluation-artifacts", "산출물", "평가 manifest, 모델 요약, scorecard, JSONL 로그, 리포트를 확인합니다.", 32),
    ("ops-status", "운영 현황", "라우팅 운영 지표와 최근 상태를 확인합니다.", 60),
]


def seed_screens(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    UserScreenAccess = apps.get_model("accounts", "UserScreenAccess")

    for screen_id, label, description, sort_order in SCREENS:
        ScreenDefinition.objects.update_or_create(
            screen_id=screen_id,
            defaults={
                "label": label,
                "description": description,
                "sort_order": sort_order,
                "is_active": True,
            },
        )

    for access in UserScreenAccess.objects.all():
        allowed = list(access.allowed_screens or [])
        if "evaluation-datasets" in allowed or "evaluation-runs" in allowed or "model-evaluation" in allowed:
            for screen_id, _, _, _ in SCREENS[:3]:
                if screen_id not in allowed:
                    allowed.append(screen_id)
        if "dashboard" in allowed and "ops-status" not in allowed:
            allowed.append("ops-status")
        if allowed != access.allowed_screens:
            access.allowed_screens = allowed
            access.save(update_fields=["allowed_screens"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0019_grant_evaluation_runs_access"),
    ]

    operations = [
        migrations.RunPython(seed_screens, migrations.RunPython.noop),
    ]
