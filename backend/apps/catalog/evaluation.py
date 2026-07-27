import time
from decimal import Decimal

from django.utils import timezone

from apps.catalog.model_metrics import (
    EvaluationQuestion,
    LatencyStats,
    build_generation_prompt,
    build_mcq_prompt,
    build_provider_options,
    decimal_percentile,
    estimate_cost,
    estimate_tokens,
    execute_model_call,
    extract_answer,
    is_generation_correct,
    is_strict_answer,
    load_questions,
    percentile,
    ratio,
    select_questions_by_difficulty,
    select_questions_from_pools,
    start_kv_cache_poller,
    stop_kv_cache_poller,
    strip_thinking_output,
)
from apps.catalog.models import EvaluationDatasetSnapshot, EvaluationItemResult, EvaluationRun
from apps.providers.registry import ProviderRegistry


class PilotEvaluationRunner:
    def __init__(self):
        self.provider_registry = ProviderRegistry()

    def execute(self, run: EvaluationRun) -> EvaluationRun:
        run.status = "running"
        run.started_at = timezone.now()
        run.completed_at = None
        run.save(update_fields=["status", "started_at", "completed_at", "updated_at"])

        try:
            snapshot = self.ensure_dataset_snapshot(run)
            questions = [EvaluationQuestion.from_payload(item) for item in snapshot.questions_payload]
            if not questions:
                raise ValueError("평가할 문항을 찾을 수 없습니다. raw_content 또는 접근 가능한 source_url을 확인하세요.")

            for result in run.results.select_related(
                "model", "routing_config", "routing_config__small_model", "routing_config__large_model"
            ):
                if result.result_type == "routing":
                    self.evaluate_routing_result(result, questions, run.config)
                else:
                    self.evaluate_model_result(result, questions, run.config)

            run.status = "completed"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
        except Exception as exc:
            run.status = "failed"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
            run.results.update(status="failed", error_message=str(exc))
            raise
        return run

    def ensure_dataset_snapshot(self, run: EvaluationRun) -> EvaluationDatasetSnapshot:
        """run에 스냅샷이 아직 없으면(예: 스냅샷 도입 이전에 만들어진 run) 지금 기준으로
        하나 만들어 붙입니다. 정상 경로에서는 실험 생성 시점에 이미 만들어져 있어야 합니다."""
        try:
            return run.dataset_snapshot
        except EvaluationDatasetSnapshot.DoesNotExist:
            pass
        return self.build_dataset_snapshot(
            run=run,
            dataset=run.dataset,
            easy_dataset=run.easy_dataset,
            hard_dataset=run.hard_dataset,
            easy_ratio=run.config.get("easy_ratio"),
            seed=run.config.get("seed"),
            total_questions=run.config.get("total_questions") or run.config.get("max_questions"),
        )

    def build_dataset_snapshot(
        self,
        *,
        run: EvaluationRun,
        dataset,
        easy_dataset=None,
        hard_dataset=None,
        easy_ratio,
        seed,
        total_questions,
    ) -> EvaluationDatasetSnapshot:
        method_type = run.evaluation_method.method_type if run.evaluation_method_id else "multiple_choice"
        selection = self.select_snapshot_questions(
            dataset=dataset,
            easy_dataset=easy_dataset,
            hard_dataset=hard_dataset,
            easy_ratio=easy_ratio,
            seed=seed,
            total_questions=total_questions,
            method_type=method_type,
        )
        return EvaluationDatasetSnapshot.objects.create(
            run=run,
            dataset=dataset,
            easy_dataset=easy_dataset,
            hard_dataset=hard_dataset,
            easy_ratio=selection["easy_ratio"],
            seed=int(seed) if seed is not None else 0,
            total_questions=len(selection["questions"]),
            questions_payload=[question.to_payload() for question in selection["questions"]],
        )

    def preview_snapshot_counts(self, *, dataset, easy_dataset=None, hard_dataset=None, easy_ratio, seed, total_questions) -> dict:
        """실험 생성 화면의 Dataset Preview용 — 저장 없이 총/Easy/Hard 문항 수만 계산합니다.
        실제 생성 시 쓰는 것과 완전히 같은 select_snapshot_questions()를 호출하므로
        미리보기 숫자와 실제 생성 결과가 어긋나지 않습니다."""
        selection = self.select_snapshot_questions(
            dataset=dataset,
            easy_dataset=easy_dataset,
            hard_dataset=hard_dataset,
            easy_ratio=easy_ratio,
            seed=seed,
            total_questions=total_questions,
        )
        return {
            "total_questions": len(selection["questions"]),
            "easy_count": selection["easy_count"],
            "hard_count": selection["hard_count"],
        }

    def select_snapshot_questions(
        self, *, dataset, easy_dataset=None, hard_dataset=None, easy_ratio, seed, total_questions, method_type="multiple_choice"
    ) -> dict:
        total = int(total_questions or 20)
        total = max(1, min(total, 500))
        if easy_dataset is not None and hard_dataset is not None:
            easy_questions = load_questions(easy_dataset, method_type)
            hard_questions = load_questions(hard_dataset, method_type)
            resolved_ratio = 50 if easy_ratio is None else int(easy_ratio)
            selected = select_questions_from_pools(easy_questions, hard_questions, resolved_ratio, total, seed)
        else:
            questions = load_questions(dataset, method_type)
            resolved_ratio = easy_ratio
            selected = select_questions_by_difficulty(questions, easy_ratio, total, seed)
        easy_count = sum(1 for question in selected if question.difficulty == "easy")
        hard_count = sum(1 for question in selected if question.difficulty == "hard")
        return {
            "questions": selected,
            "easy_count": easy_count,
            "hard_count": hard_count,
            "easy_ratio": resolved_ratio,
        }

    def evaluate_model_result(self, result, questions: list[EvaluationQuestion], config: dict):
        model = result.model
        method_type = result.run.evaluation_method.method_type if result.run.evaluation_method_id else "multiple_choice"
        result.status = "running"
        result.error_message = ""
        result.save(update_fields=["status", "error_message", "updated_at"])

        try:
            provider = self.provider_registry.get(model.provider, credential=model.provider_credential)
        except Exception as exc:
            result.status = "failed"
            result.failure_rate = Decimal("1.0000")
            result.error_message = str(exc)
            result.save()
            return

        latency_stats = LatencyStats()
        correct = 0
        strict_ok = 0
        failures = 0
        parse_failures = 0
        input_tokens = 0
        output_tokens = 0
        category_stats = {}
        subject_stats = {}

        result.item_results.all().delete()
        max_retries = max(0, int(config.get("retry") or config.get("max_retries") or 0))
        run_started = time.perf_counter()

        kv_cache_samples = []
        kv_cache_thread, kv_cache_stop = start_kv_cache_poller(provider, kv_cache_samples)

        for item_index, question in enumerate(questions, start=1):
            prompt = self.build_item_prompt(method_type, question, config)
            prompt_tokens = estimate_tokens(prompt)
            final_record = None

            for attempt in range(1, max_retries + 2):
                call = execute_model_call(
                    provider,
                    model_name=model.name,
                    prompt=prompt,
                    options=build_provider_options(model.provider, config),
                    prompt_tokens_estimate=prompt_tokens,
                )
                prompt_tokens = call.input_tokens
                extracted, strict_answer, is_correct, ok = self.grade_output(method_type, call.output_text, question)
                if call.error:
                    result.error_message = call.error

                final_record = EvaluationItemResult.objects.create(
                    result=result,
                    run=result.run,
                    dataset=result.dataset,
                    model=model,
                    item_index=item_index,
                    question=question.question,
                    choices=question.choices,
                    gold=question.answer[:16],
                    predicted_choice=extracted,
                    strict_ok=strict_answer,
                    is_correct=is_correct,
                    ok=ok,
                    attempt=attempt,
                    error=call.error,
                    input_tokens=prompt_tokens,
                    output_tokens=call.output_tokens,
                    latency_ms=call.latency_ms,
                    ttft_ms=call.ttft_ms,
                    raw_output=call.output_text,
                    subject=question.subject,
                    category=question.category,
                )
                if ok or attempt > max_retries:
                    break

            input_tokens += prompt_tokens
            if final_record is None:
                continue
            output_tokens += final_record.output_tokens
            latency_stats.record(
                ok=final_record.ok,
                latency_ms=final_record.latency_ms,
                ttft_ms=final_record.ttft_ms,
                output_tokens=final_record.output_tokens,
            )
            if not final_record.ok:
                if final_record.error:
                    failures += 1
                else:
                    parse_failures += 1
            if final_record.ok and not final_record.predicted_choice:
                parse_failures += 1
            if final_record.strict_ok:
                strict_ok += 1
            if final_record.is_correct:
                correct += 1
            self.add_group_stat(category_stats, question.category, final_record.is_correct)
            self.add_group_stat(subject_stats, question.subject, final_record.is_correct)

        run_elapsed_seconds = time.perf_counter() - run_started
        stop_kv_cache_poller(kv_cache_thread, kv_cache_stop)

        total = len(questions)
        result.status = "completed" if failures < total else "failed"
        result.overall_accuracy = ratio(correct, total)
        result.strict_compliance_rate = ratio(strict_ok, total)
        result.failure_rate = ratio(failures, total)
        result.parse_failure_rate = ratio(parse_failures, total)
        result.latency_p50_ms = percentile(latency_stats.latencies, 50)
        result.latency_p95_ms = percentile(latency_stats.latencies, 95)
        result.ttft_p50_ms = percentile(latency_stats.ttfts, 50)
        result.ttft_p95_ms = percentile(latency_stats.ttfts, 95)
        result.tpot_p50_ms = decimal_percentile(latency_stats.tpots, 50)
        result.tpot_p95_ms = decimal_percentile(latency_stats.tpots, 95)
        result.throughput_p50_tps = decimal_percentile(latency_stats.throughputs, 50)
        result.throughput_p95_tps = decimal_percentile(latency_stats.throughputs, 95)
        result.system_throughput_tps = (
            Decimal(str(round(output_tokens / run_elapsed_seconds, 3)))
            if run_elapsed_seconds > 0
            else None
        )
        if kv_cache_samples:
            result.kv_cache_usage_min = Decimal(str(round(min(kv_cache_samples), 4)))
            result.kv_cache_usage_avg = Decimal(str(round(sum(kv_cache_samples) / len(kv_cache_samples), 4)))
            result.kv_cache_usage_max = Decimal(str(round(max(kv_cache_samples), 4)))
        result.input_tokens = input_tokens
        result.output_tokens = output_tokens
        result.estimated_cost_usd = estimate_cost(model, input_tokens, output_tokens)
        result.category_accuracy = self.serialize_group_stats(category_stats)
        result.subject_accuracy = self.serialize_group_stats(subject_stats)
        result.scorecard = self.build_scorecard(
            result=result,
            total=total,
            correct=correct,
            failures=failures,
            parse_failures=parse_failures,
            strict_ok=strict_ok,
        )
        result.save()

    def build_item_prompt(self, method_type: str, question: EvaluationQuestion, config: dict) -> str:
        if method_type == "generation":
            return build_generation_prompt(question, config)
        return build_mcq_prompt(question, config)

    def grade_output(self, method_type: str, output_text: str, question: EvaluationQuestion) -> tuple[str, bool, bool, bool]:
        """(predicted_choice, strict_ok, is_correct, ok) 튜플을 돌려줍니다.
        generation은 참조 정답 부분 문자열 매치로 채점하므로 predicted_choice/strict_ok는 MCQ 전용 개념이라 비워둡니다."""
        if method_type == "generation":
            is_correct = is_generation_correct(output_text, question.answer)
            ok = bool(output_text.strip())
            return "", False, is_correct, ok
        extracted = extract_answer(output_text)
        strict_answer = is_strict_answer(output_text)
        is_correct = extracted == question.answer
        ok = bool(extracted)
        return extracted, strict_answer, is_correct, ok

    def build_router_prompt(self, routing_prompt: str, question: EvaluationQuestion) -> str:
        if "{question}" in routing_prompt:
            return routing_prompt.replace("{question}", question.question)
        return f"{routing_prompt}\n\n질문: {question.question}"

    def parse_router_choice(self, router_output_text: str) -> str:
        """Router(Small Model) 응답이 정확히 "large"일 때만 large로 라우팅합니다.
        그 외(정확히 "small", 빈 응답, 부연 설명이 섞인 응답, <think> 추론 블록 등)는
        모두 small로 처리합니다 — Router 자신이 small_model이므로 판단이 애매할 때는
        안전하게 자기 자신이 답합니다."""
        return "large" if strip_thinking_output(router_output_text).lower() == "large" else "small"

    def evaluate_routing_result(self, result, questions: list[EvaluationQuestion], config: dict):
        routing_config = getattr(result, "routing_config", None)
        method_type = result.run.evaluation_method.method_type if result.run.evaluation_method_id else "multiple_choice"
        result.status = "running"
        result.error_message = ""
        result.save(update_fields=["status", "error_message", "updated_at"])

        small_model = routing_config.small_model if routing_config else None
        large_model = routing_config.large_model if routing_config else None
        if routing_config is None or small_model is None or large_model is None:
            result.status = "failed"
            result.failure_rate = Decimal("1.0000")
            result.error_message = "Small/Large 모델이 설정되지 않았습니다."
            result.save()
            return

        try:
            small_provider = self.provider_registry.get(small_model.provider, credential=small_model.provider_credential)
        except Exception as exc:
            result.status = "failed"
            result.failure_rate = Decimal("1.0000")
            result.error_message = str(exc)
            result.save()
            return

        provider_by_model_id = {small_model.id: small_provider}

        def get_provider_for(model):
            if model.id not in provider_by_model_id:
                provider_by_model_id[model.id] = self.provider_registry.get(model.provider, credential=model.provider_credential)
            return provider_by_model_id[model.id]

        latency_stats = LatencyStats()
        correct = 0
        strict_ok = 0
        failures = 0
        parse_failures = 0
        input_tokens = 0
        output_tokens = 0
        estimated_cost = Decimal("0")
        category_stats = {}
        subject_stats = {}
        routing_counts = {"small": 0, "large": 0}
        router_latencies = []

        result.item_results.all().delete()
        max_retries = max(0, int(config.get("retry") or config.get("max_retries") or 0))
        run_started = time.perf_counter()

        kv_cache_samples = []
        kv_cache_thread, kv_cache_stop = start_kv_cache_poller(small_provider, kv_cache_samples)

        for item_index, question in enumerate(questions, start=1):
            router_prompt = self.build_router_prompt(routing_config.routing_prompt, question)
            router_call = execute_model_call(
                small_provider,
                model_name=small_model.name,
                prompt=router_prompt,
                options=build_provider_options(small_model.provider, config),
                prompt_tokens_estimate=estimate_tokens(router_prompt),
            )
            choice = self.parse_router_choice(router_call.output_text)
            routing_counts[choice] += 1
            if router_call.latency_ms is not None:
                router_latencies.append(router_call.latency_ms)
            chosen_model = large_model if choice == "large" else small_model
            provider = get_provider_for(chosen_model)
            estimated_cost += estimate_cost(small_model, router_call.input_tokens, router_call.output_tokens)

            prompt = self.build_item_prompt(method_type, question, config)
            prompt_tokens = estimate_tokens(prompt)
            final_record = None

            for attempt in range(1, max_retries + 2):
                call = execute_model_call(
                    provider,
                    model_name=chosen_model.name,
                    prompt=prompt,
                    options=build_provider_options(chosen_model.provider, config),
                    prompt_tokens_estimate=prompt_tokens,
                )
                prompt_tokens = call.input_tokens
                extracted, strict_answer, is_correct, ok = self.grade_output(method_type, call.output_text, question)
                if call.error:
                    result.error_message = call.error

                final_record = EvaluationItemResult.objects.create(
                    result=result,
                    run=result.run,
                    dataset=result.dataset,
                    model=chosen_model,
                    item_index=item_index,
                    question=question.question,
                    choices=question.choices,
                    gold=question.answer[:16],
                    predicted_choice=extracted,
                    strict_ok=strict_answer,
                    is_correct=is_correct,
                    ok=ok,
                    attempt=attempt,
                    error=call.error,
                    input_tokens=prompt_tokens,
                    output_tokens=call.output_tokens,
                    latency_ms=call.latency_ms,
                    ttft_ms=call.ttft_ms,
                    router_output=router_call.output_text,
                    raw_output=call.output_text,
                    subject=question.subject,
                    category=question.category,
                )
                if ok or attempt > max_retries:
                    break

            input_tokens += prompt_tokens + router_call.input_tokens
            if final_record is None:
                continue
            output_tokens += final_record.output_tokens + router_call.output_tokens
            estimated_cost += estimate_cost(chosen_model, final_record.input_tokens, final_record.output_tokens)
            latency_stats.record(
                ok=final_record.ok,
                latency_ms=final_record.latency_ms,
                ttft_ms=final_record.ttft_ms,
                output_tokens=final_record.output_tokens,
            )
            if not final_record.ok:
                if final_record.error:
                    failures += 1
                else:
                    parse_failures += 1
            if final_record.ok and not final_record.predicted_choice:
                parse_failures += 1
            if final_record.strict_ok:
                strict_ok += 1
            if final_record.is_correct:
                correct += 1
            self.add_group_stat(category_stats, question.category, final_record.is_correct)
            self.add_group_stat(subject_stats, question.subject, final_record.is_correct)

        run_elapsed_seconds = time.perf_counter() - run_started
        stop_kv_cache_poller(kv_cache_thread, kv_cache_stop)

        total = len(questions)
        result.status = "completed" if failures < total else "failed"
        result.overall_accuracy = ratio(correct, total)
        result.strict_compliance_rate = ratio(strict_ok, total)
        result.failure_rate = ratio(failures, total)
        result.parse_failure_rate = ratio(parse_failures, total)
        result.latency_p50_ms = percentile(latency_stats.latencies, 50)
        result.latency_p95_ms = percentile(latency_stats.latencies, 95)
        result.ttft_p50_ms = percentile(latency_stats.ttfts, 50)
        result.ttft_p95_ms = percentile(latency_stats.ttfts, 95)
        result.tpot_p50_ms = decimal_percentile(latency_stats.tpots, 50)
        result.tpot_p95_ms = decimal_percentile(latency_stats.tpots, 95)
        result.throughput_p50_tps = decimal_percentile(latency_stats.throughputs, 50)
        result.throughput_p95_tps = decimal_percentile(latency_stats.throughputs, 95)
        result.system_throughput_tps = (
            Decimal(str(round(output_tokens / run_elapsed_seconds, 3)))
            if run_elapsed_seconds > 0
            else None
        )
        if kv_cache_samples:
            result.kv_cache_usage_min = Decimal(str(round(min(kv_cache_samples), 4)))
            result.kv_cache_usage_avg = Decimal(str(round(sum(kv_cache_samples) / len(kv_cache_samples), 4)))
            result.kv_cache_usage_max = Decimal(str(round(max(kv_cache_samples), 4)))
        result.input_tokens = input_tokens
        result.output_tokens = output_tokens
        result.estimated_cost_usd = estimated_cost.quantize(Decimal("0.000001"))
        result.category_accuracy = self.serialize_group_stats(category_stats)
        result.subject_accuracy = self.serialize_group_stats(subject_stats)
        result.routing_model_distribution = {
            "small": {
                "count": routing_counts["small"],
                "percent": round(routing_counts["small"] / total * 100, 2) if total else 0.0,
            },
            "large": {
                "count": routing_counts["large"],
                "percent": round(routing_counts["large"] / total * 100, 2) if total else 0.0,
            },
        }
        result.router_latency_p50_ms = percentile(router_latencies, 50)
        result.router_latency_p95_ms = percentile(router_latencies, 95)
        result.scorecard = self.build_scorecard(
            result=result,
            total=total,
            correct=correct,
            failures=failures,
            parse_failures=parse_failures,
            strict_ok=strict_ok,
            reference_average_latency_ms=round((small_model.average_latency_ms + large_model.average_latency_ms) / 2),
            reference_quality_level=round((small_model.quality_level + large_model.quality_level) / 2, 2),
        )
        result.save()

    def add_group_stat(self, stats: dict, key: str, is_correct: bool):
        if not key:
            return
        if key not in stats:
            stats[key] = {"correct": 0, "total": 0}
        stats[key]["total"] += 1
        if is_correct:
            stats[key]["correct"] += 1

    def serialize_group_stats(self, stats: dict) -> dict:
        return {
            key: {
                **value,
                "accuracy": float(ratio(value["correct"], value["total"])),
            }
            for key, value in stats.items()
        }

    def build_scorecard(
        self,
        *,
        result,
        total: int,
        correct: int,
        failures: int,
        parse_failures: int,
        strict_ok: int,
        reference_average_latency_ms=None,
        reference_quality_level=None,
    ) -> dict:
        # routing 타입은 result.model이 없으므로(문항마다 모델이 달라짐) 호출자가
        # small/large 모델을 평균한 대표값을 reference_*로 넘겨줍니다.
        average_latency_ms = reference_average_latency_ms if reference_average_latency_ms is not None else result.model.average_latency_ms
        quality_level = reference_quality_level if reference_quality_level is not None else result.model.quality_level

        accuracy = float(ratio(correct, total))
        strict_rate = float(ratio(strict_ok, total))
        failure_rate = float(ratio(failures, total))
        parse_failure_rate = float(ratio(parse_failures, total))
        reliability = max(0.0, 1.0 - failure_rate - parse_failure_rate)
        p95 = result.latency_p95_ms or average_latency_ms or 0
        cost = float(result.estimated_cost_usd or 0)
        tokens = max(1, result.input_tokens + result.output_tokens)

        performance_score = round((accuracy * 80.0) + (strict_rate * 20.0), 2)
        latency_score = max(0.0, 100.0 - min(p95 / 30.0, 100.0)) if p95 else 60.0
        token_score = min(100.0, (correct / tokens) * 10000.0)
        cost_score = max(0.0, 100.0 - min(cost * 5000.0, 100.0))
        efficiency_score = round((latency_score * 0.45) + (token_score * 0.25) + (cost_score * 0.30), 2)
        capability_score = round((reliability * 70.0) + (min(quality_level, 5) / 5.0 * 30.0), 2)
        total_score = round((performance_score * 0.55) + (efficiency_score * 0.25) + (capability_score * 0.20), 2)
        recommended_role = self.recommend_role(accuracy, p95, failure_rate, total_score)

        return {
            "evaluated_questions": total,
            "correct": correct,
            "failures": failures,
            "parse_failures": parse_failures,
            "performance_score": performance_score,
            "efficiency_score": efficiency_score,
            "capability_score": capability_score,
            "total_score": total_score,
            "reliability_score": round(reliability * 100.0, 2),
            "recommended_role": recommended_role,
            "role_reason": self.role_reason(recommended_role),
            "mode": "pilot_sync_item_logs",
        }

    def recommend_role(self, accuracy: float, p95: int, failure_rate: float, total_score: float) -> str:
        if failure_rate > 0.25:
            return "Escalation Candidate"
        if accuracy >= 0.8 and total_score >= 70:
            return "Accurate Path"
        if p95 and p95 <= 3000 and accuracy >= 0.55:
            return "Fast Path"
        return "Escalation Candidate"

    def role_reason(self, role: str) -> str:
        if role == "Accurate Path":
            return "정확도와 종합 점수가 높아 품질 우선 경로 후보입니다."
        if role == "Fast Path":
            return "지연시간이 낮고 기본 정확도를 만족해 빠른 경로 후보입니다."
        return "실패율, 정확도 또는 지연 조건을 보완한 뒤 정책에 편입하는 것이 안전합니다."
