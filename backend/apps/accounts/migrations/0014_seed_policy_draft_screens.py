from django.db import migrations


NEW_SCREENS = [
    {"screen_id": "model-evaluation", "label": "Model Evaluation", "description": "등록된 모델에 대한 평가 실행 및 결과 비교", "sort_order": 35},
    {"screen_id": "tier-recommendation", "label": "Tier Recommendation", "description": "모델 메타데이터 기반 Tier 자동 추천", "sort_order": 36},
    {"screen_id": "service-features", "label": "Service Features", "description": "서비스 기능별 필요 Tier 및 라우팅 Path 정의", "sort_order": 37},
    {"screen_id": "feature-ranking", "label": "Feature Ranking", "description": "서비스 기능별 후보 모델 및 우선순위 조회", "sort_order": 38},
    {"screen_id": "policy-draft", "label": "Policy Draft Generator", "description": "평가 결과 기반 라우팅 정책 초안 자동 생성", "sort_order": 39},
]


def seed_screens(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    for screen in NEW_SCREENS:
        ScreenDefinition.objects.update_or_create(
            screen_id=screen["screen_id"],
            defaults={
                "label": screen["label"],
                "description": screen["description"],
                "sort_order": screen["sort_order"],
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_auditlog_seed_audit_logs_screen"),
    ]

    operations = [
        migrations.RunPython(seed_screens, migrations.RunPython.noop),
    ]
