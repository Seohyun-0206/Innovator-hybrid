from django.db import migrations


DEFAULT_VALIDATION_RULES = [
    {
        "rule_id": "V-07",
        "name": "Structured JSON validation",
        "description": "JSON/SQL 구조화 요청에서 JSON parse validation을 수행하고 실패하면 strict retry를 시도합니다.",
        "condition_key": "structured_output",
        "validation_type": "json",
        "action_on_fail": "strict_retry",
        "retry_prompt": "Return only valid JSON. Do not include markdown fences, prose, or comments.",
        "max_retries": 1,
        "target_tier": "",
        "priority": 70,
    },
]


def seed_default_response_validation_rules(apps, schema_editor):
    ResponseValidationRule = apps.get_model("catalog", "ResponseValidationRule")
    for rule in DEFAULT_VALIDATION_RULES:
        ResponseValidationRule.objects.update_or_create(
            rule_id=rule["rule_id"],
            defaults={**rule, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_responsevalidationrule"),
    ]

    operations = [
        migrations.RunPython(seed_default_response_validation_rules, migrations.RunPython.noop),
    ]
