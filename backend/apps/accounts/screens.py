DEFAULT_SCREENS = [
    {"id": "dashboard", "label": "운영 현황"},
    {"id": "models", "label": "모델"},
    {"id": "credentials", "label": "인증 관리"},
    {"id": "evaluation-datasets", "label": "데이터셋 관리"},
    {"id": "evaluation-methods", "label": "평가방식"},
    {"id": "evaluation-runs", "label": "평가 실행"},
    {"id": "model-evaluation", "label": "평가 결과"},
    {"id": "evaluation-item-results", "label": "문항별 로그"},
    {"id": "evaluation-artifacts", "label": "산출물"},
    {"id": "tier-recommendation", "label": "Tier 추천"},
    {"id": "feature-ranking", "label": "기능별 모델 순위"},
    {"id": "policies", "label": "정책"},
    {"id": "service-features", "label": "대상 서비스"},
    {"id": "routing-rules", "label": "라우팅 규칙"},
    {"id": "threshold-rules", "label": "SLA/임계값"},
    {"id": "policy-draft", "label": "초안 생성"},
    {"id": "playground", "label": "테스트"},
    {"id": "simulator", "label": "시뮬레이션"},
    {"id": "validation-rules", "label": "응답 규칙"},
    {"id": "recovery-strategies", "label": "복구 전략"},
    {"id": "ops-status", "label": "운영 현황"},
    {"id": "logs", "label": "라우팅 로그"},
    {"id": "health-rules", "label": "모델 상태 규칙"},
    {"id": "health-events", "label": "상태 이벤트"},
    {"id": "health-overrides", "label": "수동 조치"},
    {"id": "quotas", "label": "사용량 한도"},
    {"id": "users", "label": "사용자"},
    {"id": "screens", "label": "화면 권한"},
    {"id": "security-settings", "label": "보안 설정"},
    {"id": "sessions", "label": "사용자 세션"},
    {"id": "audit-logs", "label": "감사 로그"},
]

ALL_SCREENS = [screen["id"] for screen in DEFAULT_SCREENS]


def get_available_screens(include_inactive: bool = False) -> list[dict[str, object]]:
    # 마이그레이션 전 테스트나 초기 상태에서도 기본 화면 목록은 반환되도록 fallback을 둡니다.
    from apps.accounts.models import ScreenDefinition

    queryset = ScreenDefinition.objects.all()
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    screens = [
        {
            "pk": screen.pk,
            "id": screen.screen_id,
            "label": screen.label,
            "description": screen.description,
            "sort_order": screen.sort_order,
            "is_active": screen.is_active,
        }
        for screen in queryset
    ]
    return screens or DEFAULT_SCREENS


def get_available_screen_ids(include_inactive: bool = False) -> list[str]:
    return [screen["id"] for screen in get_available_screens(include_inactive=include_inactive)]


def normalize_allowed_screens(value: list[str]) -> list[str]:
    # 관리자가 직접 입력한 화면 id도 허용하되, 빈 값과 중복 값은 저장 전에 제거합니다.
    normalized = []
    for screen in value:
        if not isinstance(screen, str):
            continue
        screen_id = screen.strip()
        if screen_id and screen_id not in normalized:
            normalized.append(screen_id)
    return normalized
