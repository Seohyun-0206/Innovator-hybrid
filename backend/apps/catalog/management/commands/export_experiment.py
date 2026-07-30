import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.catalog.models import EvaluationItemResult, EvaluationRun


class Command(BaseCommand):
    help = (
        "현재 DB에 있는 실험(EvaluationRun) 하나를 seed_demo가 읽어들일 수 있는 "
        "Django fixture JSON으로 backend/fixtures/experiments/ 아래에 내보냅니다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--run", help="EvaluationRun.name (정확히 일치하는 이름)")
        parser.add_argument("--run-id", type=int, help="EvaluationRun.id (이름이 여러 개 겹칠 때 사용)")

    def handle(self, *args, **options):
        run = self.resolve_run(options)

        run_models = list(run.models.all())
        results = list(run.results.all())
        routing_candidates = [c for c in (getattr(r, "routing_config", None) for r in results) if c]
        result_models = [r.model for r in results if r.model_id]
        routing_models = [
            m
            for c in routing_candidates
            for m in (c.small_model, c.large_model)
            if m
        ]
        all_models = list({m.pk: m for m in run_models + result_models + routing_models}.values())
        credentials = list(
            {m.provider_credential.pk: m.provider_credential for m in all_models if m.provider_credential_id}.values()
        )
        datasets = list({d.pk: d for d in [run.dataset, run.easy_dataset, run.hard_dataset] if d}.values())
        snapshot = getattr(run, "dataset_snapshot", None)
        item_results = list(
            EvaluationItemResult.objects.filter(result__in=results).order_by("result_id", "item_index", "attempt")
        )

        records = []
        records += self.serialize(credentials)
        records += self.serialize(all_models)
        if run.evaluation_method_id:
            records += self.serialize([run.evaluation_method])
        records += self.serialize(datasets)
        records += self.serialize([run])
        if snapshot:
            records += self.serialize([snapshot])
        records += self.serialize(results)
        records += self.serialize(routing_candidates)
        records += self.serialize(item_results)

        scrubbed = self.scrub_portability_fields(records)

        out_dir = Path(__file__).resolve().parents[4] / "fixtures" / "experiments"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slugify(run.name) or f'run-{run.pk}'}.json"
        out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(
            f"Exported experiment '{run.name}' ({len(records)} records) -> {out_path}"
        ))
        if scrubbed:
            self.stdout.write(self.style.WARNING(
                f"{scrubbed} provider credential(s) had their access token excluded for security. "
                "Re-seeding will create them as inactive/without a token - reconfigure via .env "
                "(see seed_vllm_from_env in seed_demo.py) or the admin screen if live calls are needed."
            ))

    def resolve_run(self, options):
        if options.get("run_id"):
            try:
                return EvaluationRun.objects.get(pk=options["run_id"])
            except EvaluationRun.DoesNotExist:
                raise CommandError(f"EvaluationRun id={options['run_id']} not found.")

        name = options.get("run")
        if not name:
            raise CommandError("--run <name> 또는 --run-id <id> 중 하나는 필요합니다.")
        matches = list(EvaluationRun.objects.filter(name=name))
        if not matches:
            raise CommandError(f"EvaluationRun name='{name}' not found.")
        if len(matches) > 1:
            ids = ", ".join(str(m.pk) for m in matches)
            raise CommandError(
                f"'{name}' matches {len(matches)} runs (ids: {ids}). Use --run-id to pick one."
            )
        return matches[0]

    def serialize(self, objects):
        objects = list(objects)
        if not objects:
            return []
        data = serializers.serialize(
            "json", objects, use_natural_foreign_keys=True, use_natural_primary_keys=True
        )
        return json.loads(data)

    def scrub_portability_fields(self, records) -> int:
        """실행 환경마다 달라지거나(사용자 계정), 이 fixture에 포함하지 않은 다른 모델을
        가리키는(GeneratedDataset PK) 필드를 지워서 다른 DB에 안전하게 옮길 수 있게 합니다."""
        scrubbed = 0
        for record in records:
            fields = record["fields"]
            if record["model"] == "catalog.providercredential":
                fields["encrypted_access_token"] = ""
                fields["is_active"] = False
                scrubbed += 1
            elif record["model"] == "catalog.evaluationrun":
                fields["created_by"] = None
            elif record["model"] == "catalog.evaluationdataset":
                fields["uploaded_by"] = None
                # GeneratedDataset은 이 fixture에 포함되지 않으므로(natural_key도 없음) PK
                # 참조를 그대로 두면 다른 DB에서 엉뚱한 row를 가리키게 됩니다.
                fields["source_generated_dataset"] = None
        return scrubbed
