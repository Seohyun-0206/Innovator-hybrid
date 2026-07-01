import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import (
    EvaluationDataset,
    EvaluationItemResult,
    EvaluationMethod,
    EvaluationResult,
    EvaluationRun,
    LLMModel,
    RoutingPolicy,
)


STRICT_ANSWER_PATTERN = re.compile(r"\s*[ABCD]\s*", re.IGNORECASE)


class Command(BaseCommand):
    help = "Seed demo Ollama models and routing policies."

    def handle(self, *args, **options):
        models = [
            {
                "provider": "ollama",
                "name": "llama3.1:8b",
                "display_name": "Llama 3.1 8B",
                "role": "general",
                "quality_level": 3,
                "speed_level": 5,
                "cost_level": 1,
                "privacy_level": "local",
                "context_window": 8192,
                "input_token_price_per_1m": 0,
                "output_token_price_per_1m": 0,
                "average_latency_ms": 2500,
                "timeout_seconds": 120,
                "is_active": True,
            },
            {
                "provider": "ollama",
                "name": "codellama:latest",
                "display_name": "Code Llama",
                "role": "coding",
                "quality_level": 4,
                "speed_level": 3,
                "cost_level": 1,
                "privacy_level": "local",
                "context_window": 16384,
                "input_token_price_per_1m": 0,
                "output_token_price_per_1m": 0,
                "average_latency_ms": 4000,
                "timeout_seconds": 120,
                "is_active": True,
            },
            {
                "provider": "ollama",
                "name": "qwen3:8b",
                "display_name": "Qwen 3 8B",
                "role": "reasoning",
                "quality_level": 4,
                "speed_level": 4,
                "cost_level": 1,
                "privacy_level": "local",
                "context_window": 32768,
                "input_token_price_per_1m": 0,
                "output_token_price_per_1m": 0,
                "average_latency_ms": 5500,
                "timeout_seconds": 180,
                "is_active": True,
            },
            {
                "provider": "openai",
                "name": "gpt-4.1-mini",
                "display_name": "GPT-4.1 Mini",
                "role": "general",
                "quality_level": 4,
                "speed_level": 4,
                "cost_level": 3,
                "privacy_level": "external",
                "context_window": 128000,
                "input_token_price_per_1m": 0.4,
                "output_token_price_per_1m": 1.6,
                "average_latency_ms": 1800,
                "timeout_seconds": 120,
                "is_active": False,
            },
            {
                "provider": "gemini",
                "name": "gemini-2.5-flash",
                "display_name": "Gemini 2.5 Flash",
                "role": "general",
                "quality_level": 4,
                "speed_level": 5,
                "cost_level": 2,
                "privacy_level": "external",
                "context_window": 1000000,
                "input_token_price_per_1m": 0.3,
                "output_token_price_per_1m": 2.5,
                "average_latency_ms": 1600,
                "timeout_seconds": 120,
                "is_active": False,
            },
            {
                "provider": "openrouter",
                "name": "openai/gpt-4.1-mini",
                "display_name": "OpenRouter GPT-4.1 Mini",
                "role": "general",
                "quality_level": 4,
                "speed_level": 4,
                "cost_level": 3,
                "privacy_level": "external",
                "context_window": 128000,
                "input_token_price_per_1m": 0.4,
                "output_token_price_per_1m": 1.6,
                "average_latency_ms": 2200,
                "timeout_seconds": 120,
                "is_active": False,
            },
        ]
        for payload in models:
            LLMModel.objects.update_or_create(
                provider=payload["provider"],
                name=payload["name"],
                defaults=payload,
            )

        policies = [
            ("cost-first", "Cost First", "Prefer low-cost and fast local models."),
            ("quality-first", "Quality First",
             "Prefer stronger models for reasoning-heavy prompts."),
            ("privacy-first", "Privacy First",
             "Keep sensitive prompts on local models."),
        ]
        for name, display_name, description in policies:
            RoutingPolicy.objects.update_or_create(
                name=name,
                defaults={
                    "display_name": display_name,
                    "description": description,
                    "priority_config": {},
                    "is_active": True,
                },
            )

        imported_results = self.seed_mmlu_experiment()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded demo models, policies, and {imported_results} imported MMLU results."))

    def seed_mmlu_experiment(self) -> int:
        fixture_root = Path(__file__).resolve().parents[4] / "fixtures" / "imported_mmlu"
        artifacts = [
            {
                "model": "llama3.1:8b",
                "metrics": fixture_root / "output_ollama3_1_8b" / "llama3.1_8b_20260510_211025_metrics.json",
                "report": fixture_root / "output_ollama3_1_8b" / "llama3.1_8b_20260510_211025_report.md",
                "jsonl": fixture_root / "output_ollama3_1_8b" / "llama3.1_8b_20260510_210932.jsonl",
            },
            {
                "model": "qwen3:8b",
                "metrics": fixture_root / "output_qwen3_8b" / "qwen3_8b_20260510_224004_metrics.json",
                "report": fixture_root / "output_qwen3_8b" / "qwen3_8b_20260510_224004_report.md",
                "jsonl": fixture_root / "output_qwen3_8b" / "qwen3_8b_20260510_222708.jsonl",
            },
        ]
        if not all(path.exists() for artifact in artifacts for path in (artifact["metrics"], artifact["report"], artifact["jsonl"])):
            self.stdout.write(self.style.WARNING("MMLU artifact files were not found; skipped imported experiment seed."))
            return 0

        with transaction.atomic():
            method = self.get_or_create_mmlu_method()
            dataset = self.seed_dataset(artifacts[0]["jsonl"])
            run = self.seed_run(dataset, method)
            imported = 0
            for artifact in artifacts:
                model = LLMModel.objects.get(provider="ollama", name=artifact["model"])
                metrics_payload = self.read_json(artifact["metrics"])
                report_markdown = artifact["report"].read_text(encoding="utf-8")
                rows = self.read_jsonl(artifact["jsonl"])
                result = self.seed_result(run, dataset, model, metrics_payload, report_markdown)
                self.seed_item_results(result, dataset, model, rows)
                imported += 1
            return imported

    def get_or_create_mmlu_method(self):
        method, _ = EvaluationMethod.objects.update_or_create(
            name="mmlu_multiple_choice",
            defaults={
                "display_name": "MMLU 객관식 평가",
                "method_type": "multiple_choice",
                "description": "A/B/C/D 객관식 정답 추출, strict 응답 준수율, 정확도, 지연, 토큰, 비용을 함께 집계합니다.",
                "compatible_dataset_types": ["multiple_choice", "mmlu", "custom_mcq", "jsonl", "csv"],
                "default_config": {
                    "seed": 42,
                    "total_questions": 48,
                    "few_shot": 0,
                    "temperature": 0,
                    "max_tokens": 8,
                    "timeout_seconds": 180,
                    "retry": 0,
                },
                "metric_schema": {
                    "overall_accuracy": "0..1",
                    "strict_compliance_rate": "0..1",
                    "failure_rate": "0..1",
                    "parse_failure_rate": "0..1",
                    "latency_p50_ms": "milliseconds",
                    "latency_p95_ms": "milliseconds",
                    "scorecard": ["performance_score", "efficiency_score", "capability_score", "total_score"],
                },
                "artifact_schema": {
                    "eval_manifest": "run/dataset/method/config metadata",
                    "model_summary": "aggregated result metrics",
                    "scorecard": "routing-oriented score card",
                    "jsonl_like_logs": "per-item execution logs",
                    "report_markdown": "imported MMLU report markdown",
                },
                "is_active": True,
            },
        )
        return method

    def seed_dataset(self, jsonl_path: Path):
        rows = self.read_jsonl(jsonl_path)
        raw_content = "\n".join(
            json.dumps(
                {
                    "subject": row.get("subject", ""),
                    "category": row.get("category", ""),
                    "question": row.get("question", ""),
                    "choices": row.get("choices", []),
                    "answer": row.get("correct_answer", ""),
                },
                ensure_ascii=False,
            )
            for row in rows
        )
        categories = sorted({row.get("category", "") for row in rows if row.get("category")})
        subjects = sorted({row.get("subject", "") for row in rows if row.get("subject")})
        dataset, _ = EvaluationDataset.objects.update_or_create(
            name="MMLU 카테고리 균형 표본 N=48",
            defaults={
                "dataset_type": "multiple_choice",
                "dataset_family": "mmlu",
                "data_format": "jsonl",
                "source": "upload",
                "source_url": "",
                "original_filename": jsonl_path.name,
                "description": "2026-05-10 Ollama 8B 비교 실험에서 사용한 MMLU 카테고리 균형 48문항 표본입니다.",
                "raw_content": raw_content,
                "question_count": len(rows),
                "category_schema": {
                    "categories": categories,
                    "subjects": subjects,
                    "question_field": "question",
                    "answer_field": "answer",
                    "choices_field": "choices",
                    "subject_field": "subject",
                    "category_field": "category",
                    "source_artifact": jsonl_path.name,
                },
            },
        )
        return dataset

    def seed_run(self, dataset, method):
        completed_at = timezone.make_aware(datetime(2026, 5, 10, 22, 40, 4))
        run, _ = EvaluationRun.objects.update_or_create(
            name="2026-05-10 MMLU Ollama 8B 비교",
            defaults={
                "dataset": dataset,
                "evaluation_method": method,
                "status": "completed",
                "config": {
                    "seed": 42,
                    "total_questions": 48,
                    "max_questions": 48,
                    "few_shot": 0,
                    "temperature": 0,
                    "max_tokens": 8,
                    "timeout_seconds": 180,
                    "retry": 0,
                    "source": "imported_ollama_mmlu_artifacts",
                },
                "notes": "기존 output_* 산출물을 seed_demo로 가져온 비교 실험입니다.",
                "started_at": completed_at,
                "completed_at": completed_at,
            },
        )
        run.models.set(LLMModel.objects.filter(provider="ollama", name__in=["llama3.1:8b", "qwen3:8b"]))
        return run

    def seed_result(self, run, dataset, model, payload, report_markdown: str):
        metrics = payload["metrics"]
        score = payload["score"]
        total = int(metrics.get("total_questions") or 0)
        correct = round(float(metrics.get("accuracy") or 0) * total)
        strict_count = self.count_strict_answers(model.name)
        result, _ = EvaluationResult.objects.update_or_create(
            run=run,
            model=model,
            defaults={
                "dataset": dataset,
                "status": "completed",
                "overall_accuracy": self.decimal_ratio(metrics.get("accuracy")),
                "strict_compliance_rate": self.decimal_ratio(strict_count / total if total else 0),
                "failure_rate": self.decimal_ratio(metrics.get("api_failure_rate")),
                "parse_failure_rate": self.decimal_ratio(metrics.get("parse_failure_rate")),
                "latency_p50_ms": self.seconds_to_ms(metrics.get("latency_p50")),
                "latency_p95_ms": self.seconds_to_ms(metrics.get("latency_p95")),
                "input_tokens": int(metrics.get("total_input_tokens") or 0),
                "output_tokens": int(metrics.get("total_output_tokens") or 0),
                "estimated_cost_usd": Decimal(str(metrics.get("total_cost_usd") or 0)).quantize(Decimal("0.000001")),
                "category_accuracy": self.accuracy_map(metrics.get("category_accuracy", {})),
                "subject_accuracy": self.accuracy_map(metrics.get("subject_accuracy", {})),
                "scorecard": {
                    "evaluated_questions": total,
                    "correct": correct,
                    "failures": int(metrics.get("api_failure_count") or 0),
                    "parse_failures": int(metrics.get("parse_failure_count") or 0),
                    "performance_score": round(float(score.get("performance") or 0), 2),
                    "efficiency_score": round(float(score.get("efficiency") or 0), 2),
                    "capability_score": round(float(score.get("capability") or 0), 2),
                    "total_score": round(float(score.get("total") or 0), 2),
                    "reliability_score": round((1 - float(metrics.get("api_failure_rate") or 0) - float(metrics.get("parse_failure_rate") or 0)) * 100, 2),
                    "recommended_role": self.recommend_role(metrics, score),
                    "role_reason": "기존 MMLU/Ollama 산출물에서 가져온 scorecard를 기준으로 추천했습니다.",
                    "mode": "imported_ollama_mmlu",
                    "report_markdown": report_markdown,
                },
                "error_message": "",
            },
        )
        return result

    def seed_item_results(self, result, dataset, model, rows):
        result.item_results.all().delete()
        for index, row in enumerate(rows, start=1):
            error = row.get("api_error") or ""
            predicted = row.get("parsed_answer") or ""
            raw_output = row.get("model_output") or ""
            EvaluationItemResult.objects.create(
                result=result,
                run=result.run,
                dataset=dataset,
                model=model,
                item_index=index,
                question=row.get("question", ""),
                choices=row.get("choices", []),
                gold=row.get("correct_answer", ""),
                predicted_choice=predicted,
                strict_ok=bool(STRICT_ANSWER_PATTERN.fullmatch(raw_output.strip())),
                is_correct=bool(row.get("correct")),
                ok=not bool(error) and bool(predicted),
                attempt=1,
                error=str(error),
                input_tokens=int(row.get("input_tokens") or 0),
                output_tokens=int(row.get("output_tokens") or 0),
                latency_ms=self.seconds_to_ms(row.get("latency")),
                raw_output=raw_output,
                subject=row.get("subject", ""),
                category=row.get("category", ""),
            )

    def count_strict_answers(self, model_name: str) -> int:
        fixture_root = Path(__file__).resolve().parents[4] / "fixtures" / "imported_mmlu"
        jsonl_path = (
            fixture_root / "output_ollama3_1_8b" / "llama3.1_8b_20260510_210932.jsonl"
            if model_name == "llama3.1:8b"
            else fixture_root / "output_qwen3_8b" / "qwen3_8b_20260510_222708.jsonl"
        )
        return sum(
            1
            for row in self.read_jsonl(jsonl_path)
            if STRICT_ANSWER_PATTERN.fullmatch(str(row.get("model_output") or "").strip())
        )

    def recommend_role(self, metrics, score):
        accuracy = float(metrics.get("accuracy") or 0)
        p95_ms = self.seconds_to_ms(metrics.get("latency_p95")) or 0
        if accuracy >= 0.75 and float(score.get("total") or 0) >= 80:
            return "Accurate Path"
        if p95_ms <= 3000 and accuracy >= 0.5:
            return "Fast Path"
        return "Escalation Candidate"

    def read_json(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def read_jsonl(self, path: Path):
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def decimal_ratio(self, value):
        return Decimal(str(value or 0)).quantize(Decimal("0.0001"))

    def seconds_to_ms(self, value):
        if value is None:
            return None
        return int(round(float(value) * 1000))

    def accuracy_map(self, values):
        return {
            key: {
                "correct": round(float(value) * 1),
                "total": 1,
                "accuracy": float(value),
            }
            for key, value in values.items()
        }
