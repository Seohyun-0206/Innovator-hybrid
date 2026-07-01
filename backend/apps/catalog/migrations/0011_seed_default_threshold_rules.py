from django.db import migrations


DEFAULT_THRESHOLD_RULES = [
    {
        "rule_id": "T-08",
        "name": "Token control path",
        "description": "출력량 과다 예상 요청은 Long Context Tier를 우선 사용합니다.",
        "metric_key": "estimated_tokens",
        "operator": "gte",
        "threshold_value": "3000.0000",
        "action_on_trigger": "prefer_tier",
        "target_tier": "long_context",
        "max_tokens": None,
        "priority": 80,
    },
]


def seed_default_threshold_rules(apps, schema_editor):
    ThresholdRule = apps.get_model("catalog", "ThresholdRule")
    for rule in DEFAULT_THRESHOLD_RULES:
        ThresholdRule.objects.update_or_create(
            rule_id=rule["rule_id"],
            defaults={**rule, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_thresholdrule"),
    ]

    operations = [
        migrations.RunPython(seed_default_threshold_rules, migrations.RunPython.noop),
    ]
