from django.db import migrations


def seed_default_recovery_strategy(apps, schema_editor):
    RecoveryStrategy = apps.get_model("catalog", "RecoveryStrategy")
    ResponseValidationRule = apps.get_model("catalog", "ResponseValidationRule")
    strategy, _ = RecoveryStrategy.objects.update_or_create(
        strategy_id="S-01",
        defaults={
            "name": "Strict retry then fallback",
            "description": "Validation 실패 시 엄격한 재시도 프롬프트로 1회 재시도하고, 실패하면 다음 후보로 fallback합니다.",
            "trigger_event": "validation_fail",
            "action": "strict_retry",
            "retry_prompt": "Return only valid JSON. Do not include markdown fences, prose, or comments.",
            "max_retries": 1,
            "target_tier": "",
            "priority": 10,
            "is_active": True,
        },
    )
    ResponseValidationRule.objects.filter(rule_id="V-07").update(recovery_strategy=strategy)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0014_recoverystrategy_validation_recovery_strategy"),
    ]

    operations = [
        migrations.RunPython(seed_default_recovery_strategy, migrations.RunPython.noop),
    ]
