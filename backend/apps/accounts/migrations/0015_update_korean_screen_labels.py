from django.db import migrations


SCREEN_LABELS = [
    ("dashboard", "운영 현황", "전체 요청, 지연, 비용, 실패율 등 운영 지표를 확인합니다.", 10),
    ("models", "모델", "LLM 모델 카탈로그와 모델별 속성을 관리합니다.", 20),
    ("credentials", "인증 관리", "외부 Provider 접속 정보와 API 인증 정보를 관리합니다.", 21),
    ("model-evaluation", "평가 결과", "등록된 모델의 평가 결과와 주요 지표를 확인합니다.", 30),
    ("tier-recommendation", "Tier 추천", "모델 메타데이터 기반 Tier 추천 결과를 확인합니다.", 31),
    ("feature-ranking", "기능별 모델 순위", "서비스 기능별 후보 모델과 우선순위를 확인합니다.", 32),
    ("policies", "정책", "라우팅 정책을 조회하고 관리합니다.", 40),
    ("service-features", "대상 서비스", "서비스 기능별 필요 Tier와 라우팅 경로를 정의합니다.", 41),
    ("routing-rules", "라우팅 규칙", "프롬프트 조건 기반 라우팅 규칙을 관리합니다.", 42),
    ("threshold-rules", "SLA/임계값", "토큰, 지연, 실패율 등 임계값 기반 정책을 관리합니다.", 43),
    ("policy-draft", "초안 생성", "모델 평가와 서비스 기능을 바탕으로 정책 초안을 생성합니다.", 44),
    ("playground", "테스트", "프롬프트를 실제 LLM에 호출하고 라우팅 결과를 확인합니다.", 50),
    ("simulator", "시뮬레이션", "LLM 호출 없이 프롬프트별 모델 선택 결과를 시뮬레이션합니다.", 51),
    ("validation-rules", "응답 규칙", "JSON, SQL, 빈 응답 등 응답 형식 검증 규칙을 관리합니다.", 60),
    ("recovery-strategies", "복구 전략", "검증 실패, timeout, API 실패 시 retry/fallback/escalation 전략을 관리합니다.", 61),
    ("logs", "라우팅 로그", "라우팅 요청 로그와 상세 실행 결과를 조회합니다.", 70),
    ("health-rules", "모델 상태 규칙", "모델 상태 판단과 자동 제외 규칙을 관리합니다.", 71),
    ("health-events", "상태 이벤트", "모델 상태 변화와 health rule 발동 이력을 확인합니다.", 72),
    ("health-overrides", "수동 조치", "모델 상태를 수동으로 정상/비정상 처리합니다.", 73),
    ("quotas", "사용량 한도", "요청 수와 비용 기반 사용량 한도를 관리합니다.", 74),
    ("users", "사용자", "사용자 계정과 화면 접근 권한을 관리합니다.", 90),
    ("screens", "화면 권한", "권한에서 사용할 화면 목록을 관리합니다.", 91),
    ("security-settings", "보안 설정", "세션 제한, timeout 등 보안 정책을 관리합니다.", 92),
    ("sessions", "사용자 세션", "사용자 로그인 세션을 조회하고 강제 종료합니다.", 93),
    ("audit-logs", "감사 로그", "관리 작업과 보안 이벤트의 감사 로그를 조회합니다.", 94),
]


def update_screen_labels(apps, schema_editor):
    ScreenDefinition = apps.get_model("accounts", "ScreenDefinition")
    for screen_id, label, description, sort_order in SCREEN_LABELS:
        ScreenDefinition.objects.update_or_create(
            screen_id=screen_id,
            defaults={
                "label": label,
                "description": description,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_seed_policy_draft_screens"),
    ]

    operations = [
        migrations.RunPython(update_screen_labels, migrations.RunPython.noop),
    ]
