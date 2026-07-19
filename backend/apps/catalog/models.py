from django.db import models
from django.conf import settings


class LLMModel(models.Model):
    PROVIDER_CHOICES = [
        ("ollama", "Ollama"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("openrouter", "OpenRouter"),
        ("anthropic", "Anthropic"),
        ("vllm", "vLLM"),
    ]
    ROLE_CHOICES = [
        ("general", "General"),
        ("coding", "Coding"),
        ("reasoning", "Reasoning"),
        ("summary", "Summary"),
    ]
    TIER_CHOICES = [
        ("lightweight", "Lightweight"),
        ("standard", "Standard"),
        ("advanced", "Advanced"),
        ("long_context", "Long Context"),
        ("structured", "Structured"),
    ]
    PRIVACY_CHOICES = [
        ("local", "Local"),
        ("external", "External"),
    ]

    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    name = models.CharField(max_length=120)
    display_name = models.CharField(max_length=160)
    model_tier = models.CharField(max_length=32, choices=TIER_CHOICES, default="standard")
    provider_credential = models.ForeignKey(
        "ProviderCredential",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="models",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="general")
    quality_level = models.PositiveSmallIntegerField(default=3)
    speed_level = models.PositiveSmallIntegerField(default=3)
    cost_level = models.PositiveSmallIntegerField(default=1)
    privacy_level = models.CharField(max_length=32, choices=PRIVACY_CHOICES, default="local")
    context_window = models.PositiveIntegerField(default=8192)
    input_token_price_per_1m = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    output_token_price_per_1m = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    average_latency_ms = models.PositiveIntegerField(default=0)
    timeout_seconds = models.PositiveIntegerField(default=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "name"]
        unique_together = ("provider", "name")

    def __str__(self):
        return f"{self.provider}/{self.name}"

    def to_candidate(self):
        from apps.catalog.entities import LLMModelCandidate

        # 정책 엔진이 Django 모델에 직접 의존하지 않도록 DB row를 작은 불변 후보 객체로
        # 변환한 뒤 라우팅에 사용합니다.
        return LLMModelCandidate(
            provider=self.provider,
            name=self.name,
            model_tier=self.model_tier,
            role=self.role,
            quality_level=self.quality_level,
            speed_level=self.speed_level,
            cost_level=self.cost_level,
            privacy_level=self.privacy_level,
            context_window=self.context_window,
            input_token_price_per_1m=self.input_token_price_per_1m,
            output_token_price_per_1m=self.output_token_price_per_1m,
            average_latency_ms=self.average_latency_ms,
            timeout_seconds=self.timeout_seconds,
        )


class EvaluationDataset(models.Model):
    DATASET_TYPE_CHOICES = [
        ("multiple_choice", "Multiple Choice"),
        ("qa", "Question Answering"),
        ("generation", "Generation/Summarization"),
        ("rag", "Retrieval-Augmented Generation"),
        ("safety_classification", "Safety/Classification"),
        ("custom", "Custom"),
        ("mmlu", "MMLU (legacy)"),
        ("custom_mcq", "Custom Multiple Choice (legacy)"),
        ("jsonl", "JSONL (legacy)"),
        ("csv", "CSV (legacy)"),
    ]
    DATASET_FAMILY_CHOICES = [
        ("mmlu", "MMLU"),
        ("custom", "Custom"),
        ("humaneval", "HumanEval"),
        ("gsm8k", "GSM8K"),
        ("other", "Other"),
    ]
    DATA_FORMAT_CHOICES = [
        ("jsonl", "JSONL"),
        ("csv", "CSV"),
        ("json", "JSON"),
        ("txt", "TXT"),
        ("unknown", "Unknown"),
    ]
    SOURCE_CHOICES = [
        ("upload", "Upload"),
        ("url", "URL"),
        ("huggingface", "Hugging Face"),
        ("generated", "Generated Dataset"),
    ]

    name = models.CharField(max_length=160)
    dataset_type = models.CharField(max_length=32, choices=DATASET_TYPE_CHOICES, default="multiple_choice")
    dataset_family = models.CharField(max_length=32, choices=DATASET_FAMILY_CHOICES, default="custom")
    data_format = models.CharField(max_length=32, choices=DATA_FORMAT_CHOICES, default="jsonl")
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default="url")
    source_url = models.URLField(blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    raw_content = models.TextField(blank=True)
    question_count = models.PositiveIntegerField(default=0)
    category_schema = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluation_datasets",
    )
    # 생성 데이터셋(GeneratedDataset)이 완료되면 자동으로 동기화되는 대상. 수동 업로드 데이터셋은 null.
    source_generated_dataset = models.OneToOneField(
        "GeneratedDataset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluation_dataset",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self):
        return self.name

    @property
    def compatible_type_keys(self):
        keys = {self.dataset_type}
        if self.dataset_type == "multiple_choice":
            keys.add("custom_mcq")
        if self.dataset_family == "mmlu":
            keys.add("mmlu")
        if self.data_format in {"jsonl", "csv"}:
            keys.add(self.data_format)
        return keys


class EvaluationMethod(models.Model):
    METHOD_TYPE_CHOICES = [
        ("multiple_choice", "Multiple Choice"),
        ("generation", "Generation"),
        ("retrieval", "Retrieval"),
        ("custom", "Custom"),
    ]

    name = models.SlugField(max_length=80, unique=True)
    display_name = models.CharField(max_length=160)
    method_type = models.CharField(max_length=32, choices=METHOD_TYPE_CHOICES, default="multiple_choice")
    description = models.TextField(blank=True)
    compatible_dataset_types = models.JSONField(default=list, blank=True)
    default_config = models.JSONField(default=dict, blank=True)
    metric_schema = models.JSONField(default=dict, blank=True)
    artifact_schema = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "name"]

    def __str__(self):
        return self.display_name


class EvaluationRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    name = models.CharField(max_length=160)
    dataset = models.ForeignKey(EvaluationDataset, on_delete=models.CASCADE, related_name="runs")
    # Easy/Hard 데이터셋 조합 모드에서만 사용됩니다. 둘 다 지정되면 위 dataset은
    # easy_dataset과 동일한 값으로 자동 채워지는 대표값입니다.
    easy_dataset = models.ForeignKey(
        EvaluationDataset, null=True, blank=True, on_delete=models.CASCADE, related_name="easy_runs"
    )
    hard_dataset = models.ForeignKey(
        EvaluationDataset, null=True, blank=True, on_delete=models.CASCADE, related_name="hard_runs"
    )
    evaluation_method = models.ForeignKey(
        EvaluationMethod,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="runs",
    )
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    config = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluation_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    models = models.ManyToManyField(LLMModel, related_name="evaluation_runs")

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self):
        return self.name


class EvaluationDatasetSnapshot(models.Model):
    """실험(run) 생성 시점에 문항을 확정해서 통째로 복제 저장합니다.

    EvaluationDataset은 raw_content 텍스트 blob을 매번 다시 파싱하는 구조라 안정적인
    문항 ID가 없습니다. 원본 데이터셋이 나중에 바뀌어도 이 실험은 항상 그때 그 문항으로
    재현되도록, 인덱스가 아니라 문항 내용 자체를 questions_payload에 복제해 둡니다."""

    run = models.OneToOneField(EvaluationRun, on_delete=models.CASCADE, related_name="dataset_snapshot")
    dataset = models.ForeignKey(EvaluationDataset, on_delete=models.PROTECT, related_name="snapshots")
    # Easy/Hard 데이터셋 조합 모드에서만 사용됩니다(재현성 보존용 참조).
    easy_dataset = models.ForeignKey(
        EvaluationDataset, null=True, blank=True, on_delete=models.PROTECT, related_name="easy_snapshots"
    )
    hard_dataset = models.ForeignKey(
        EvaluationDataset, null=True, blank=True, on_delete=models.PROTECT, related_name="hard_snapshots"
    )
    # None/미지정 = 난이도 구분 없이 기존 방식대로 시드 셔플만 적용(하위호환).
    easy_ratio = models.PositiveSmallIntegerField(null=True, blank=True)
    seed = models.PositiveIntegerField()
    total_questions = models.PositiveIntegerField()
    # [{"question":..., "choices":[...], "answer":"B", "category":"...", "subject":"...", "difficulty":"easy"}, ...]
    questions_payload = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"snapshot for {self.run_id}"


class EvaluationResult(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    RESULT_TYPE_CHOICES = [
        ("single_model", "Single Model"),
        ("routing", "Routing"),
    ]

    run = models.ForeignKey(EvaluationRun, on_delete=models.CASCADE, related_name="results")
    dataset = models.ForeignKey(EvaluationDataset, on_delete=models.CASCADE, related_name="results")
    # routing 타입은 고정된 모델이 없으므로(문항마다 달라짐) null 허용.
    model = models.ForeignKey(LLMModel, on_delete=models.CASCADE, related_name="evaluation_results", null=True, blank=True)
    result_type = models.CharField(max_length=32, choices=RESULT_TYPE_CHOICES, default="single_model")
    # routing 타입 결과의 표시 이름(단일 모델 타입은 model.display_name을 그대로 씀).
    candidate_label = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    overall_accuracy = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    strict_compliance_rate = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    failure_rate = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    parse_failure_rate = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    latency_p50_ms = models.PositiveIntegerField(null=True, blank=True)
    latency_p95_ms = models.PositiveIntegerField(null=True, blank=True)
    ttft_p50_ms = models.PositiveIntegerField(null=True, blank=True)
    ttft_p95_ms = models.PositiveIntegerField(null=True, blank=True)
    tpot_p50_ms = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tpot_p95_ms = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    throughput_p50_tps = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    throughput_p95_tps = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    system_throughput_tps = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kv_cache_usage_min = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    kv_cache_usage_avg = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    kv_cache_usage_max = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    # routing 타입 전용 — 문항이 실제로 small/large 중 어디로 갔는지 분포.
    # 예: {"small": {"count": 72, "percent": 72.0}, "large": {"count": 28, "percent": 28.0}}
    routing_model_distribution = models.JSONField(default=dict, blank=True)
    # routing 타입 전용 — 라우터(Small Model) 판단 호출 자체의 지연시간(문항 채점 호출과 별개).
    router_latency_p50_ms = models.PositiveIntegerField(null=True, blank=True)
    router_latency_p95_ms = models.PositiveIntegerField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    category_accuracy = models.JSONField(default=dict, blank=True)
    subject_accuracy = models.JSONField(default=dict, blank=True)
    scorecard = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("run", "model")

    def __str__(self):
        return f"{self.run} - {self.model}"


class EvaluationItemResult(models.Model):
    result = models.ForeignKey(EvaluationResult, on_delete=models.CASCADE, related_name="item_results")
    run = models.ForeignKey(EvaluationRun, on_delete=models.CASCADE, related_name="item_results")
    dataset = models.ForeignKey(EvaluationDataset, on_delete=models.CASCADE, related_name="item_results")
    # "이 문항에 실제로 응답한 모델" — single_model 타입은 항상 result.model과 같고,
    # routing 타입은 문항마다 small/large 중 실제로 뽑힌 모델이 들어갑니다.
    model = models.ForeignKey(LLMModel, on_delete=models.SET_NULL, related_name="evaluation_item_results", null=True, blank=True)
    item_index = models.PositiveIntegerField(default=0)
    question = models.TextField()
    choices = models.JSONField(default=list, blank=True)
    gold = models.CharField(max_length=16, blank=True)
    predicted_choice = models.CharField(max_length=16, blank=True)
    strict_ok = models.BooleanField(default=False)
    is_correct = models.BooleanField(default=False)
    ok = models.BooleanField(default=False)
    attempt = models.PositiveIntegerField(default=1)
    error = models.TextField(blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    ttft_ms = models.PositiveIntegerField(null=True, blank=True)
    # routing 타입 전용 — 라우터(항상 Small Model)의 원문 응답. exact match 판정에 씁니다.
    # Router Prompt(입력)는 별도 저장하지 않고 EvaluationRoutingCandidate.routing_prompt +
    # 이 row의 question을 조합해서 화면에서 재구성합니다.
    router_output = models.TextField(blank=True)
    raw_output = models.TextField(blank=True)
    subject = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["result_id", "item_index", "attempt"]
        indexes = [
            models.Index(fields=["run", "model"]),
            models.Index(fields=["result", "item_index"]),
        ]

    def __str__(self):
        return f"{self.result_id} item {self.item_index} attempt {self.attempt}"


class EvaluationRoutingCandidate(models.Model):
    """routing 타입 EvaluationResult 하나에 붙는 라우팅 설정.

    PoC 범위: 후보 모델은 Small/Large 둘로 고정하고, Router는 항상 Small Model이 맡습니다
    (별도 Router Model 선택 없음). 향후 Router Model을 선택 가능하게 하려면 이 모델에
    nullable `router_model` FK를 추가하고 "없으면 small_model을 쓴다"는 fallback만 넣으면
    되므로, 지금 스키마를 깨지 않고 확장할 수 있습니다."""

    result = models.OneToOneField(EvaluationResult, on_delete=models.CASCADE, related_name="routing_config")
    routing_prompt = models.TextField()
    small_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    large_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"routing config for {self.result_id}"


class RoutingPolicy(models.Model):
    name = models.SlugField(max_length=64, unique=True)
    display_name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    priority_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name


class RoutingRule(models.Model):
    CONDITION_CHOICES = [
        ("general", "General/simple query"),
        ("code", "Code or technical request"),
        ("reasoning", "Reasoning request"),
        ("long_context", "Long context request"),
        ("structured_output", "SQL/JSON structured output"),
        ("sensitive", "Sensitive data request"),
        ("always", "Always"),
    ]
    TARGET_TIER_CHOICES = LLMModel.TIER_CHOICES

    rule_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    condition_key = models.CharField(max_length=32, choices=CONDITION_CHOICES, default="general")
    target_tier = models.CharField(max_length=32, choices=TARGET_TIER_CHOICES)
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "rule_id"]

    def __str__(self):
        return f"{self.rule_id} - {self.name}"


class ThresholdRule(models.Model):
    METRIC_CHOICES = [
        ("estimated_tokens", "Estimated tokens"),
        ("p95_latency_ms", "p95 latency ms"),
        ("timeout_seconds", "Timeout seconds"),
        ("parse_fail_rate", "Parse fail rate"),
        ("failure_rate", "Failure rate"),
    ]
    OPERATOR_CHOICES = [
        ("gte", ">="),
        ("lte", "<="),
    ]
    ACTION_CHOICES = [
        ("prefer_tier", "Prefer model tier"),
        ("set_max_tokens", "Set max tokens"),
    ]
    TARGET_TIER_CHOICES = LLMModel.TIER_CHOICES

    rule_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    metric_key = models.CharField(max_length=32, choices=METRIC_CHOICES, default="estimated_tokens")
    operator = models.CharField(max_length=8, choices=OPERATOR_CHOICES, default="gte")
    threshold_value = models.DecimalField(max_digits=12, decimal_places=4)
    action_on_trigger = models.CharField(max_length=32, choices=ACTION_CHOICES, default="prefer_tier")
    target_tier = models.CharField(max_length=32, choices=TARGET_TIER_CHOICES, blank=True, default="")
    max_tokens = models.PositiveIntegerField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "rule_id"]

    def __str__(self):
        return f"{self.rule_id} - {self.name}"


class ResponseValidationRule(models.Model):
    CONDITION_CHOICES = RoutingRule.CONDITION_CHOICES
    VALIDATION_CHOICES = [
        ("non_empty", "Non-empty response"),
        ("json", "JSON parse validation"),
        ("sql", "SQL format validation"),
    ]
    ACTION_CHOICES = [
        ("strict_retry", "Strict retry"),
        ("fallback", "Fallback"),
        ("escalate", "Escalate to tier"),
        ("block", "Block response"),
    ]
    TARGET_TIER_CHOICES = LLMModel.TIER_CHOICES

    rule_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    recovery_strategy = models.ForeignKey(
        "RecoveryStrategy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="validation_rules",
    )
    condition_key = models.CharField(max_length=32, choices=CONDITION_CHOICES, default="structured_output")
    validation_type = models.CharField(max_length=32, choices=VALIDATION_CHOICES, default="json")
    action_on_fail = models.CharField(max_length=32, choices=ACTION_CHOICES, default="strict_retry")
    retry_prompt = models.TextField(blank=True)
    max_retries = models.PositiveIntegerField(default=1)
    target_tier = models.CharField(max_length=32, choices=TARGET_TIER_CHOICES, blank=True, default="")
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "rule_id"]

    def __str__(self):
        return f"{self.rule_id} - {self.name}"


class RecoveryStrategy(models.Model):
    TRIGGER_CHOICES = [
        ("validation_fail", "Validation failure"),
        ("timeout", "Timeout"),
        ("api_fail", "API failure"),
        ("parse_fail", "Parse failure"),
        ("low_confidence", "Low confidence"),
    ]
    ACTION_CHOICES = ResponseValidationRule.ACTION_CHOICES
    TARGET_TIER_CHOICES = LLMModel.TIER_CHOICES

    strategy_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    trigger_event = models.CharField(max_length=32, choices=TRIGGER_CHOICES, default="validation_fail")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default="strict_retry")
    retry_prompt = models.TextField(blank=True)
    max_retries = models.PositiveIntegerField(default=1)
    target_tier = models.CharField(max_length=32, choices=TARGET_TIER_CHOICES, blank=True, default="")
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "strategy_id"]

    def __str__(self):
        return f"{self.strategy_id} - {self.name}"


class ProviderCredential(models.Model):
    PROVIDER_CHOICES = [
        ("ollama", "Ollama"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("openrouter", "OpenRouter"),
        ("anthropic", "Anthropic"),
        ("vllm", "vLLM"),
    ]

    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    display_name = models.CharField(max_length=120)
    encrypted_base_url = models.TextField(blank=True)
    encrypted_access_token = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    token_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider"]

    def __str__(self):
        return self.display_name

    @property
    def base_url(self) -> str:
        return self.get_base_url()

    @base_url.setter
    def base_url(self, value: str):
        self.set_base_url(value)

    @property
    def access_token(self) -> str:
        return self.get_access_token()

    @access_token.setter
    def access_token(self, value: str):
        self.set_access_token(value)

    def set_base_url(self, value: str):
        from apps.catalog.crypto import encrypt_value

        self.encrypted_base_url = encrypt_value(value)

    def get_base_url(self) -> str:
        from apps.catalog.crypto import decrypt_value

        return decrypt_value(self.encrypted_base_url)

    def set_access_token(self, value: str):
        from apps.catalog.crypto import encrypt_value

        self.encrypted_access_token = encrypt_value(value)

    def get_access_token(self) -> str:
        from apps.catalog.crypto import decrypt_value

        return decrypt_value(self.encrypted_access_token)

    def mark_used(self):
        from django.utils import timezone

        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])


class UsageQuota(models.Model):
    ACTION_CHOICES = [
        ("block", "Block request"),
        ("local_fallback", "Fallback to local"),
    ]
    PROVIDER_CHOICES = [
        ("", "All providers"),
        ("ollama", "Ollama"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("openrouter", "OpenRouter"),
    ]

    name = models.CharField(max_length=120)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="usage_quotas",
    )
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, blank=True, default="")
    monthly_request_limit = models.PositiveIntegerField(null=True, blank=True)
    monthly_cost_limit_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    action_on_exceed = models.CharField(max_length=32, choices=ACTION_CHOICES, default="local_fallback")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ModelHealthRule(models.Model):
    PROVIDER_CHOICES = [
        ("", "All providers"),
        ("ollama", "Ollama"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("openrouter", "OpenRouter"),
    ]
    ACTION_CHOICES = [
        ("exclude", "Exclude from routing"),
    ]

    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, blank=True, default="")
    model_name = models.CharField(max_length=120, blank=True, default="")
    window_minutes = models.PositiveIntegerField(default=60)
    min_requests = models.PositiveIntegerField(default=5)
    max_failure_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_average_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    action_on_trigger = models.CharField(max_length=32, choices=ACTION_CHOICES, default="exclude")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ModelHealthEvent(models.Model):
    EVENT_CHOICES = [
        ("triggered", "Triggered"),
        ("recovered", "Recovered"),
    ]
    STATUS_CHOICES = [
        ("healthy", "Healthy"),
        ("unhealthy", "Unhealthy"),
    ]

    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    provider = models.CharField(max_length=32)
    model_name = models.CharField(max_length=120)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    rule = models.ForeignKey(
        ModelHealthRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    rule_name = models.CharField(max_length=120, blank=True, default="")
    reason = models.TextField(blank=True)
    request_count = models.PositiveIntegerField(default=0)
    failures = models.PositiveIntegerField(default=0)
    failure_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    average_latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}/{self.model_name} {self.event_type}"


class ServiceFeature(models.Model):
    TIER_CHOICES = LLMModel.TIER_CHOICES
    PATH_CHOICES = [
        ("lightweight", "Lightweight Path"),
        ("standard", "Standard Path"),
        ("advanced", "Advanced Path"),
        ("long_context", "Long Context Path"),
        ("structured", "Structured Path"),
        ("escalation", "Escalation Path"),
        ("fallback", "Fallback Path"),
    ]
    CONDITION_CHOICES = RoutingRule.CONDITION_CHOICES

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    required_tier = models.CharField(max_length=32, choices=TIER_CHOICES, default="standard")
    routing_path = models.CharField(max_length=32, choices=PATH_CHOICES, default="standard")
    condition_key = models.CharField(max_length=32, choices=CONDITION_CHOICES, default="general")
    main_metrics = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class GeneratedDataset(models.Model):
    DATASET_TYPE_CHOICES = EvaluationDataset.DATASET_TYPE_CHOICES
    DATA_FORMAT_CHOICES = EvaluationDataset.DATA_FORMAT_CHOICES
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    service_feature = models.OneToOneField(
        ServiceFeature,
        on_delete=models.CASCADE,
        related_name="generated_dataset",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    dataset_type = models.CharField(max_length=32, choices=DATASET_TYPE_CHOICES, default="multiple_choice")
    data_format = models.CharField(max_length=32, choices=DATA_FORMAT_CHOICES, default="jsonl")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="completed")
    requested_question_count = models.PositiveIntegerField(default=0)
    question_count = models.PositiveIntegerField(default=0)
    generation_model = models.ForeignKey(
        LLMModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_datasets",
    )
    few_shot_examples = models.TextField(blank=True)
    generation_prompt = models.TextField(blank=True)
    raw_content = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_datasets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "name"]

    def __str__(self):
        return f"{self.service_feature.name} generated dataset"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == "completed":
            self.sync_evaluation_dataset()

    def sync_evaluation_dataset(self):
        EvaluationDataset.objects.update_or_create(
            source_generated_dataset=self,
            defaults={
                "name": self.name,
                "dataset_type": self.dataset_type,
                "data_format": self.data_format,
                "source": "generated",
                "description": self.description,
                "raw_content": self.raw_content,
                "question_count": self.question_count,
            },
        )


class PolicyDraft(models.Model):
    PRESET_CHOICES = [
        ("cost-first", "Cost First"),
        ("quality-first", "Quality First"),
        ("balanced", "Balanced"),
        ("privacy-first", "Privacy First"),
    ]

    name = models.CharField(max_length=120)
    preset = models.CharField(max_length=32, choices=PRESET_CHOICES, default="balanced")
    selected_model_ids = models.JSONField(default=list)
    tier_assignments = models.JSONField(default=dict)
    feature_model_map = models.JSONField(default=dict)
    routing_rules = models.JSONField(default=list)
    threshold_rules = models.JSONField(default=list)
    validation_rules = models.JSONField(default=list)
    recovery_strategies = models.JSONField(default=list)
    summary_text = models.TextField(blank=True)
    missing_coverage = models.JSONField(default=list)
    is_saved = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="policy_drafts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ModelHealthOverride(models.Model):
    OVERRIDE_CHOICES = [
        ("force_healthy", "Force healthy"),
        ("force_unhealthy", "Force unhealthy"),
    ]
    PROVIDER_CHOICES = [
        ("", "All providers"),
        ("ollama", "Ollama"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("openrouter", "OpenRouter"),
    ]

    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, blank=True, default="")
    model_name = models.CharField(max_length=120, blank=True, default="")
    override_type = models.CharField(max_length=32, choices=OVERRIDE_CHOICES)
    reason = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="model_health_overrides",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        scope = f"{self.provider or '*'}/{self.model_name or '*'}"
        return f"{scope} {self.override_type}"
