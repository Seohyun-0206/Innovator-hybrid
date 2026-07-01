# 연구계획서: MMLU 기반 OpenAI 모델 비교 평가

## 한눈에 보는 요약

| 항목 | 내용 |
|---|---|
| **연구 목표** | 정확도 중심 비교를 넘어, 비용·지연·실패율을 포함한 모델 선택 근거 제시 |
| **비교 모델** | `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano` |
| **데이터 전략** | MMLU 전수 대신 **카테고리 균형 표본** |
| **핵심 지표** | Accuracy, Cost, Latency, Failure Rate, Scorecard |
| **핵심 산출물** | `outputs/summary/*.json`, `outputs/reports/mmlu_model_comparison.md` |

**문서 목적**: 연구 설계(무엇을, 어떤 조건으로, 어떻게 측정하는지)를 표준화해 보고서·부록·재현 패키지의 기준으로 사용한다.  
**프로토콜 기준**: [MMLU 평가 프로토콜](../experiment-protocols/mmlu-evaluation-protocol.md). 과거 `openai_mmlu` CLI 패키지는 web 중심 구조로 통합하면서 제거되었고, 현재 실행·관리 표면은 web 앱과 Django seed/import 흐름을 기준으로 한다.

---

## 1) 연구 목적과 범위

- 동일 프로토콜로 3개 모델을 비교해 **성능-효율-운영 안정성**을 함께 평가한다.
- 비용 제약으로 인해 MMLU 전수는 기본값으로 사용하지 않고, **카테고리 균형 표본**을 이용한 정량 평가를 기본 설계로 한다.
- 해석 범위는 “MMLU 전체 절대 점수”가 아니라 **동일 조건의 상대 비교**다.

---

## 2) 표준 MMLU 대비 본 연구의 위치

| 구분 | 표준 MMLU(원 저장소 스타일) | 본 연구 |
|---|---|---|
| 답 선택 방식 | logprob 기반 A/B/C/D 선택 | 생성 응답 파싱(A/B/C/D) |
| 주 지표 | 정확도 중심 | 정확도 + 비용 + 지연 + 실패율 + 종합점수 |
| 목표 | 벤치마크 성능 보고 | 배포/운영 의사결정 근거 제공 |

**참고**: 리더보드의 STEM/Humanities/Social/Other 요약 축은 유지하되, 운영 지표를 추가해 분석 깊이를 높인다.

---

## 3) 연구 질문(RQ)과 가설(H)

### 연구 질문

1. **RQ1 성능**: **카테고리 균형 표본**에서 모델 간 정확도 차이는 유의미한가?
2. **RQ2 효율**: 비용·지연 관점에서 어떤 trade-off가 나타나는가?
3. **RQ3 운영**: 실패율이 결과 해석에 미치는 영향은 무엇인가?
4. **RQ4 종합**: 가중치 변화에도 모델 순위는 안정적인가?

### 검증 가설

| ID | 가설 | 검증 지표 | 기대 기여 |
|---|---|---|---|
| **H1 체감수익** | 고가 모델일수록 정확도는 상승하나, 비용 대비 개선폭은 체감한다. | `overall_accuracy`, `cost_per_1k_questions_usd` | 비용 기반 모델 선택 기준 |
| **H2 지연-성능** | 최고 정확도 모델이 항상 최적은 아니며 `Accuracy/Latency` 우위 모델이 존재한다. | `overall_accuracy`, `latency_ms_p50/p95` | SLA 기준 의사결정 |
| **H3 안정성-성능** | `failure_rate`가 높을수록 정확도 저하가 동반된다. | `failure_rate`, `overall_accuracy` | 운영 리스크 정량화 |
| **H4 카테고리 역전** | 전체 평균 우위 모델이 카테고리별 비용효율에서는 역전될 수 있다. | `category_accuracy`, 비용 지표 | 도메인별 라우팅 근거 |
| **H5 길이 민감도** | 입력 토큰 증가 시 지연·비용이 증가하고 모델별 성능 저하 폭이 다르다. | `input_tokens`, `latency_ms`, 정확도 | 긴 문맥 업무 대응 전략 |

---

## 4) 데이터 설계(비용 통제형)

### 4-1. 권장 설계: 카테고리 균형 표본

| 설계 요소 | 권장 기준 |
|---|---|
| 표본 구획(상위 카테고리) | `STEM`, `humanities`, `social_sciences`, `other` |
| 과목 선택 | 카테고리별 동일 개수 과목(예: 각 3~5개) 사전 고정 |
| 문항 수 | 과목당 상한 N(`--max-questions-per-subject N`) 또는 seed 고정 표본 |
| 해석 범위 | 표본 범위 안의 상대 비교(리더보드 전수 점수와 직접 비교 금지) |

### 4-2. 보조 설계

- **전수 평가**: 예산/일정이 허용될 때 선택 수행
- **파일럿**: 파이프라인 검증용(예: 과목당 5~20문항), 본분석과 분리 표기

### 4-3. 실행 흐름

```mermaid
flowchart LR
  subset[Stratified_subject_subset] --> data[MMLU_dev_test]
  data --> prompt[Few_shot_prompt]
  prompt --> api[OpenAI_Responses_API]
  api --> log[JSONL_per_subject]
  log --> metrics[Accuracy_cost_latency]
  metrics --> score[Scorecard_sensitivity]
```

---

## 5) 평가 프로토콜(고정값)

### 실험 조건

| 항목 | 값 |
|---|---|
| few-shot | `k=5` (`--ntrain 5`) |
| 출력 규칙 | A/B/C/D 단일 문자 |
| API | OpenAI Responses API |
| temperature | `0` |
| max_output_tokens | `8` |
| reasoning.effort | `minimal` |
| 재시도 | 최대 5회, 지수 백오프 |

### 채점 규칙

- 응답에서 첫 `A|B|C|D`를 추출해 정답과 비교
- 파싱 실패는 오답 처리
- 문항 로그에 `ok`, `error`, `input_tokens`, `output_tokens`, `latency_ms` 기록

---

## 6) 지표 체계

| 지표 | 정의 | 해석 포인트 |
|---|---|---|
| Accuracy | 정답 수 / 평가 문항 수 | 표본 분모 기준 |
| Category/Subject Accuracy | 카테고리/과목별 정확도 | 도메인별 강약 |
| Cost | 토큰 사용량 × 단가 (`cost_total`, `cost_per_1k`) | 비용 효율 |
| Latency | 문항별 지연, 요약 p50/p95 | 체감 성능/SLA |
| Failure Rate | `ok=false` 비율 | 운영 안정성 |
| Token Efficiency | 정답 수 / 총 토큰 | 계산 효율 |

### 종합 점수(Scorecard)

- Performance + Efficiency + Capability를 min-max 정규화 후 결합
- 기본 가중치: `0.55 / 0.25 / 0.20`
- 민감도: 가중치 시나리오별 순위 변동 확인

---

## 7) 실행 체크리스트

- [ ] 카테고리별 과목 목록 고정(부록 표 작성)
- [ ] 과목당 문항 수 및 seed 고정
- [ ] 실행 CLI 인자 기록 (`outputs/summary/eval_manifest.json`에 자동 기록)
- [ ] `outputs/logs/*.jsonl` 생성 확인
- [ ] `outputs/summary/*.json` 생성 확인
- [ ] 자동 리포트/가설별 결과표 작성

---

## 8) 산출물 패키지

| 산출물 | 경로(기본 출력 루트는 `--output-dir`, 예: `outputs/`) |
|---|---|
| 평가 범위 사전정의(과목·문항·seed) | 연구 부록 + `<DIR>/summary/eval_manifest.json` |
| 프로토콜 | `web/docs/experiment-protocols/mmlu-evaluation-protocol.md` |
| 원시 로그 | `<DIR>/logs/*.jsonl` |
| 요약 지표 | `<DIR>/summary/model_summary.json` |
| 종합 점수·민감도 | `<DIR>/summary/scorecard.json`, `<DIR>/summary/sensitivity.json` |
| 자동 리포트 | `<DIR>/reports/mmlu_model_comparison.md` |
| 연구계획서(본 문서) | `web/docs/research-plans/mmlu-openai-model-evaluation-plan.md` |

### 실행 결과가 나오는 순서(legacy CLI 산출물 기준)

과거 `openai_mmlu` CLI에서 `python -m openai_mmlu.run_eval ... --output-dir <DIR>` 실행이 **끝까지 완료**되면, `<DIR>` 아래에 다음이 **순서대로·자동** 생성되었다. 현재 저장소의 실행 표면은 web 앱이며, 보존된 Ollama 비교 산출물은 `cd web/backend && python manage.py seed_demo`로 import한다.

1. **`<DIR>/logs/{모델명}_{과목}.jsonl`**  
   - 평가 중 문항마다 **한 줄(JSON)** 추가.  
   - 포함 예: `run_id`, 시각, `question_id`, 정답·예측, `is_correct`, `ok`, `error`, 토큰, `latency_ms`, `raw_output` 등.  
   - **중단 후 재실행** 시 이미 있는 `question_id`는 건너뛰므로, 동일 로그에 **이어 쓰기**된다.

2. **`<DIR>/summary/eval_manifest.json`**  
   - **한 번의 실행(run)**에 대응하는 **실험 조건 전부**: `run_id`, `data_dir`, 사용 모델, `ntrain`, `temperature`, `evaluation_mode`(균형 총문항 vs `full_per_subject`), `subset`(과목·표본·`question_selection` 등), `category_subject_counts` 등.  
   - 연구 보고서의 **「재현 패키지」 핵심**으로 삼는다.

3. **`<DIR>/summary/model_summary.json`**  
   - 모델별 **집계 지표**: 정확도, 비용, 지연(p50/p95 등), 실패율, 파싱 실패율, 과목·카테고리별 정확도 등.  
   - 본문 **표·그래프의 숫자**는 원칙적으로 여기서 인용한다.

4. **`<DIR>/summary/scorecard.json`**, **`<DIR>/summary/sensitivity.json`**  
   - 가중치 기반 **종합 점수** 및 **가중치 시나리오별 순위**.  
   - RQ4(순위 안정성)·의사결정 요약에 사용한다.

5. **`<DIR>/reports/mmlu_model_comparison.md`**  
   - 위 JSON을 바탕으로 한 **요약 리포트**(Markdown). 발표·내부 공유용 **1차 읽기**에 쓴다.

### 연구결과는 어떻게 기록하는가

| 기록 목적 | 권장 근거 파일 | 연구 본문·부록에서의 쓰임 |
|---|---|---|
| **무엇을 평가했는가(표본·설계)** | `eval_manifest.json`의 `subset`, `total_questions`, `evaluation_mode` | 방법 절, 표본 정의, 재현 조건 |
| **문항 단위 원시 증거** | `*.jsonl` | 부록·데이터 공개 시; 이상 응답·파싱 실패 사례 인용 |
| **모델 간 정량 비교** | `model_summary.json` | 결과 절 표·가설 H1–H5 검증 수치 |
| **종합 순위·민감도** | `scorecard.json`, `sensitivity.json` | 논의·한계; 가중치에 따른 순위 변동 |
| **실행 단위 식별** | 동일 `run_id`(manifest·각 JSONL 행) | 「실험 A」「실험 B」 구분, Git 커밋·출력 폴더와 짝지음 |

**운영 원칙**: 연구결과(수치·주장)를 적을 때는 **가능한 한 `eval_manifest.json` + `model_summary.json`의 조합**을 근거로 삼고, 개별 문항 주장이 필요할 때만 해당 **JSONL 행**을 인용한다. 실행이 실패·중단된 경우에도 이미 쓰인 로그는 **부분 결과**로 명시하고, 재실행 시 `run_id` 또는 출력 디렉터리를 바꿔 **실험 단위를 혼동하지 않는다.**

---

## 9) 한계와 보완

- 표본 설계는 비용 효율적이지만 전체 MMLU 일반화에는 한계가 있다.
- 카테고리별 표본 불균형 시 가중치/표준오차를 함께 보고한다.
- 파싱 실패와 오답이 같은 결과로 처리되므로, 실패율을 분리 해석한다.

---

## 10) 문서 이력

- 초안: 구현 코드와 동기화한 기본 연구계획 수립
- 개정: 비용 제약 반영, 카테고리 균형 표본을 기본 설계로 전환
- 개정: 실행 산출물 생성 순서·연구 기록(근거 파일) 매핑 명시
- 유지보수 원칙: 모델/단가/CLI/평가 범위 변경 시 본 문서와 부록 동시 업데이트
