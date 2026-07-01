# 연구계획서: MMLU 기반 Ollama 로컬 평가

## 한눈에 보는 요약

| 항목 | 내용 |
|---|---|
| **연구 목표** | 단일 모델 우열 비교가 아니라, 로컬 LLM을 실제 서비스에 배치할 때 필요한 **SLA-aware Hybrid Routing** 근거를 제시한다. |
| **비교 단위** | Ollama 모델 태그별 성능·지연·실패·토큰 특성. 각 모델을 **기본 응답, escalation, fallback, 검증 경로** 중 어디에 둘지 판단한다. |
| **데이터 전략** | MMLU **카테고리 균형 표본**(상위 영역별 과목 수 맞춤, 문항 상한·시드 고정). |
| **핵심 지표** | Relaxed 정확도, 카테고리별 정확도, p50/p95 지연, 실패율, 파싱 실패율, 출력 토큰, Score Card. |
| **핵심 산출물** | `eval_manifest.json`, `*.jsonl`, `model_summary.json`, `scorecard.json`, Hybrid Routing 정책 제안. |

**문서 목적**: Ollama 로컬 평가에서 **연구 목적 → 연구 질문 → 가설 → 지표 → Hybrid Architecture 해석**을 정리한다. 프로토콜 세부는 [MMLU 평가 프로토콜](../experiment-protocols/mmlu-evaluation-protocol.md)을 기준으로 한다. 과거 `ollama_mmlu` CLI 패키지는 web 중심 구조로 통합하면서 제거되었고, 현재 보존된 비교 산출물은 Django `seed_demo` fixture로 import된다.

---

## 1) 연구 목적과 범위

### 공통 목적

- **동일 머신·동일 Ollama 설정**에서 MMLU **카테고리 균형 표본**을 평가해 로컬 LLM 서비스 운영에 쓸 근거를 만든다.
- **Relaxed**(응답에서 첫 `A|B|C|D` 매칭), 지연, 실패율, 출력 토큰을 함께 보아 모델을 단일 순위가 아니라 **서비스 경로별 역할**로 해석한다.
- 평가 결과를 **기본 응답 경로(Fast Path)**, **고정확도 경로(Accurate Path)**, **대체 응답 경로(Fallback Path)**, **상향 검증 경로(Escalation Path)** 설계에 연결한다.
- 해석은 “MMLU 전수 절대 순위”가 아니라 **고정 표본·고정 하드웨어·고정 프로토콜** 안에서 수행한다.

### 범위

| 포함 | 제외 또는 부록만 |
|---|---|
| 카테고리별 과목·문항 상한·시드, few-shot `k`, 샘플링·`num_ctx`, 동시성 정의 | 다른 PC·GPU에서의 지연을 본문 결론으로 일반화하지 않음 |
| 지연(p50/p95), 실패율, strict/relaxed, JSONL·manifest | 본 문서 범위 밖의 앱별 부하 테스트(필요 시 별도 설계) |

---

## 2) 표준 MMLU 대비 본 연구의 위치

| 구분 | 표준 MMLU(원 저장소 스타일) | 본 연구(Ollama·로컬) |
|---|---|---|
| 답 선택 | logprob 기반 등 | 생성 응답에서 **relaxed 파싱** + **strict 준수** 병행 |
| 지표 | 정확도 중심 | 정확도·도메인 편차·p95 지연·실패·출력 토큰·종합 점수 |
| 목표 | 벤치마크 보고 | **SLA-aware Hybrid Routing**을 위한 모델 역할 정의 |

---

## 3) 연구 질문(RQ)과 검증 가설(H)

본 연구는 "어떤 로컬 모델이 더 좋은가"보다 **LLM 서비스를 안정적으로 운영하려면 어떤 요청을 어떤 모델 경로로 보내야 하는가**를 묻는다. 따라서 정확도뿐 아니라 SLA, tail latency, 실패율, 출력 제어, 관측 가능성을 함께 검증한다.

### 연구 질문

1. **RQ1 SLA 적합성**: MMLU에서 높은 정확도를 보이는 모델이 실시간 LLM 서비스의 기본 응답 경로에도 적합한가?
2. **RQ2 Tail Latency**: 평균 지연보다 p95 지연과 타임아웃 구간이 운영 리스크를 더 잘 설명하는가?
3. **RQ3 Failure-Aware 운영**: 정확도가 높은 모델이라도 API 실패율이 존재하면 fallback 없이 단독 운영할 수 있는가?
4. **RQ4 Token Control**: 출력 토큰 수 증가는 지연, 자원 점유, 처리량 저하의 원인이 되는가?
5. **RQ5 Cascading 구조**: 빠른 모델을 1차 처리기로 사용하고 고난도 요청만 고성능 모델로 escalation하는 구조가 합리적인가?
6. **RQ6 Observability**: LLM 서비스 운영에는 정답률뿐 아니라 지연, 실패, 토큰, 선택 모델, fallback 여부를 추적하는 로그가 필요한가?

### 검증 가설

| ID | 가설 | 검증 지표 | 기대 기여 |
|---|---|---|---|
| **H1 SLA 적합성** | 전체 정확도 1위 모델이 실시간 기본 응답 모델로도 최적인 것은 아니다. | `overall_accuracy`, `latency_ms_p95`, `total_score` | 최고 성능 모델의 기본 경로 배치 위험 판단 |
| **H2 Tail Risk** | 평균 지연보다 p95 지연이 사용자 경험과 timeout 정책 설계에 더 직접적인 근거가 된다. | `latency_ms_mean`, `latency_ms_p50`, `latency_ms_p95` | SLA 기준, timeout guard 기준 수립 |
| **H3 Failure-Aware Routing** | 실패율이 있는 고성능 모델은 단독 사용보다 fallback 모델과 결합할 때 운영 적합성이 높다. | `failure_rate`, `api_failure_count`, `ok=false` 로그 | retry/fallback 경로 설계 |
| **H4 Token Control** | 출력 토큰 수가 큰 모델은 정확도와 별개로 지연·자원 점유·처리량 저하를 유발한다. | `total_output_tokens`, `avg_output_tokens`, `latency_ms_p95` | `max_tokens`, structured output, stop condition 필요성 |
| **H5 Cascading Efficiency** | 빠르고 안정적인 모델을 1차 처리하고, 고난도 요청만 고성능 모델로 넘기면 단일 고성능 모델 운영보다 서비스 설계가 유리하다. | 정확도, 지연, 실패율, Score Card 비교 | Fast Path / Accurate Path 역할 분담 |
| **H6 Observability** | 문항 단위 로그가 있어야 품질 저하, 지연 증가, 실패 원인을 사후 분석할 수 있다. | `*.jsonl`의 `latency_ms`, `error`, `raw_output`, `input_tokens`, `output_tokens` | 운영 모니터링·장애 분석 체계 |

### Hybrid Architecture 해석 기준

| 평가 결과 | 서비스 경로 해석 |
|---|---|
| 낮은 지연 + 낮은 실패율 | **Fast Path** 또는 **Fallback Path** 후보 |
| 높은 정확도 + 긴 지연 | **Accurate Path**, 비동기 분석, 고난도 요청 처리 후보 |
| 높은 정확도 + 실패율 존재 | 기본 경로 단독 배치보다 timeout/retry/fallback이 필요한 후보 |
| 출력 토큰 과다 | 출력 길이 제한, 구조화 응답, stop condition 적용 대상 |
| 카테고리별 성능 편차 | 도메인 기반 routing 또는 escalation 기준 |

### 보조 연구 유형

- **후보 비교·크기 스윕**: 모델 크기 또는 계열별 정확도, 지연, 실패율 변화를 비교한다.
- **임계값 적합성 검증**: 특정 서비스 SLA 기준을 정하고 각 모델이 충족하는지 판정한다.
- **파이프라인 검증**: strict 출력, 파싱 실패, 재시도, timeout 정책을 실제 자동화 흐름에 연결한다.

---

## 4) 데이터 설계

| 설계 요소 | 권장 기준 |
|---|---|
| 표본 구획(상위 카테고리) | `STEM`, `humanities`, `social_sciences`, `other` |
| 과목 선택 | 카테고리별 동일 개수 과목(예: 각 3~5개) 사전 고정 |
| 문항 수 | 과목당 상한 N, `seed` 고정 |
| 해석 | 표본 범위 안의 결론; **전수 리더보드 점수와 숫자 직접 비교**는 하지 않는다. |

---

## 5) 평가 프로토콜(로컬 고정값 예시)

| 항목 | 권장 |
|---|---|
| few-shot | `k=5` |
| 출력 규칙 | 채점용 `A/B/C/D` — strict 정의를 부록에 한 줄 고정 |
| 추론 | Ollama Chat 호환 API, `temperature=0` 등 사전 고정 |
| 컨텍스트 | `num_ctx` 등 **모델 간 동일** 또는 부록에 예외 규칙 명시 |
| 동시성 | 비교 실험 시 **1** 권장; 운영 검증(유형 C)은 별도 정의 |
| 재시도 | 최대 횟수·백오프 정책을 프로토콜에 고정 |

**Strict 정의 예**: 출력 전체가 공백 제외 후 정확히 한 글자이며 그 글자가 `A|B|C|D`인 경우만 `strict_ok=true`.

---

## 6) 지표 체계

| 지표 | 정의 | 서비스 운영 해석 |
|---|---|---|
| **Relaxed accuracy** | relaxed 규칙으로 추출한 선택지가 정답과 일치한 비율 | 지식 기반 문제 해결 능력 |
| **Category accuracy** | 상위 카테고리별 정답률 | 도메인 기반 routing/elevation 기준 |
| **Strict compliance rate** | `strict_ok=true` 문항 비율 | 자동화 파이프라인의 구조화 출력 적합성 |
| **Latency mean/p50/p95** | 문항별 지연(ms)의 평균·중앙값·95백분위수 | 사용자 체감 속도와 tail latency 리스크 |
| **Failure rate** | `ok=false` 비율(또는 정의한 실패 조건) | fallback, retry, timeout 정책 필요성 |
| **Parse failure rate** | 선택지 추출 실패 비율 | 자동 채점·자동 후처리 가능성 |
| **Output tokens** | 모델이 생성한 총 출력 토큰 수 | 지연, 자원 점유, 처리량 저하 원인 |
| **Score Card** | Performance, Efficiency, Capability 가중 종합 점수 | 단일 순위와 서비스 경로 역할을 함께 해석 |

**확장(선택)**: 처리량(문항/시간), VRAM 피크, 반복 실행 편차, 실제 router 선택 로그, fallback 발생률.

---

## 7) 실행 체크리스트

- [ ] 연구 목적을 **SLA-aware Hybrid Routing** 관점으로 명시
- [ ] PC 사양·Ollama 버전·모델 태그·`num_ctx`·동시성 고정
- [ ] Strict/Relaxed 정의 문서화
- [ ] 카테고리별 과목·문항 수·seed 고정
- [ ] `eval_manifest.json`에 위 조건 반영
- [ ] JSONL·`model_summary.json`·Score Card·리포트 생성 확인
- [ ] 결과 절에서 H1~H6 검증표와 Fast/Accurate/Fallback/Escalation 경로 해석 작성

---

## 8) 산출물 패키지

| 산출물 | 설명(기본 출력 루트는 `--output-dir`, 예: `outputs_ollama/`) |
|---|---|
| `<DIR>/summary/eval_manifest.json` | 실행 조건·표본·`run_id`, `backend`, `evaluation_mode` 등 |
| `<DIR>/logs/*.jsonl` | 문항 단위 raw, strict/relaxed, 지연, ok/error |
| `<DIR>/summary/model_summary.json` | 모델별 4지표 + (선택) 카테고리 블록 |
| `<DIR>/summary/scorecard.json` 등 | 종합 점수·민감도 |
| `<DIR>/reports/mmlu_ollama_comparison.md` | 모델별 원 지표, Score Card, Hybrid Routing 해석 요약 |

### 실행 결과가 나오는 순서(legacy CLI 산출물 기준)

과거 `ollama_mmlu` CLI에서 `python -m ollama_mmlu.run_eval ... --output-dir <DIR>`(기본 예: `outputs_ollama/`) 실행이 **끝까지 완료**되면, `<DIR>` 아래에 다음이 **순서대로·자동** 생성되었다. 현재 저장소의 실행 표면은 web 앱이며, 보존된 Ollama 비교 산출물은 `cd web/backend && python manage.py seed_demo`로 import한다.

1. **`<DIR>/logs/{모델명}_{과목}.jsonl`**  
   - 문항마다 **한 줄(JSON)**. OpenAI 패키지와 동일하게 `run_id`, `question_id`, 정답·예측, `is_correct`, `ok`, 토큰·지연, `raw_output` 등.  
   - **Ollama 전용**: `strict_ok`(단일 문자 A–D 준수 여부)로 형식 지표를 나중에 집계한다.  
   - 재실행 시 동일 `question_id`는 건너뛴다(이어 쓰기).

2. **`<DIR>/summary/eval_manifest.json`**  
   - `run_id`, `backend: ollama`, `evaluation_mode`, `subset`, `total_questions`(균형 모드일 때), PC·Ollama 버전을 **수동으로 부록에 적은 내용**과 함께 **재현 조건의 정본**으로 둔다.

3. **`<DIR>/summary/model_summary.json`**  
   - 모델별 **relaxed 정확도(`overall_accuracy`)**, **`strict_compliance_rate`**, 지연·실패·파싱 실패 등.  
   - H1~H4의 **정량 결론**은 우선 이 파일에서 읽는다.

4. **`<DIR>/summary/scorecard.json`**, **`<DIR>/summary/sensitivity.json`**  
   - 로컬 메타(비용 0) 기준 min-max **종합 점수** 및 시나리오별 순위. 해석 시 **「비용 축 없음」**을 본문에 명시한다.

5. **`<DIR>/reports/mmlu_ollama_comparison.md`**  
   - 요약 Markdown. 열에 **Strict** 등이 포함된다.

### 연구결과는 어떻게 기록하는가

| 기록 목적 | 권장 근거 파일 | 연구 본문·부록에서의 쓰임 |
|---|---|---|
| **표본·로컬 조건** | `eval_manifest.json` + 부록(하드웨어·Ollama 버전·`num_ctx` 등) | 방법·환경 절; 단일 PC 결론의 한계와 짝 |
| **SLA 적합성** | `model_summary.json`의 `overall_accuracy`, `latency_ms_p95` | H1·H2 검증; 기본 응답 경로 적합성 판단 |
| **Failure-aware 운영** | 동 파일의 `failure_rate`; `*.jsonl`의 `ok`, `error` | H3 검증; retry/fallback 설계 |
| **Token control** | `output_tokens`, `raw_output`, 지연 지표 | H4 검증; 출력 길이 제한·structured output 설계 |
| **Hybrid 역할 분담** | `scorecard.json`, `model_summary.json` | H5 검증; Fast/Accurate/Fallback 경로 정의 |
| **관측 가능성** | `*.jsonl`의 문항 단위 로그 | H6 검증; 장애 분석·품질 회귀 추적 |
| **실험 단위** | `run_id` | 실행별 결과를 혼동하지 않도록 폴더·Git과 함께 기록 |

**운영 원칙**: 로컬 연구는 **동일 PC·동일 manifest**를 한 **실험(run)**으로 묶어 보고한다. 수치 표는 **`model_summary.json`**을 출처로 표기하고, 결과 절에서는 **「정확도=품질 근거, p95=서비스 tail risk, 실패율=fallback 필요성, 출력 토큰=자원·지연 부담」**을 함께 해석한다.

---

## 9) 한계와 보완

- 결론은 **단일 PC·고정 설정**에 국한된다.
- Relaxed와 strict는 성격이 다르다 — **한 지표만으로 능력을 단정하지 않는다.**
- 표본 설계는 전체 MMLU 일반화에 한계가 있다.
- Ollama·드라이버 업그레이드 시 지연이 변할 수 있으므로 **버전을 manifest에 고정**한다.
- 본 계획의 Hybrid Routing 결론은 개별 모델 평가 결과를 바탕으로 한 **아키텍처 설계 근거**다. 실제 router를 구현한 뒤의 end-to-end 품질, 평균 지연, fallback 발생률은 후속 실험으로 검증한다.
- 실제 서비스 적용 시에는 MMLU 외에 업무별 평가셋, 사용자 요청 분포, 위험도 분류 기준, timeout/retry 정책을 추가해야 한다.

---

## 10) 문서 이력

- 초안: Ollama 로컬 평가용 목적·유형·RQ/H·4지표·산출물
- 개정: 부수 서술 정리, Ollama 로컬 평가 본문에 집중
- 개정: 실행 산출물 생성 순서·연구 기록(근거 파일) 매핑 명시
- 개정: SLA-aware Hybrid Routing 관점의 연구 질문·가설·검증 지표로 재구성
