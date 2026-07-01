import time

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.audit import record_audit_log
from apps.accounts.permissions import HasScreenAccess
from apps.catalog.credentials import get_provider_access_token, get_provider_base_url
from apps.catalog.connectivity import check_models_connectivity, validate_models_available
from apps.catalog.draft import generate_draft, get_tier_recommendations, save_draft_as_policy
from apps.catalog.evaluation import PilotEvaluationRunner
from apps.catalog.provider_models import fetch_provider_models, humanize_model_name, parse_provider_models
from apps.catalog.models import (
    EvaluationDataset,
    EvaluationItemResult,
    EvaluationMethod,
    EvaluationResult,
    EvaluationRun,
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
from apps.catalog.serializers import (
    EvaluationDatasetSerializer,
    EvaluationItemResultSerializer,
    EvaluationMethodSerializer,
    EvaluationResultSerializer,
    EvaluationRunSerializer,
    LLMModelSerializer,
    ModelHealthEventSerializer,
    ModelHealthOverrideSerializer,
    ModelHealthRuleSerializer,
    PolicyDraftSerializer,
    ProviderCredentialSerializer,
    RecoveryStrategySerializer,
    ResponseValidationRuleSerializer,
    RoutingPolicySerializer,
    RoutingRuleSerializer,
    ServiceFeatureSerializer,
    ThresholdRuleSerializer,
    UsageQuotaSerializer,
)


class AuditCrudMixin:
    audit_resource_type = ""
    audit_name_field = "name"

    def audit_resource_name(self, instance):
        return str(getattr(instance, self.audit_name_field, "") or instance)

    def audit_metadata(self, instance):
        metadata = {}
        for field in ("provider", "name", "rule_id", "strategy_id"):
            if hasattr(instance, field):
                metadata[field] = getattr(instance, field)
        return metadata

    def perform_create(self, serializer):
        instance = serializer.save()
        record_audit_log(
            request=self.request,
            action=f"{self.audit_resource_type}.create",
            resource_type=self.audit_resource_type,
            resource_id=instance.id,
            resource_name=self.audit_resource_name(instance),
            metadata=self.audit_metadata(instance),
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        record_audit_log(
            request=self.request,
            action=f"{self.audit_resource_type}.update",
            resource_type=self.audit_resource_type,
            resource_id=instance.id,
            resource_name=self.audit_resource_name(instance),
            metadata=self.audit_metadata(instance),
        )

    def perform_destroy(self, instance):
        record_audit_log(
            request=self.request,
            action=f"{self.audit_resource_type}.delete",
            resource_type=self.audit_resource_type,
            resource_id=instance.id,
            resource_name=self.audit_resource_name(instance),
            metadata=self.audit_metadata(instance),
        )
        instance.delete()


class LLMModelListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = LLMModel.objects.all()
    serializer_class = LLMModelSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "models"
    audit_resource_type = "model"


class LLMModelDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = LLMModel.objects.all()
    serializer_class = LLMModelSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "models"
    audit_resource_type = "model"


class LLMModelConnectivityView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "models"

    def get(self, request):
        models = list(LLMModel.objects.select_related("provider_credential").all())
        return Response(check_models_connectivity(models))


class EvaluationDatasetListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = EvaluationDataset.objects.select_related("uploaded_by").all()
    serializer_class = EvaluationDatasetSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-datasets"
    audit_resource_type = "evaluation_dataset"

    def perform_create(self, serializer):
        instance = serializer.save(uploaded_by=self.request.user)
        record_audit_log(
            request=self.request,
            action="evaluation_dataset.create",
            resource_type="evaluation_dataset",
            resource_id=instance.id,
            resource_name=instance.name,
            metadata={
                "dataset_type": instance.dataset_type,
                "dataset_family": instance.dataset_family,
                "data_format": instance.data_format,
                "source": instance.source,
                "question_count": instance.question_count,
            },
        )


class EvaluationDatasetDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = EvaluationDataset.objects.select_related("uploaded_by").all()
    serializer_class = EvaluationDatasetSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-datasets"
    audit_resource_type = "evaluation_dataset"


class EvaluationMethodListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = EvaluationMethod.objects.all()
    serializer_class = EvaluationMethodSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-methods"
    audit_resource_type = "evaluation_method"


class EvaluationMethodDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = EvaluationMethod.objects.all()
    serializer_class = EvaluationMethodSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-methods"
    audit_resource_type = "evaluation_method"


class EvaluationRunListView(generics.ListCreateAPIView):
    queryset = (
        EvaluationRun.objects.select_related("dataset", "evaluation_method", "created_by")
        .defer("dataset__dataset_family", "dataset__data_format")
        .prefetch_related("models", "results")
    )
    serializer_class = EvaluationRunSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-runs"

    def perform_create(self, serializer):
        run = serializer.save(created_by=self.request.user)
        record_audit_log(
            request=self.request,
            action="evaluation_run.create",
            resource_type="evaluation_run",
            resource_id=run.id,
            resource_name=run.name,
            metadata={
                "dataset_id": run.dataset_id,
                "model_ids": list(run.models.values_list("id", flat=True)),
            },
        )


class EvaluationResultListView(generics.ListAPIView):
    queryset = EvaluationResult.objects.select_related("run__evaluation_method", "dataset", "model").all()
    serializer_class = EvaluationResultSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "model-evaluation"


class EvaluationItemResultListView(generics.ListAPIView):
    serializer_class = EvaluationItemResultSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-item-results"

    def get_queryset(self):
        queryset = EvaluationItemResult.objects.select_related("result", "run", "dataset", "model").all()
        run_id = self.request.query_params.get("run")
        result_id = self.request.query_params.get("result")
        if run_id:
            queryset = queryset.filter(run_id=run_id)
        if result_id:
            queryset = queryset.filter(result_id=result_id)
        return queryset[:1000]


class EvaluationResultArtifactsView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-artifacts"

    def get(self, request, pk):
        result = generics.get_object_or_404(
            EvaluationResult.objects.select_related("run__evaluation_method", "dataset", "model"),
            pk=pk,
        )
        item_logs = list(
            EvaluationItemResult.objects.filter(result=result)
            .order_by("item_index", "attempt")
            .values(
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
                "raw_output",
                "subject",
                "category",
            )
        )
        manifest = {
            "run_id": result.run_id,
            "run_name": result.run.name,
            "dataset": {
                "id": result.dataset_id,
                "name": result.dataset.name,
                "type": result.dataset.dataset_type,
                "family": result.dataset.dataset_family,
                "format": result.dataset.data_format,
                "question_count": result.dataset.question_count,
            },
            "evaluation_method": {
                "id": result.run.evaluation_method_id,
                "name": result.run.evaluation_method.name if result.run.evaluation_method else "legacy",
                "display_name": result.run.evaluation_method.display_name if result.run.evaluation_method else "Legacy evaluation",
            },
            "config": result.run.config,
            "generated_from": "api",
        }
        model_summary = {
            "model_id": result.model_id,
            "provider": result.model.provider,
            "model": result.model.name,
            "display_name": result.model.display_name,
            "status": result.status,
            "overall_accuracy": result.overall_accuracy,
            "strict_compliance_rate": result.strict_compliance_rate,
            "failure_rate": result.failure_rate,
            "parse_failure_rate": result.parse_failure_rate,
            "latency_p50_ms": result.latency_p50_ms,
            "latency_p95_ms": result.latency_p95_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "estimated_cost_usd": result.estimated_cost_usd,
            "subject_accuracy": result.subject_accuracy,
            "category_accuracy": result.category_accuracy,
        }
        jsonl_like_logs = [self.to_jsonl_row(row) for row in item_logs]
        return Response(
            {
                "eval_manifest": manifest,
                "model_summary": model_summary,
                "scorecard": result.scorecard,
                "item_logs": item_logs,
                "jsonl_like_logs": jsonl_like_logs,
                "report_markdown": result.scorecard.get("report_markdown") or self.build_report_markdown(result),
            }
        )

    def to_jsonl_row(self, row):
        return {
            "item_index": row["item_index"],
            "subject": row["subject"],
            "category": row["category"],
            "gold": row["gold"],
            "predicted": row["predicted_choice"],
            "strict_ok": row["strict_ok"],
            "is_correct": row["is_correct"],
            "ok": row["ok"],
            "attempt": row["attempt"],
            "latency_ms": row["latency_ms"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "error": row["error"],
        }

    def build_report_markdown(self, result):
        scorecard = result.scorecard or {}
        return "\n".join(
            [
                f"# {result.run.name} 결과 리포트",
                "",
                f"- 모델: {result.model.provider}/{result.model.name}",
                f"- 데이터셋: {result.dataset.name} ({result.dataset.dataset_family}/{result.dataset.dataset_type}/{result.dataset.data_format})",
                f"- 정확도: {self.format_ratio(result.overall_accuracy)}",
                f"- Strict 준수율: {self.format_ratio(result.strict_compliance_rate)}",
                f"- 실패율: {self.format_ratio(result.failure_rate)}",
                f"- SLA: p50 {result.latency_p50_ms or '-'}ms / p95 {result.latency_p95_ms or '-'}ms",
                f"- Token: input {result.input_tokens}, output {result.output_tokens}",
                f"- 비용 추정: ${result.estimated_cost_usd or '0.000000'}",
                "",
                "## Score Card",
                f"- Performance: {scorecard.get('performance_score', '-')}",
                f"- Efficiency: {scorecard.get('efficiency_score', '-')}",
                f"- Capability: {scorecard.get('capability_score', '-')}",
                f"- Total: {scorecard.get('total_score', '-')}",
                "",
                f"권장 역할: {scorecard.get('recommended_role', 'insufficient_data')}",
            ]
        )

    def format_ratio(self, value):
        if value is None:
            return "-"
        return f"{float(value) * 100:.1f}%"


class EvaluationModelAvailabilityView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-runs"

    def get(self, request):
        model_ids = [int(value) for value in request.query_params.get("model_ids", "").split(",") if value.strip().isdigit()]
        run_id = request.query_params.get("run_id")
        models = []

        if run_id and run_id.isdigit():
            run = generics.get_object_or_404(
                EvaluationRun.objects.prefetch_related("models"),
                pk=int(run_id),
            )
            models = list(run.models.select_related("provider_credential").all())
        elif model_ids:
            models = list(LLMModel.objects.filter(id__in=model_ids).select_related("provider_credential"))
        else:
            models = list(LLMModel.objects.filter(is_active=True).select_related("provider_credential"))

        connectivity = check_models_connectivity(models)
        unavailable = [item for item in connectivity if item["status"] != "online"]
        return Response(
            {
                "ready": len(unavailable) == 0 and bool(models),
                "models": connectivity,
                "unavailable_models": unavailable,
            }
        )


class EvaluationRunDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        EvaluationRun.objects.select_related("dataset", "evaluation_method", "created_by")
        .prefetch_related("models", "results")
    )
    serializer_class = EvaluationRunSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-runs"
    audit_resource_type = "evaluation_run"


class EvaluationRunExecuteView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "evaluation-runs"

    def post(self, request, pk):
        run = generics.get_object_or_404(
            EvaluationRun.objects.select_related("dataset", "created_by").prefetch_related("models", "results"),
            pk=pk,
        )
        if run.status == "running":
            return Response({"detail": "이미 실행 중인 평가입니다."}, status=status.HTTP_400_BAD_REQUEST)

        run_models = list(run.models.select_related("provider_credential").all())
        if not run_models:
            return Response({"detail": "평가 대상 모델이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        ready, availability_errors = validate_models_available(run_models)
        if not ready:
            return Response(
                {
                    "detail": "실험 실행 전 모델 가용성 검사에 실패했습니다.",
                    "availability_errors": availability_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        runner = PilotEvaluationRunner()
        try:
            executed_run = runner.execute(run)
        except Exception as exc:
            record_audit_log(
                request=request,
                action="evaluation_run.execute_failed",
                resource_type="evaluation_run",
                resource_id=run.id,
                resource_name=run.name,
                metadata={"error": str(exc)},
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record_audit_log(
            request=request,
            action="evaluation_run.execute",
            resource_type="evaluation_run",
            resource_id=executed_run.id,
            resource_name=executed_run.name,
            metadata={
                "dataset_id": executed_run.dataset_id,
                "status": executed_run.status,
                "result_count": executed_run.results.count(),
            },
        )
        executed_run = EvaluationRun.objects.select_related("dataset", "created_by").prefetch_related("models", "results").get(pk=executed_run.pk)
        return Response(EvaluationRunSerializer(executed_run).data)


class PolicyListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = RoutingPolicy.objects.all()
    serializer_class = RoutingPolicySerializer
    permission_classes = [HasScreenAccess]
    required_screen = "policies"
    audit_resource_type = "policy"


class PolicyDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = RoutingPolicy.objects.all()
    serializer_class = RoutingPolicySerializer
    permission_classes = [HasScreenAccess]
    required_screen = "policies"
    audit_resource_type = "policy"


class RoutingRuleListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = RoutingRule.objects.all()
    serializer_class = RoutingRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "routing-rules"
    audit_resource_type = "routing_rule"


class RoutingRuleDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = RoutingRule.objects.all()
    serializer_class = RoutingRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "routing-rules"
    audit_resource_type = "routing_rule"


class ThresholdRuleListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = ThresholdRule.objects.all()
    serializer_class = ThresholdRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "threshold-rules"
    audit_resource_type = "threshold_rule"


class ThresholdRuleDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ThresholdRule.objects.all()
    serializer_class = ThresholdRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "threshold-rules"
    audit_resource_type = "threshold_rule"


class ResponseValidationRuleListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = ResponseValidationRule.objects.all()
    serializer_class = ResponseValidationRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "validation-rules"
    audit_resource_type = "validation_rule"


class ResponseValidationRuleDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ResponseValidationRule.objects.all()
    serializer_class = ResponseValidationRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "validation-rules"
    audit_resource_type = "validation_rule"


class RecoveryStrategyListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = RecoveryStrategy.objects.all()
    serializer_class = RecoveryStrategySerializer
    permission_classes = [HasScreenAccess]
    required_screen = "recovery-strategies"
    audit_resource_type = "recovery_strategy"


class RecoveryStrategyDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = RecoveryStrategy.objects.all()
    serializer_class = RecoveryStrategySerializer
    permission_classes = [HasScreenAccess]
    required_screen = "recovery-strategies"
    audit_resource_type = "recovery_strategy"


class ModelHealthEventListView(generics.ListAPIView):
    queryset = ModelHealthEvent.objects.select_related("rule").all()
    serializer_class = ModelHealthEventSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "health-events"


class ModelHealthOverrideListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = ModelHealthOverride.objects.select_related("created_by").all()
    serializer_class = ModelHealthOverrideSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "health-overrides"
    audit_resource_type = "health_override"

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        record_audit_log(
            request=self.request,
            action="health_override.create",
            resource_type="health_override",
            resource_id=instance.id,
            resource_name=instance.name,
            metadata=self.audit_metadata(instance),
        )


class ModelHealthOverrideDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ModelHealthOverride.objects.select_related("created_by").all()
    serializer_class = ModelHealthOverrideSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "health-overrides"
    audit_resource_type = "health_override"


class ProviderCredentialListView(generics.ListCreateAPIView):
    queryset = ProviderCredential.objects.all()
    serializer_class = ProviderCredentialSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "credentials"

    def perform_create(self, serializer):
        credential = serializer.save()
        record_audit_log(
            request=self.request,
            action="credential.create",
            resource_type="provider_credential",
            resource_id=credential.id,
            resource_name=credential.display_name,
            metadata={"provider": credential.provider},
        )


class ProviderCredentialDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProviderCredential.objects.all()
    serializer_class = ProviderCredentialSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "credentials"

    def perform_update(self, serializer):
        token_was_rotated = bool(serializer.validated_data.get("access_token"))
        credential = serializer.save()
        record_audit_log(
            request=self.request,
            action="credential.rotate_token" if token_was_rotated else "credential.update",
            resource_type="provider_credential",
            resource_id=credential.id,
            resource_name=credential.display_name,
            metadata={"provider": credential.provider},
        )

    def perform_destroy(self, instance):
        record_audit_log(
            request=self.request,
            action="credential.delete",
            resource_type="provider_credential",
            resource_id=instance.id,
            resource_name=instance.display_name,
            metadata={"provider": instance.provider},
        )
        instance.delete()


class ProviderCredentialTestSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["ollama", "openai", "gemini", "openrouter"])
    base_url = serializers.CharField()
    access_token = serializers.CharField(allow_blank=True, required=False)


class ProviderCredentialTestView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "credentials"

    def post(self, request):
        serializer = ProviderCredentialTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.validated_data["provider"]
        base_url = serializer.validated_data["base_url"].rstrip("/")
        access_token = serializer.validated_data.get("access_token", "")

        try:
            response = self.request_provider(provider, base_url, access_token)
            ok = 200 <= response.status_code < 300
            return Response(
                {
                    "ok": ok,
                    "status_code": response.status_code,
                    "message": "Connection succeeded." if ok else self.extract_error_message(response),
                },
                status=status.HTTP_200_OK,
            )
        except requests.RequestException as exc:
            return Response(
                {
                    "ok": False,
                    "status_code": None,
                    "message": str(exc),
                },
                status=status.HTTP_200_OK,
            )

    def request_provider(self, provider: str, base_url: str, access_token: str):
        if provider == "ollama":
            headers = {}
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            return requests.get(
                f"{base_url}/api/tags",
                headers=headers,
                timeout=15,
            )
        if provider == "gemini":
            return requests.get(
                f"{base_url}/models",
                headers={"x-goog-api-key": access_token},
                timeout=15,
            )
        return requests.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )

    def extract_error_message(self, response):
        try:
            payload = response.json()
        except ValueError:
            return response.text[:300] or "Connection failed."
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return error.get("message") or str(error)
            if error:
                return str(error)
            return payload.get("message") or str(payload)[:300]
        return str(payload)[:300]


class ProviderModelImportSerializer(serializers.Serializer):
    model_names = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )


class ProviderCredentialModelPreviewView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "credentials"

    def get(self, request, pk):
        credential = generics.get_object_or_404(ProviderCredential, pk=pk, is_active=True)
        try:
            models = fetch_provider_models(credential)
        except requests.RequestException as exc:
            record_audit_log(
                request=request,
                action="provider_models.preview_failed",
                resource_type="provider_credential",
                resource_id=credential.id,
                resource_name=credential.display_name,
                metadata={"provider": credential.provider, "error": str(exc)},
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"models": models})


class ProviderCredentialModelImportView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "credentials"

    def post(self, request, pk):
        credential = generics.get_object_or_404(ProviderCredential, pk=pk, is_active=True)
        serializer = ProviderModelImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        imported = []
        skipped = []
        for model_name in serializer.validated_data["model_names"]:
            model, created = LLMModel.objects.get_or_create(
                provider=credential.provider,
                name=model_name,
                defaults={
                    "display_name": humanize_model_name(model_name),
                    "model_tier": "standard",
                    "provider_credential": credential,
                    "role": "general",
                    "quality_level": 3,
                    "speed_level": 3,
                    "cost_level": 3,
                    "privacy_level": "external",
                    "context_window": 8192,
                    "input_token_price_per_1m": 0,
                    "output_token_price_per_1m": 0,
                    "average_latency_ms": 0,
                    "timeout_seconds": 120,
                    "is_active": True,
                },
            )
            if created:
                imported.append(LLMModelSerializer(model).data)
            else:
                skipped.append(model_name)
        record_audit_log(
            request=request,
            action="provider_models.import",
            resource_type="provider_credential",
            resource_id=credential.id,
            resource_name=credential.display_name,
            metadata={
                "provider": credential.provider,
                "imported": [model["name"] for model in imported],
                "skipped": skipped,
            },
        )
        return Response({"imported": imported, "skipped": skipped}, status=status.HTTP_201_CREATED)


class UsageQuotaListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = UsageQuota.objects.select_related("user").all()
    serializer_class = UsageQuotaSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "quotas"
    audit_resource_type = "usage_quota"


class UsageQuotaDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = UsageQuota.objects.select_related("user").all()
    serializer_class = UsageQuotaSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "quotas"
    audit_resource_type = "usage_quota"


class ServiceFeatureListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = ServiceFeature.objects.all()
    serializer_class = ServiceFeatureSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "service-features"
    audit_resource_type = "service_feature"


class ServiceFeatureDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ServiceFeature.objects.all()
    serializer_class = ServiceFeatureSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "service-features"
    audit_resource_type = "service_feature"


class TierRecommendationView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "tier-recommendation"

    def get(self, request):
        raw = request.query_params.get("model_ids", "")
        if raw:
            try:
                model_ids = [int(x) for x in raw.split(",") if x.strip()]
            except ValueError:
                return Response({"detail": "Invalid model_ids parameter."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            model_ids = list(LLMModel.objects.filter(is_active=True).values_list("id", flat=True))
        return Response(get_tier_recommendations(model_ids))


class PolicyDraftGenerateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    preset = serializers.ChoiceField(choices=["cost-first", "quality-first", "balanced", "privacy-first"])
    model_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    feature_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    tier_overrides = serializers.DictField(child=serializers.CharField(), required=False, default=dict)


class PolicyDraftGenerateView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "policy-draft"

    def post(self, request):
        serializer = PolicyDraftGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        draft = generate_draft(
            name=data["name"],
            preset=data["preset"],
            model_ids=data["model_ids"],
            feature_ids=data["feature_ids"],
            tier_overrides=data.get("tier_overrides", {}),
            created_by=request.user,
        )
        return Response(PolicyDraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class PolicyDraftListView(generics.ListAPIView):
    queryset = PolicyDraft.objects.select_related("created_by").all()
    serializer_class = PolicyDraftSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "policy-draft"


class PolicyDraftDetailView(generics.RetrieveAPIView):
    queryset = PolicyDraft.objects.select_related("created_by").all()
    serializer_class = PolicyDraftSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "policy-draft"


class PolicyDraftSaveView(APIView):
    permission_classes = [HasScreenAccess]
    required_screen = "policy-draft"

    def post(self, request, pk):
        draft = generics.get_object_or_404(PolicyDraft, pk=pk)
        if draft.is_saved:
            return Response({"detail": "Draft already saved as a policy."}, status=status.HTTP_400_BAD_REQUEST)
        policy = save_draft_as_policy(draft)
        return Response({
            "saved": True,
            "policy_id": policy.id,
            "policy_name": policy.display_name,
        })


class ModelHealthRuleListView(AuditCrudMixin, generics.ListCreateAPIView):
    queryset = ModelHealthRule.objects.all()
    serializer_class = ModelHealthRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "health-rules"
    audit_resource_type = "health_rule"


class ModelHealthRuleDetailView(AuditCrudMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ModelHealthRule.objects.all()
    serializer_class = ModelHealthRuleSerializer
    permission_classes = [HasScreenAccess]
    required_screen = "health-rules"
    audit_resource_type = "health_rule"
