from rest_framework import serializers
from django.utils import timezone

from apps.catalog.health import evaluate_model_health, serialize_model_health_status
from apps.catalog.models import (
    EvaluationDataset,
    EvaluationItemResult,
    EvaluationMethod,
    EvaluationResult,
    EvaluationRoutingCandidate,
    EvaluationRun,
    GeneratedDataset,
    LLMModel,
    ModelHealthEvent,
    ModelHealthOverride,
    ModelHealthRule,
    PolicyDraft,
    ProviderCredential,
    RecoveryStrategy,
    ResponseValidationRule,
    RoutingPolicy,
    RoutingRule,
    ServiceFeature,
    ThresholdRule,
    UsageQuota,
)
from apps.catalog.usage import get_quota_usage


class LLMModelSerializer(serializers.ModelSerializer):
    provider_credential_display_name = serializers.CharField(
        source="provider_credential.display_name",
        read_only=True,
        allow_null=True,
    )
    health_status = serializers.SerializerMethodField()
    health_reason = serializers.SerializerMethodField()
    health_metrics = serializers.SerializerMethodField()

    class Meta:
        model = LLMModel
        fields = [
            "id",
            "provider",
            "name",
            "display_name",
            "model_tier",
            "provider_credential",
            "provider_credential_display_name",
            "health_status",
            "health_reason",
            "health_metrics",
            "role",
            "quality_level",
            "speed_level",
            "cost_level",
            "privacy_level",
            "context_window",
            "input_token_price_per_1m",
            "output_token_price_per_1m",
            "average_latency_ms",
            "timeout_seconds",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_health_status(self, instance):
        return evaluate_model_health(provider=instance.provider, model_name=instance.name).status

    def get_health_reason(self, instance):
        return evaluate_model_health(provider=instance.provider, model_name=instance.name).reason

    def get_health_metrics(self, instance):
        return serialize_model_health_status(
            evaluate_model_health(provider=instance.provider, model_name=instance.name)
        )

    def validate(self, attrs):
        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        credential = attrs.get(
            "provider_credential",
            getattr(self.instance, "provider_credential", None),
        )
        if credential is not None and credential.provider != provider:
            raise serializers.ValidationError(
                {"provider_credential": "Credential provider must match the model provider."}
            )
        privacy_level = attrs.get("privacy_level", getattr(self.instance, "privacy_level", "local"))
        if provider == "ollama" and credential is not None and privacy_level == "local":
            raise serializers.ValidationError(
                {"privacy_level": "Remote Ollama models that use credentials must be marked as external."}
            )
        return attrs


class EvaluationDatasetSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True, allow_null=True)
    LEGACY_DATASET_TYPE_MAP = {
        "mmlu": ("multiple_choice", "mmlu", "jsonl"),
        "custom_mcq": ("multiple_choice", "custom", "jsonl"),
        "jsonl": ("multiple_choice", "custom", "jsonl"),
        "csv": ("multiple_choice", "custom", "csv"),
    }

    class Meta:
        model = EvaluationDataset
        fields = [
            "id",
            "name",
            "dataset_type",
            "dataset_family",
            "data_format",
            "source",
            "source_url",
            "original_filename",
            "description",
            "raw_content",
            "question_count",
            "category_schema",
            "uploaded_by",
            "uploaded_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uploaded_by", "question_count"]

    def validate(self, attrs):
        dataset_type = attrs.get("dataset_type", getattr(self.instance, "dataset_type", "multiple_choice"))
        if dataset_type in self.LEGACY_DATASET_TYPE_MAP:
            mapped_type, mapped_family, mapped_format = self.LEGACY_DATASET_TYPE_MAP[dataset_type]
            attrs["dataset_type"] = mapped_type
            attrs.setdefault("dataset_family", mapped_family)
            attrs.setdefault("data_format", mapped_format)
        source = attrs.get("source", getattr(self.instance, "source", "url"))
        source_url = attrs.get("source_url", getattr(self.instance, "source_url", ""))
        raw_content = attrs.get("raw_content", getattr(self.instance, "raw_content", ""))
        if source in ("url", "huggingface") and not source_url:
            raise serializers.ValidationError({"source_url": "URL 기반 데이터셋은 source_url이 필요합니다."})
        if source == "upload" and not raw_content:
            raise serializers.ValidationError({"raw_content": "업로드 데이터셋은 원문 내용이 필요합니다."})
        return attrs

    def create(self, validated_data):
        validated_data["question_count"] = self.count_questions(validated_data.get("raw_content", ""))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "raw_content" in validated_data:
            validated_data["question_count"] = self.count_questions(validated_data.get("raw_content", ""))
        return super().update(instance, validated_data)

    def count_questions(self, raw_content: str) -> int:
        if not raw_content:
            return 0
        return len([line for line in raw_content.splitlines() if line.strip()])


class GeneratedDatasetSerializer(serializers.ModelSerializer):
    service_feature_name = serializers.CharField(source="service_feature.name", read_only=True)
    generation_model_label = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)

    class Meta:
        model = GeneratedDataset
        fields = [
            "id",
            "service_feature",
            "service_feature_name",
            "name",
            "description",
            "dataset_type",
            "data_format",
            "status",
            "requested_question_count",
            "question_count",
            "generation_model",
            "generation_model_label",
            "few_shot_examples",
            "generation_prompt",
            "raw_content",
            "error_message",
            "metadata",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "question_count"]

    def get_generation_model_label(self, instance):
        if not instance.generation_model:
            return None
        return f"{instance.generation_model.provider}/{instance.generation_model.name}"


class EvaluationMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationMethod
        fields = [
            "id",
            "name",
            "display_name",
            "method_type",
            "description",
            "compatible_dataset_types",
            "default_config",
            "metric_schema",
            "artifact_schema",
            "is_active",
            "created_at",
            "updated_at",
        ]


class EvaluationItemResultSerializer(serializers.ModelSerializer):
    result_run_name = serializers.CharField(source="run.name", read_only=True)
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    model_display_name = serializers.CharField(source="model.display_name", read_only=True, allow_null=True)
    model_provider = serializers.CharField(source="model.provider", read_only=True, allow_null=True)
    model_name = serializers.CharField(source="model.name", read_only=True, allow_null=True)

    class Meta:
        model = EvaluationItemResult
        fields = [
            "id",
            "result",
            "run",
            "result_run_name",
            "dataset",
            "dataset_name",
            "model",
            "model_display_name",
            "model_provider",
            "model_name",
            "item_index",
            "question",
            "choices",
            "gold",
            "predicted_choice",
            "strict_ok",
            "is_correct",
            "ok",
            "attempt",
            "error",
            "input_tokens",
            "output_tokens",
            "latency_ms",
            "ttft_ms",
            "router_output",
            "raw_output",
            "subject",
            "category",
            "created_at",
        ]


class EvaluationRoutingCandidateSerializer(serializers.ModelSerializer):
    small_model_display_name = serializers.CharField(source="small_model.display_name", read_only=True, allow_null=True)
    large_model_display_name = serializers.CharField(source="large_model.display_name", read_only=True, allow_null=True)

    class Meta:
        model = EvaluationRoutingCandidate
        fields = [
            "id",
            "result",
            "routing_prompt",
            "small_model",
            "small_model_display_name",
            "large_model",
            "large_model_display_name",
            "created_at",
        ]


class EvaluationResultSerializer(serializers.ModelSerializer):
    run_name = serializers.CharField(source="run.name", read_only=True)
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    dataset_type = serializers.CharField(source="dataset.dataset_type", read_only=True)
    dataset_source = serializers.CharField(source="dataset.source", read_only=True)
    dataset_question_count = serializers.IntegerField(source="dataset.question_count", read_only=True)
    model_display_name = serializers.CharField(source="model.display_name", read_only=True, allow_null=True)
    model_provider = serializers.CharField(source="model.provider", read_only=True, allow_null=True)
    model_name = serializers.CharField(source="model.name", read_only=True, allow_null=True)
    evaluation_method_name = serializers.CharField(source="run.evaluation_method.display_name", read_only=True, allow_null=True)
    item_result_count = serializers.IntegerField(source="item_results.count", read_only=True)
    routing_config = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationResult
        fields = [
            "id",
            "run",
            "run_name",
            "dataset",
            "dataset_name",
            "dataset_type",
            "dataset_source",
            "dataset_question_count",
            "model",
            "model_display_name",
            "model_provider",
            "model_name",
            "result_type",
            "candidate_label",
            "routing_model_distribution",
            "router_latency_p50_ms",
            "router_latency_p95_ms",
            "routing_config",
            "evaluation_method_name",
            "status",
            "overall_accuracy",
            "strict_compliance_rate",
            "failure_rate",
            "parse_failure_rate",
            "latency_p50_ms",
            "latency_p95_ms",
            "ttft_p50_ms",
            "ttft_p95_ms",
            "tpot_p50_ms",
            "tpot_p95_ms",
            "throughput_p50_tps",
            "throughput_p95_tps",
            "system_throughput_tps",
            "kv_cache_usage_min",
            "kv_cache_usage_avg",
            "kv_cache_usage_max",
            "input_tokens",
            "output_tokens",
            "estimated_cost_usd",
            "category_accuracy",
            "subject_accuracy",
            "scorecard",
            "item_result_count",
            "error_message",
            "created_at",
            "updated_at",
        ]

    def get_routing_config(self, result):
        routing_config = getattr(result, "routing_config", None)
        if routing_config is None:
            return None
        return EvaluationRoutingCandidateSerializer(routing_config).data


class EvaluationRoutingCandidateInputSerializer(serializers.Serializer):
    """실험 생성 화면에서 라우팅 후보 하나를 입력받는 쓰기 전용 형태.

    PoC 범위: 후보 모델은 Small/Large 둘로 고정, Router는 항상 Small Model이 맡습니다."""

    display_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    routing_prompt = serializers.CharField()
    small_model = serializers.PrimaryKeyRelatedField(queryset=LLMModel.objects.filter(is_active=True))
    large_model = serializers.PrimaryKeyRelatedField(queryset=LLMModel.objects.filter(is_active=True))


class EvaluationRunSerializer(serializers.ModelSerializer):
    model_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )
    # 라우팅 후보(Small/Large 모델 + Routing Prompt) — 단일 모델 후보(model_ids)와 자유롭게 섞을 수 있음.
    routing_candidates = EvaluationRoutingCandidateInputSerializer(many=True, write_only=True, required=False, default=list)
    # Easy/Hard 비율 샘플링을 위한 입력. 지정하지 않으면 기존과 동일하게(난이도 구분 없이) 문항을 뽑습니다.
    easy_ratio = serializers.IntegerField(write_only=True, required=False, allow_null=True, min_value=0, max_value=100)
    # 단일 데이터셋 모드에서만 필요. Easy/Hard 데이터셋 조합 모드에서는 생략하면 easy_dataset으로 자동 채워집니다.
    dataset = serializers.PrimaryKeyRelatedField(queryset=EvaluationDataset.objects.all(), required=False)
    # Easy/Hard 데이터셋 조합 모드 — 두 데이터셋을 각각 통째로 easy/hard 풀로 취급해 easy_ratio만큼 뽑습니다.
    easy_dataset = serializers.PrimaryKeyRelatedField(
        queryset=EvaluationDataset.objects.all(), required=False, allow_null=True
    )
    hard_dataset = serializers.PrimaryKeyRelatedField(
        queryset=EvaluationDataset.objects.all(), required=False, allow_null=True
    )
    easy_dataset_name = serializers.CharField(source="easy_dataset.name", read_only=True, allow_null=True)
    hard_dataset_name = serializers.CharField(source="hard_dataset.name", read_only=True, allow_null=True)
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    dataset_type = serializers.CharField(source="dataset.dataset_type", read_only=True)
    dataset_question_count = serializers.IntegerField(source="dataset.question_count", read_only=True)
    evaluation_method_name = serializers.CharField(source="evaluation_method.display_name", read_only=True, allow_null=True)
    evaluation_method_type = serializers.CharField(source="evaluation_method.method_type", read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)
    results = EvaluationResultSerializer(many=True, read_only=True)

    class Meta:
        model = EvaluationRun
        fields = [
            "id",
            "name",
            "dataset",
            "dataset_name",
            "dataset_type",
            "dataset_question_count",
            "easy_dataset",
            "easy_dataset_name",
            "hard_dataset",
            "hard_dataset_name",
            "easy_ratio",
            "evaluation_method",
            "evaluation_method_name",
            "evaluation_method_type",
            "model_ids",
            "routing_candidates",
            "status",
            "config",
            "notes",
            "created_by",
            "created_by_username",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "results",
        ]
        read_only_fields = ["created_by", "status", "started_at", "completed_at"]

    def validate_evaluation_method(self, value):
        if value is not None and not value.is_active:
            raise serializers.ValidationError("활성 평가방식만 선택할 수 있습니다.")
        return value

    def validate(self, attrs):
        dataset = attrs.get("dataset", getattr(self.instance, "dataset", None))
        easy_dataset = attrs.get("easy_dataset", getattr(self.instance, "easy_dataset", None))
        hard_dataset = attrs.get("hard_dataset", getattr(self.instance, "hard_dataset", None))
        if self.instance is None:
            if bool(easy_dataset) != bool(hard_dataset):
                raise serializers.ValidationError("Easy 데이터셋과 Hard 데이터셋을 모두 지정해야 합니다.")
            if not dataset and not (easy_dataset and hard_dataset):
                raise serializers.ValidationError("데이터셋 또는 Easy/Hard 데이터셋 조합을 지정해야 합니다.")

        effective_dataset = easy_dataset if (easy_dataset and hard_dataset) else dataset
        method = attrs.get("evaluation_method", getattr(self.instance, "evaluation_method", None))
        if method and effective_dataset and method.compatible_dataset_types:
            compatible_type_keys = getattr(effective_dataset, "compatible_type_keys", {effective_dataset.dataset_type})
            if compatible_type_keys.isdisjoint(set(method.compatible_dataset_types)):
                raise serializers.ValidationError(
                    {"evaluation_method": "선택한 평가방식은 이 데이터셋 유형과 호환되지 않습니다."}
                )
        if self.instance is None:
            model_ids = attrs.get("model_ids") or []
            routing_candidates = attrs.get("routing_candidates") or []
            if not model_ids and not routing_candidates:
                raise serializers.ValidationError("단일 모델 후보 또는 라우팅 후보를 1개 이상 지정해야 합니다.")
        return attrs

    def validate_model_ids(self, value):
        existing_ids = set(LLMModel.objects.filter(id__in=value, is_active=True).values_list("id", flat=True))
        missing = [model_id for model_id in value if model_id not in existing_ids]
        if missing:
            raise serializers.ValidationError(f"활성 모델을 찾을 수 없습니다: {missing}")
        return value

    def create(self, validated_data):
        from apps.catalog.evaluation import PilotEvaluationRunner

        model_ids = validated_data.pop("model_ids", [])
        routing_candidates = validated_data.pop("routing_candidates", [])
        easy_ratio = validated_data.pop("easy_ratio", None)
        easy_dataset = validated_data.get("easy_dataset")
        hard_dataset = validated_data.get("hard_dataset")
        if easy_dataset and hard_dataset and not validated_data.get("dataset"):
            validated_data["dataset"] = easy_dataset
        if validated_data.get("evaluation_method") is None:
            validated_data["evaluation_method"] = EvaluationMethod.objects.filter(name="mmlu_multiple_choice", is_active=True).first()
        run = EvaluationRun.objects.create(**validated_data)
        selected_models = list(LLMModel.objects.filter(id__in=model_ids, is_active=True))
        run.models.set(selected_models)
        for model in selected_models:
            EvaluationResult.objects.create(
                run=run,
                dataset=run.dataset,
                model=model,
                result_type="single_model",
                status="pending",
                scorecard={
                    "quality_level": model.quality_level,
                    "speed_level": model.speed_level,
                    "cost_level": model.cost_level,
                    "note": "평가 실행 기록이 생성되었습니다. 실제 추론 평가 worker가 완료되면 지표가 업데이트됩니다.",
                },
            )
        for candidate in routing_candidates:
            small_model = candidate["small_model"]
            large_model = candidate["large_model"]
            display_name = candidate.get("display_name") or f"Routing: {small_model.display_name} / {large_model.display_name}"
            result = EvaluationResult.objects.create(
                run=run,
                dataset=run.dataset,
                model=None,
                result_type="routing",
                candidate_label=display_name,
                status="pending",
                scorecard={"note": "라우팅 실험 후보가 생성되었습니다. 실행 후 지표가 업데이트됩니다."},
            )
            EvaluationRoutingCandidate.objects.create(
                result=result,
                routing_prompt=candidate["routing_prompt"],
                small_model=small_model,
                large_model=large_model,
            )
        # 실험 생성 시점에 문항을 확정해서 스냅샷으로 저장합니다 — 이후 재실행해도
        # 원본 데이터셋이 바뀌는 것과 무관하게 항상 같은 문항으로 재현됩니다.
        PilotEvaluationRunner().build_dataset_snapshot(
            run=run,
            dataset=run.dataset,
            easy_dataset=run.easy_dataset,
            hard_dataset=run.hard_dataset,
            easy_ratio=easy_ratio,
            seed=run.config.get("seed"),
            total_questions=run.config.get("total_questions") or run.config.get("max_questions"),
        )
        return run


class RoutingPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutingPolicy
        fields = [
            "id",
            "name",
            "display_name",
            "description",
            "priority_config",
            "is_active",
        ]


class RoutingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutingRule
        fields = [
            "id",
            "rule_id",
            "name",
            "description",
            "condition_key",
            "target_tier",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ThresholdRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThresholdRule
        fields = [
            "id",
            "rule_id",
            "name",
            "description",
            "metric_key",
            "operator",
            "threshold_value",
            "action_on_trigger",
            "target_tier",
            "max_tokens",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        action = attrs.get("action_on_trigger", getattr(self.instance, "action_on_trigger", "prefer_tier"))
        target_tier = attrs.get("target_tier", getattr(self.instance, "target_tier", ""))
        max_tokens = attrs.get("max_tokens", getattr(self.instance, "max_tokens", None))
        if action == "prefer_tier" and not target_tier:
            raise serializers.ValidationError({"target_tier": "Target tier is required for prefer_tier action."})
        if action == "set_max_tokens" and max_tokens is None:
            raise serializers.ValidationError({"max_tokens": "Max tokens is required for set_max_tokens action."})
        return attrs


class ResponseValidationRuleSerializer(serializers.ModelSerializer):
    recovery_strategy_display_name = serializers.CharField(
        source="recovery_strategy.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ResponseValidationRule
        fields = [
            "id",
            "rule_id",
            "name",
            "description",
            "recovery_strategy",
            "recovery_strategy_display_name",
            "condition_key",
            "validation_type",
            "action_on_fail",
            "retry_prompt",
            "max_retries",
            "target_tier",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        action = attrs.get("action_on_fail", getattr(self.instance, "action_on_fail", "strict_retry"))
        target_tier = attrs.get("target_tier", getattr(self.instance, "target_tier", ""))
        if action == "escalate" and not target_tier:
            raise serializers.ValidationError({"target_tier": "Target tier is required for escalation."})
        return attrs


class RecoveryStrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecoveryStrategy
        fields = [
            "id",
            "strategy_id",
            "name",
            "description",
            "trigger_event",
            "action",
            "retry_prompt",
            "max_retries",
            "target_tier",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        action = attrs.get("action", getattr(self.instance, "action", "strict_retry"))
        target_tier = attrs.get("target_tier", getattr(self.instance, "target_tier", ""))
        if action == "escalate" and not target_tier:
            raise serializers.ValidationError({"target_tier": "Target tier is required for escalation."})
        return attrs


class ModelHealthEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelHealthEvent
        fields = [
            "id",
            "event_type",
            "provider",
            "model_name",
            "status",
            "rule",
            "rule_name",
            "reason",
            "request_count",
            "failures",
            "failure_rate",
            "average_latency_ms",
            "created_at",
        ]


class ModelHealthOverrideSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)

    class Meta:
        model = ModelHealthOverride
        fields = [
            "id",
            "name",
            "provider",
            "model_name",
            "override_type",
            "reason",
            "expires_at",
            "is_active",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by"]


class ProviderCredentialSerializer(serializers.ModelSerializer):
    base_url = serializers.CharField(allow_blank=True, write_only=False)
    access_token = serializers.CharField(allow_blank=True, write_only=True, required=False)
    access_token_masked = serializers.SerializerMethodField()

    class Meta:
        model = ProviderCredential
        fields = [
            "id",
            "provider",
            "display_name",
            "base_url",
            "access_token",
            "access_token_masked",
            "last_used_at",
            "token_rotated_at",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["base_url"] = instance.get_base_url()
        return data

    def get_access_token_masked(self, instance):
        token = instance.get_access_token()
        if not token:
            return ""
        if len(token) <= 8:
            return "********"
        return f"{token[:4]}********{token[-4:]}"

    def create(self, validated_data):
        base_url = validated_data.pop("base_url", "")
        access_token = validated_data.pop("access_token", "")
        credential = ProviderCredential(**validated_data)
        credential.set_base_url(base_url)
        credential.set_access_token(access_token)
        credential.save()
        return credential

    def update(self, instance, validated_data):
        base_url = validated_data.pop("base_url", None)
        access_token = validated_data.pop("access_token", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if base_url is not None:
            instance.set_base_url(base_url)
        if access_token:
            instance.set_access_token(access_token)
            instance.token_rotated_at = timezone.now()
        instance.save()
        return instance


class UsageQuotaSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True, allow_null=True)
    period_start = serializers.SerializerMethodField()
    current_month_requests = serializers.SerializerMethodField()
    current_month_cost_usd = serializers.SerializerMethodField()
    request_usage_ratio = serializers.SerializerMethodField()
    cost_usage_ratio = serializers.SerializerMethodField()
    is_exceeded = serializers.SerializerMethodField()

    class Meta:
        model = UsageQuota
        fields = [
            "id",
            "name",
            "user",
            "username",
            "provider",
            "monthly_request_limit",
            "monthly_cost_limit_usd",
            "period_start",
            "current_month_requests",
            "current_month_cost_usd",
            "request_usage_ratio",
            "cost_usage_ratio",
            "is_exceeded",
            "action_on_exceed",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_usage(self, instance):
        if not hasattr(instance, "_quota_usage"):
            instance._quota_usage = get_quota_usage(instance)
        return instance._quota_usage

    def get_period_start(self, instance):
        return self.get_usage(instance)["period_start"]

    def get_current_month_requests(self, instance):
        return self.get_usage(instance)["current_month_requests"]

    def get_current_month_cost_usd(self, instance):
        return self.get_usage(instance)["current_month_cost_usd"]

    def get_request_usage_ratio(self, instance):
        value = self.get_usage(instance)["request_usage_ratio"]
        return None if value is None else round(float(value), 4)

    def get_cost_usage_ratio(self, instance):
        value = self.get_usage(instance)["cost_usage_ratio"]
        return None if value is None else round(float(value), 4)

    def get_is_exceeded(self, instance):
        return self.get_usage(instance)["is_exceeded"]

    def validate(self, attrs):
        monthly_request_limit = attrs.get(
            "monthly_request_limit",
            getattr(self.instance, "monthly_request_limit", None),
        )
        monthly_cost_limit_usd = attrs.get(
            "monthly_cost_limit_usd",
            getattr(self.instance, "monthly_cost_limit_usd", None),
        )
        if monthly_request_limit is None and monthly_cost_limit_usd is None:
            raise serializers.ValidationError("At least one monthly limit is required.")
        return attrs


class ServiceFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceFeature
        fields = [
            "id",
            "name",
            "description",
            "required_tier",
            "routing_path",
            "condition_key",
            "main_metrics",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PolicyDraftSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)

    class Meta:
        model = PolicyDraft
        fields = [
            "id",
            "name",
            "preset",
            "selected_model_ids",
            "tier_assignments",
            "feature_model_map",
            "routing_rules",
            "threshold_rules",
            "validation_rules",
            "recovery_strategies",
            "summary_text",
            "missing_coverage",
            "is_saved",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by"]


class ModelHealthRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelHealthRule
        fields = [
            "id",
            "name",
            "provider",
            "model_name",
            "window_minutes",
            "min_requests",
            "max_failure_rate_percent",
            "max_average_latency_ms",
            "action_on_trigger",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        failure_rate = attrs.get(
            "max_failure_rate_percent",
            getattr(self.instance, "max_failure_rate_percent", None),
        )
        latency = attrs.get(
            "max_average_latency_ms",
            getattr(self.instance, "max_average_latency_ms", None),
        )
        if failure_rate is None and latency is None:
            raise serializers.ValidationError("At least one health threshold is required.")
        return attrs
