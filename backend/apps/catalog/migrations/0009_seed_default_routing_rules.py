from django.db import migrations


DEFAULT_RULES = [
    {
        "rule_id": "R-01",
        "name": "Simple FAQ fast path",
        "description": "일반 FAQ/단순 질의는 Lightweight Tier를 우선 사용합니다.",
        "condition_key": "general",
        "target_tier": "lightweight",
        "priority": 10,
    },
    {
        "rule_id": "R-05",
        "name": "Reasoning escalation path",
        "description": "고난도 추론/복합 reasoning 요청은 Advanced Tier를 우선 사용합니다.",
        "condition_key": "reasoning",
        "target_tier": "advanced",
        "priority": 50,
    },
    {
        "rule_id": "R-06",
        "name": "Long context path",
        "description": "긴 문서 기반 QA와 긴 context 요청은 Long Context Tier를 우선 사용합니다.",
        "condition_key": "long_context",
        "target_tier": "long_context",
        "priority": 60,
    },
    {
        "rule_id": "R-07",
        "name": "Structured output path",
        "description": "SQL/JSON 생성 요청은 Structured Tier를 우선 사용합니다.",
        "condition_key": "structured_output",
        "target_tier": "structured",
        "priority": 70,
    },
    {
        "rule_id": "R-04",
        "name": "Sensitive accuracy guard",
        "description": "민감 정보가 포함된 요청은 Advanced Tier 후보를 우선 검토하되 privacy 정책이 먼저 적용됩니다.",
        "condition_key": "sensitive",
        "target_tier": "advanced",
        "priority": 40,
    },
]


def seed_default_routing_rules(apps, schema_editor):
    RoutingRule = apps.get_model("catalog", "RoutingRule")
    for rule in DEFAULT_RULES:
        RoutingRule.objects.update_or_create(
            rule_id=rule["rule_id"],
            defaults={**rule, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_llmmodel_model_tier_routingrule"),
    ]

    operations = [
        migrations.RunPython(seed_default_routing_rules, migrations.RunPython.noop),
    ]
