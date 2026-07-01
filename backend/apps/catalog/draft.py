from apps.catalog.models import (
    LLMModel,
    PolicyDraft,
    RecoveryStrategy,
    ResponseValidationRule,
    RoutingPolicy,
    RoutingRule,
    ServiceFeature,
    ThresholdRule,
)


def recommend_tier(model: LLMModel) -> tuple[str, str]:
    if model.context_window >= 32000:
        return "long_context", f"Large context window ({model.context_window:,} tokens)"
    if model.role == "coding":
        return "structured", "Coding-specialized model suited for SQL/JSON generation"
    if model.quality_level >= 4 and model.role == "reasoning":
        return "advanced", f"High quality ({model.quality_level}/5) reasoning model"
    if model.quality_level >= 4:
        return "advanced", f"High quality score ({model.quality_level}/5)"
    if model.speed_level >= 4 and model.cost_level <= 2:
        return "lightweight", f"High speed ({model.speed_level}/5) with low cost ({model.cost_level}/5)"
    if model.privacy_level == "local" and model.speed_level >= 3 and model.cost_level <= 2:
        return "lightweight", "Local model with fast response and zero external cost"
    return "standard", "Balanced performance profile"


def get_tier_recommendations(model_ids: list[int]) -> list[dict]:
    models = LLMModel.objects.filter(id__in=model_ids, is_active=True)
    results = []
    for model in models:
        suggested_tier, reason = recommend_tier(model)
        results.append({
            "model_id": model.id,
            "provider": model.provider,
            "name": model.name,
            "display_name": model.display_name,
            "current_tier": model.model_tier,
            "suggested_tier": suggested_tier,
            "reason": reason,
            "quality_level": model.quality_level,
            "speed_level": model.speed_level,
            "cost_level": model.cost_level,
            "privacy_level": model.privacy_level,
            "context_window": model.context_window,
            "role": model.role,
        })
    return results


def _rank_by_preset(candidates: list[LLMModel], preset: str) -> list[LLMModel]:
    if preset == "cost-first":
        return sorted(candidates, key=lambda m: (m.cost_level, -m.quality_level))
    if preset == "quality-first":
        return sorted(candidates, key=lambda m: (-m.quality_level, m.cost_level))
    if preset == "privacy-first":
        return sorted(candidates, key=lambda m: (0 if m.privacy_level == "local" else 1, -m.quality_level))
    return sorted(candidates, key=lambda m: -(m.quality_level + m.speed_level - m.cost_level))


def generate_draft(
    name: str,
    preset: str,
    model_ids: list[int],
    feature_ids: list[int],
    tier_overrides: dict,
    created_by,
) -> PolicyDraft:
    models = list(LLMModel.objects.filter(id__in=model_ids, is_active=True))
    features = list(ServiceFeature.objects.filter(id__in=feature_ids, is_active=True).order_by("sort_order"))

    tier_assignments: dict[int, str] = {}
    for model in models:
        override = tier_overrides.get(str(model.id))
        tier_assignments[model.id] = override if override else recommend_tier(model)[0]

    feature_model_map: dict[int, list[int]] = {}
    missing_coverage: list[dict] = []

    for feature in features:
        candidates = [m for m in models if tier_assignments.get(m.id) == feature.required_tier]
        if not candidates:
            missing_coverage.append({
                "feature_id": feature.id,
                "feature_name": feature.name,
                "required_tier": feature.required_tier,
                "message": f"No {feature.required_tier} tier model selected. {feature.name} may not be fully supported.",
            })
            candidates = _rank_by_preset(models, preset)
        else:
            candidates = _rank_by_preset(candidates, preset)
        feature_model_map[feature.id] = [m.id for m in candidates]

    routing_rules = []
    for i, feature in enumerate(features):
        routing_rules.append({
            "rule_id": f"D-{(i + 1) * 10:02d}",
            "name": feature.name,
            "description": f"Route {feature.name} requests via {feature.routing_path}",
            "condition_key": feature.condition_key,
            "target_tier": feature.required_tier,
            "priority": (i + 1) * 10,
        })

    threshold_rules = [{
        "rule_id": "D-T01",
        "name": "Long Context Token Control",
        "description": "Prefer long context tier when prompt exceeds 3000 tokens",
        "metric_key": "estimated_tokens",
        "operator": "gte",
        "threshold_value": "3000",
        "action_on_trigger": "prefer_tier",
        "target_tier": "long_context",
        "max_tokens": None,
        "priority": 5,
    }]

    validation_rules = []
    has_structured = any(f.condition_key == "structured_output" for f in features)
    if has_structured:
        validation_rules.append({
            "rule_id": "D-V01",
            "name": "Structured Output JSON Validation",
            "description": "Validate JSON/SQL format for structured output requests",
            "condition_key": "structured_output",
            "validation_type": "json",
            "action_on_fail": "strict_retry",
            "retry_prompt": "",
            "max_retries": 2,
            "target_tier": "",
            "priority": 10,
        })

    recovery_strategies = []
    if validation_rules:
        recovery_strategies.append({
            "strategy_id": "D-S01",
            "name": "Draft Strict Retry then Fallback",
            "description": "Retry once with a clearer prompt, then fallback if still failing",
            "trigger_event": "validation_fail",
            "action": "strict_retry",
            "retry_prompt": "",
            "max_retries": 2,
            "target_tier": "",
            "priority": 10,
        })

    lines = [f"Recommended Hybrid Routing Policy ({preset})", ""]
    for i, feature in enumerate(features, 1):
        ids = feature_model_map.get(feature.id, [])
        primary = next((m for m in models if m.id == ids[0]), None) if ids else None
        model_label = primary.display_name if primary else "No model available"
        lines.append(f"{i}. {feature.name} → {feature.routing_path.replace('_', ' ').title()}")
        lines.append(f"   Primary Model: {model_label}")
    lines.append("")
    lines.append("• Long context requests (>3000 tokens) will prefer Long Context tier.")
    if validation_rules:
        lines.append("• Structured output requests will be validated and retried on failure.")
    if missing_coverage:
        lines.append("")
        lines.append("⚠ Missing Coverage:")
        for mc in missing_coverage:
            lines.append(f"  - {mc['message']}")

    return PolicyDraft.objects.create(
        name=name,
        preset=preset,
        selected_model_ids=model_ids,
        tier_assignments={str(k): v for k, v in tier_assignments.items()},
        feature_model_map={str(k): v for k, v in feature_model_map.items()},
        routing_rules=routing_rules,
        threshold_rules=threshold_rules,
        validation_rules=validation_rules,
        recovery_strategies=recovery_strategies,
        summary_text="\n".join(lines),
        missing_coverage=missing_coverage,
        created_by=created_by,
    )


def save_draft_as_policy(draft: PolicyDraft) -> RoutingPolicy:
    preset_configs = {
        "cost-first": {"cost_weight": 0.6, "quality_weight": 0.2, "speed_weight": 0.2},
        "quality-first": {"quality_weight": 0.6, "cost_weight": 0.2, "speed_weight": 0.2},
        "privacy-first": {"local_only": True},
        "balanced": {"quality_weight": 0.34, "speed_weight": 0.33, "cost_weight": 0.33},
    }

    base_name = draft.name.lower().replace(" ", "-").replace("_", "-")[:60]
    policy_name = base_name
    if RoutingPolicy.objects.filter(name=policy_name).exists():
        policy_name = f"{base_name}-{draft.id}"[:64]

    policy = RoutingPolicy.objects.create(
        name=policy_name,
        display_name=draft.name,
        description=f"Generated from Policy Draft #{draft.id} ({draft.preset})",
        priority_config=preset_configs.get(draft.preset, {}),
        is_active=True,
    )

    for rule_data in draft.routing_rules:
        rule_id = rule_data["rule_id"]
        if RoutingRule.objects.filter(rule_id=rule_id).exists():
            rule_id = f"{rule_id}-{draft.id}"
        RoutingRule.objects.get_or_create(
            rule_id=rule_id,
            defaults={
                "name": rule_data["name"],
                "description": rule_data.get("description", ""),
                "condition_key": rule_data["condition_key"],
                "target_tier": rule_data["target_tier"],
                "priority": rule_data["priority"],
                "is_active": True,
            },
        )

    for rule_data in draft.threshold_rules:
        rule_id = rule_data["rule_id"]
        if ThresholdRule.objects.filter(rule_id=rule_id).exists():
            rule_id = f"{rule_id}-{draft.id}"
        ThresholdRule.objects.get_or_create(
            rule_id=rule_id,
            defaults={
                "name": rule_data["name"],
                "description": rule_data.get("description", ""),
                "metric_key": rule_data["metric_key"],
                "operator": rule_data["operator"],
                "threshold_value": rule_data["threshold_value"],
                "action_on_trigger": rule_data["action_on_trigger"],
                "target_tier": rule_data.get("target_tier", ""),
                "max_tokens": rule_data.get("max_tokens"),
                "priority": rule_data["priority"],
                "is_active": True,
            },
        )

    saved_strategy = None
    for strat_data in draft.recovery_strategies:
        strat_id = strat_data["strategy_id"]
        if RecoveryStrategy.objects.filter(strategy_id=strat_id).exists():
            strat_id = f"{strat_id}-{draft.id}"
        saved_strategy, _ = RecoveryStrategy.objects.get_or_create(
            strategy_id=strat_id,
            defaults={
                "name": strat_data["name"],
                "description": strat_data.get("description", ""),
                "trigger_event": strat_data["trigger_event"],
                "action": strat_data["action"],
                "retry_prompt": strat_data.get("retry_prompt", ""),
                "max_retries": strat_data.get("max_retries", 1),
                "target_tier": strat_data.get("target_tier", ""),
                "priority": strat_data["priority"],
                "is_active": True,
            },
        )

    for rule_data in draft.validation_rules:
        rule_id = rule_data["rule_id"]
        if ResponseValidationRule.objects.filter(rule_id=rule_id).exists():
            rule_id = f"{rule_id}-{draft.id}"
        ResponseValidationRule.objects.get_or_create(
            rule_id=rule_id,
            defaults={
                "name": rule_data["name"],
                "description": rule_data.get("description", ""),
                "recovery_strategy": saved_strategy,
                "condition_key": rule_data["condition_key"],
                "validation_type": rule_data["validation_type"],
                "action_on_fail": rule_data["action_on_fail"],
                "retry_prompt": rule_data.get("retry_prompt", ""),
                "max_retries": rule_data.get("max_retries", 1),
                "target_tier": rule_data.get("target_tier", ""),
                "priority": rule_data["priority"],
                "is_active": True,
            },
        )

    draft.is_saved = True
    draft.save(update_fields=["is_saved"])
    return policy
