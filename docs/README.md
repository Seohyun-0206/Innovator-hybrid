# Web Docs

web 앱에서 연구 계획, 실험 프로토콜, 실행 결과 보고서를 함께 관리합니다.

## Research Plans

- [MMLU OpenAI 모델 평가 계획](research-plans/mmlu-openai-model-evaluation-plan.md)
- [MMLU Ollama 로컬 평가 계획](research-plans/mmlu-ollama-local-evaluation-plan.md)

## Experiment Protocols

- [MMLU 평가 프로토콜](experiment-protocols/mmlu-evaluation-protocol.md)

## Reports

- [4월 활동 보고서 - Hybrid LLM Architecture](reports/april-hybrid-llm-architecture.md)
- [MMLU Ollama 최종 산출물 - Hybrid Architecture](reports/mmlu-ollama-final-hybrid-architecture.md)
- [MMLU OpenAI 모델 비교 리포트 가이드](reports/mmlu-openai-model-comparison-guide.md)

## Archive

- [Legacy outputs 분석](archive/legacy-outputs-analysis.md)
- [Remaining roadmap](remaining-roadmap.md)

## Seed Fixtures

Django demo seed에서 import하는 MMLU 원본 산출물은 `web/backend/fixtures/imported_mmlu/` 아래에 보존합니다.

```bash
cd web/backend
python manage.py seed_demo
```
