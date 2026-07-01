from django.db import migrations


SERVICE_FEATURES = [
    {
        "name": "Real-time Chatbot",
        "description": "SLA-critical real-time chatbot responses requiring sub-second latency",
        "required_tier": "lightweight",
        "routing_path": "lightweight",
        "condition_key": "always",
        "main_metrics": ["p95 Latency", "Timeout Rate"],
        "sort_order": 15,
        "is_active": True,
    },
    {
        "name": "Report Generation",
        "description": "Long-form report generation requiring deep reasoning and structured output",
        "required_tier": "advanced",
        "routing_path": "advanced",
        "condition_key": "reasoning",
        "main_metrics": ["Completeness", "Output Quality", "Human Review"],
        "sort_order": 25,
        "is_active": True,
    },
    {
        "name": "Document Summary",
        "description": "Document summarization requiring balanced output quality and key content coverage",
        "required_tier": "standard",
        "routing_path": "standard",
        "condition_key": "general",
        "main_metrics": ["Coverage", "Summary Quality"],
        "sort_order": 45,
        "is_active": True,
    },
]

ROUTING_RULES = [
    {
        "rule_id": "R-02",
        "name": "SLA / Real-time Chatbot Path",
        "description": "SLA 또는 실시간 응답이 필요한 경우 Lightweight Path로 라우팅",
        "condition_key": "always",
        "target_tier": "lightweight",
        "priority": 15,
        "is_active": True,
    },
    {
        "rule_id": "R-03",
        "name": "General Business QA Path",
        "description": "일반 업무 질의는 Standard Path로 기본 라우팅",
        "condition_key": "general",
        "target_tier": "standard",
        "priority": 30,
        "is_active": True,
    },
    {
        "rule_id": "R-11",
        "name": "Revalidation Escalation Path",
        "description": "신뢰도 낮음 또는 재검증 필요 시 Advanced Tier로 에스컬레이션",
        "condition_key": "always",
        "target_tier": "advanced",
        "priority": 110,
        "is_active": True,
    },
    {
        "rule_id": "R-13",
        "name": "Efficiency Path",
        "description": "모델 성능 차이가 미미할 경우 latency/cost 효율 우선으로 Lightweight 선택",
        "condition_key": "always",
        "target_tier": "lightweight",
        "priority": 130,
        "is_active": True,
    },
]

THRESHOLD_RULES = [
    {
        "rule_id": "T-01",
        "name": "Fast Path Latency Guard",
        "description": "p95 latency가 기준 이하인 경우 Lightweight Path 우선 적용",
        "metric_key": "p95_latency_ms",
        "operator": "lte",
        "threshold_value": "1000.0000",
        "action_on_trigger": "prefer_tier",
        "target_tier": "lightweight",
        "max_tokens": None,
        "priority": 10,
        "is_active": True,
    },
    {
        "rule_id": "T-02",
        "name": "Timeout Trigger Guard",
        "description": "응답 시간이 timeout 기준을 초과하면 Advanced Tier로 전환",
        "metric_key": "timeout_seconds",
        "operator": "gte",
        "threshold_value": "30.0000",
        "action_on_trigger": "prefer_tier",
        "target_tier": "advanced",
        "max_tokens": None,
        "priority": 20,
        "is_active": True,
    },
    {
        "rule_id": "T-03",
        "name": "Parse Fail Rate Guard",
        "description": "형식 불일치 발생률이 30% 이상이면 Structured Tier 우선 적용",
        "metric_key": "parse_fail_rate",
        "operator": "gte",
        "threshold_value": "0.3000",
        "action_on_trigger": "prefer_tier",
        "target_tier": "structured",
        "max_tokens": None,
        "priority": 30,
        "is_active": True,
    },
    {
        "rule_id": "T-04",
        "name": "High Failure Rate Guard",
        "description": "전체 실패율이 20% 이상이면 Advanced Tier로 에스컬레이션",
        "metric_key": "failure_rate",
        "operator": "gte",
        "threshold_value": "0.2000",
        "action_on_trigger": "prefer_tier",
        "target_tier": "advanced",
        "max_tokens": None,
        "priority": 40,
        "is_active": True,
    },
]

RECOVERY_STRATEGIES = [
    {
        "strategy_id": "S-02",
        "name": "Timeout Fallback",
        "description": "timeout 발생 시 대체 모델로 즉시 Fallback 호출",
        "trigger_event": "timeout",
        "action": "fallback",
        "retry_prompt": "",
        "max_retries": 1,
        "target_tier": "",
        "priority": 20,
        "is_active": True,
    },
    {
        "strategy_id": "S-03",
        "name": "API Failure Fallback",
        "description": "API 실패 시 대체 모델로 Fallback 호출",
        "trigger_event": "api_fail",
        "action": "fallback",
        "retry_prompt": "",
        "max_retries": 1,
        "target_tier": "",
        "priority": 30,
        "is_active": True,
    },
    {
        "strategy_id": "S-04",
        "name": "Parse Fail Strict Retry",
        "description": "parse fail 발생 시 strict prompt로 최대 2회 재시도",
        "trigger_event": "parse_fail",
        "action": "strict_retry",
        "retry_prompt": "Please respond strictly in the requested format. Do not include any explanation outside the format.",
        "max_retries": 2,
        "target_tier": "",
        "priority": 40,
        "is_active": True,
    },
    {
        "strategy_id": "S-05",
        "name": "Low Confidence Escalation",
        "description": "신뢰도 낮음 또는 재검증 필요 시 Advanced Tier로 에스컬레이션",
        "trigger_event": "low_confidence",
        "action": "escalate",
        "retry_prompt": "",
        "max_retries": 1,
        "target_tier": "advanced",
        "priority": 50,
        "is_active": True,
    },
]

VALIDATION_RULES = [
    {
        "rule_id": "V-01",
        "name": "Timeout Response Check",
        "description": "SLA 기준 초과 응답 탐지 시 Fallback Path 수행",
        "condition_key": "general",
        "validation_type": "non_empty",
        "action_on_fail": "fallback",
        "retry_prompt": "",
        "max_retries": 1,
        "target_tier": "",
        "priority": 10,
        "is_active": True,
    },
    {
        "rule_id": "V-02",
        "name": "Retry Success Validation",
        "description": "Retry 성공 여부 확인 후 횟수 초과 시 Escalation 수행",
        "condition_key": "always",
        "validation_type": "non_empty",
        "action_on_fail": "escalate",
        "retry_prompt": "",
        "max_retries": 2,
        "target_tier": "advanced",
        "priority": 20,
        "is_active": True,
    },
    {
        "rule_id": "V-03",
        "name": "Groundedness Check",
        "description": "문서 기반 응답 여부 검증 실패 시 Advanced Tier 에스컬레이션",
        "condition_key": "long_context",
        "validation_type": "non_empty",
        "action_on_fail": "escalate",
        "retry_prompt": "Please answer based strictly on the provided document. Do not include information not found in the source.",
        "max_retries": 1,
        "target_tier": "advanced",
        "priority": 50,
        "is_active": True,
    },
    {
        "rule_id": "V-04",
        "name": "Hallucination Risk Check",
        "description": "허위 정보 가능성 탐지 시 Advanced Tier 재검증",
        "condition_key": "reasoning",
        "validation_type": "non_empty",
        "action_on_fail": "escalate",
        "retry_prompt": "Please verify your response for factual accuracy. Remove any statements you cannot confirm.",
        "max_retries": 2,
        "target_tier": "advanced",
        "priority": 60,
        "is_active": True,
    },
    {
        "rule_id": "V-05",
        "name": "Context Continuity Validation",
        "description": "긴 문맥 유지 여부 확인 실패 시 Long Context Tier로 전환",
        "condition_key": "long_context",
        "validation_type": "non_empty",
        "action_on_fail": "escalate",
        "retry_prompt": "",
        "max_retries": 1,
        "target_tier": "long_context",
        "priority": 65,
        "is_active": True,
    },
    {
        "rule_id": "V-06",
        "name": "SQL Format Validation",
        "description": "SQL 형식 검증 실패 시 strict prompt로 재시도",
        "condition_key": "structured_output",
        "validation_type": "sql",
        "action_on_fail": "strict_retry",
        "retry_prompt": "Please generate a valid SQL query only. Do not include explanations or markdown formatting.",
        "max_retries": 2,
        "target_tier": "",
        "priority": 75,
        "is_active": True,
    },
]


def seed_data(apps, schema_editor):
    ServiceFeature = apps.get_model("catalog", "ServiceFeature")
    RoutingRule = apps.get_model("catalog", "RoutingRule")
    ThresholdRule = apps.get_model("catalog", "ThresholdRule")
    RecoveryStrategy = apps.get_model("catalog", "RecoveryStrategy")
    ResponseValidationRule = apps.get_model("catalog", "ResponseValidationRule")

    for item in SERVICE_FEATURES:
        ServiceFeature.objects.update_or_create(name=item["name"], defaults=item)

    for item in ROUTING_RULES:
        RoutingRule.objects.update_or_create(rule_id=item["rule_id"], defaults=item)

    for item in THRESHOLD_RULES:
        ThresholdRule.objects.update_or_create(rule_id=item["rule_id"], defaults=item)

    for item in RECOVERY_STRATEGIES:
        RecoveryStrategy.objects.update_or_create(strategy_id=item["strategy_id"], defaults=item)

    for item in VALIDATION_RULES:
        ResponseValidationRule.objects.update_or_create(rule_id=item["rule_id"], defaults=item)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0021_seed_service_features"),
    ]

    operations = [
        migrations.RunPython(seed_data, migrations.RunPython.noop),
    ]
