# 4월 활동 보고서 - Hybrid LLM Architecture

> 목적: 동일한 8B급 로컬 LLM(`llama3.1:8b`, `qwen3:8b`)의 MMLU 평가 결과를 비교해 **SLA-aware Hybrid Routing의 필요성과 초기 설계 근거**를 도출한다.  
> 기준 결과: `web/backend/fixtures/imported_mmlu/output_ollama3_1_8b`, `web/backend/fixtures/imported_mmlu/output_qwen3_8b`의 `*_metrics.json`, `*_report.md`, `*.jsonl`.  
> 형식: PPT 7장 구성에 맞춘 장표용 콘텐츠.

---

## Slide 1. 과제 개요

### 장표 제목

**동일 8B급 로컬 LLM 비교 기반 Hybrid Architecture 파일럿**

### 핵심 메시지

4월 활동은 완성된 라우터의 성능 보고가 아니라, **동일한 파라미터 규모의 로컬 모델이 품질, 지연, 출력량에서 얼마나 다른 운영 특성을 보이는지 계측한 기준선 연구**다.

### 비교 전제

| 구분 | 내용 |
|---|---|
| 평가 모델 | `llama3.1:8b`, `qwen3:8b` |
| 파라미터 규모 | 동일 8B급 |
| 실행 환경 | Ollama 로컬 API |
| 평가셋 | MMLU 균형 표본 N=48 |
| 결과 파일 | `web/backend/fixtures/imported_mmlu/output_ollama3_1_8b`, `web/backend/fixtures/imported_mmlu/output_qwen3_8b` |
| 비교 관점 | 정확도, 지연, 실패율, 출력 토큰, Score Card |

### 결과 Snapshot

| 지표 | Llama 3.1 8B | Qwen3 8B | 해석 |
|---|---:|---:|---|
| 정확도 | 52.1% (25/48) | 79.2% (38/48) | Qwen +27.1%p |
| 평균 지연 | 1.11s | 16.17s | Llama 약 14.6배 빠름 |
| p95 지연 | 2.65s | 41.92s | Qwen은 timeout 정책 필요 |
| API 실패율 | 0.0% | 0.0% | 둘 다 호출 안정성 확보 |
| 파싱 실패율 | 0.0% | 0.0% | 선택지 추출은 모두 성공 |
| 출력 토큰 | 1,005 | 36,207 | Qwen 약 36.0배 많음 |
| 종합 점수 | 80.1 | 83.6 | Qwen 근소 우위 |
| 후보 역할 | Fast / Baseline | Accurate / Escalation | 역할 분리 근거 확보 |

### 발표 포인트

- 같은 8B급 모델이라도 정확도와 SLA 특성이 크게 다르게 나타남
- Qwen3 8B는 정확도와 Performance 점수에서 우세함
- Llama 3.1 8B는 지연과 출력 효율 면에서 실시간 경로 후보에 적합함
- Hybrid Routing은 모델 우열 경쟁이 아니라, 요청 조건에 따라 역할을 나누는 구조로 설계해야 함

---

## Slide 2. 연구 질문과 검증 관점

### 장표 제목

**동일 8B급 모델 비교에서 확인할 연구 질문**

### 핵심 메시지

동일한 파라미터 수만으로 운영 성격을 예측할 수 없다. 이번 평가는 **정확도 우선 모델과 실시간 응답 모델을 분리할 실증 근거가 있는지** 확인한다.

### 연구 질문

| RQ | 질문 | 운영 의미 |
|---|---|---|
| RQ1 | 동일 8B급 모델 간 정확도 차이가 유의미한가? | 기본 모델과 고정확도 모델 구분 |
| RQ2 | p95 지연 차이가 실시간 SLA 판단 기준으로 충분한가? | timeout 및 Fast Path 기준 |
| RQ3 | 실패율 0%인 모델 간에도 역할 분리가 필요한가? | 안정성 외 지표의 중요성 확인 |
| RQ4 | 출력 토큰 차이가 지연과 자원 부담을 설명하는가? | max token 및 출력 형식 제어 |
| RQ5 | 빠른 모델과 정확한 모델을 조합할 근거가 있는가? | Hybrid Routing Policy 초안 |
| RQ6 | 문항별 로그를 누적 추적할 필요가 있는가? | 연구결과 대시보드 및 관측성 |

### 검증 관점

| 검증 항목 | 사용 지표 | 이번 결과의 의미 |
|---|---|---|
| 품질 | 전체 정확도, 카테고리별 정확도 | Qwen이 모든 대분류에서 우위 |
| SLA | 평균, p50, p95 지연 | Llama가 실시간 응답에 유리 |
| 안정성 | API 실패율, 파싱 실패율 | 둘 다 실패율 0% |
| 출력 효율 | 총 출력 토큰, 문항당 출력 토큰 | Qwen 출력 제어 필요 |
| 종합 판단 | Performance, Efficiency, Capability, Total | Qwen 총점 우위, Llama 효율 우위 |
| 재현성 | metrics, report, jsonl | 집계 수치와 문항별 로그 확보 |

---

## Slide 3. 평가 방식

### 장표 제목

**MMLU 평가 로직과 Multi-Metric Score Card**

### 핵심 메시지

정답률만 비교하지 않고, 로컬 LLM 운영에 필요한 지연, 실패, 출력 토큰, 종합 점수를 함께 계측했다.

### 평가 조건

| 항목 | 내용 |
|---|---|
| 데이터셋 | MMLU |
| 표본 | 카테고리 균형 표본 N=48 |
| 영역 | STEM, Humanities, Social Sciences, Other |
| 모델 | `llama3.1:8b`, `qwen3:8b` |
| 입력 규모 | Llama 20,498 tokens / Qwen 20,790 tokens |
| 비용 | 로컬 실행 기준 $0.00 |
| 실행일 | 2026-05-10 결과 파일 기준 |

### 평가 흐름

```text
MMLU 문항
  -> Ollama 로컬 모델 호출
  -> 모델 raw output 저장
  -> A/B/C/D 선택지 파싱
  -> 정답 비교
  -> 지연, 실패, 토큰 기록
  -> metrics/report/jsonl 생성
  -> Hybrid Routing 관점으로 해석
```

### 결과 파일의 역할

| 파일 | 포함 내용 | 보고서 활용 |
|---|---|---|
| `*_metrics.json` | 정량 지표와 Score Card 원본 | 표·차트 수치 |
| `*_report.md` | 모델별 평가 요약 | 발표용 핵심 지표 확인 |
| `*.jsonl` | 문항별 질문, 응답, 정답 여부, 지연, 토큰 | 출력 형태와 실패 원인 분석 |

---

## Slide 4. 연구 결과 대시보드

### 장표 제목

**평가 결과: Qwen은 정확도, Llama는 응답 효율 우위**

### 핵심 메시지

Qwen3 8B는 정확도와 총점에서 우세하지만, Llama 3.1 8B는 지연과 출력량에서 압도적으로 효율적이다. 따라서 단일 모델 선택보다 **요청 유형별 라우팅**이 더 합리적이다.

### Score Card

| 지표 | Llama 3.1 8B | Qwen3 8B | 우위 |
|---|---:|---:|:---:|
| Performance | 66.5 | 85.4 | Qwen |
| Efficiency | 94.0 | 66.6 | Llama |
| Capability | 100.0 | 100.0 | 동률 |
| Total | 80.1 | 83.6 | Qwen |

```text
Performance  Llama [█████████████░░░░░░░] 66.5
             Qwen  [█████████████████░░░] 85.4

Efficiency   Llama [███████████████████░] 94.0
             Qwen  [█████████████░░░░░░░] 66.6

Total        Llama [████████████████░░░░] 80.1
             Qwen  [█████████████████░░░] 83.6
```

### 핵심 원 지표

| 지표 | Llama 3.1 8B | Qwen3 8B | 비교 |
|---|---:|---:|---|
| 정답 수 | 25/48 | 38/48 | Qwen +13문항 |
| 전체 정확도 | 52.1% | 79.2% | Qwen +27.1%p |
| 평균 지연 | 1.11s | 16.17s | Qwen 약 14.6배 느림 |
| p50 지연 | 0.78s | 10.79s | Qwen 약 13.8배 느림 |
| p95 지연 | 2.65s | 41.92s | Qwen 약 15.8배 느림 |
| 총 입력 토큰 | 20,498 | 20,790 | 거의 동일 |
| 총 출력 토큰 | 1,005 | 36,207 | Qwen 약 36.0배 많음 |
| 문항당 출력 토큰 | 20.9 | 754.3 | 출력 형식 차이 큼 |

### 카테고리별 정확도

| 카테고리 | Llama 3.1 8B | Qwen3 8B | 차이 |
|---|---:|---:|---:|
| STEM | 41.7% | 91.7% | +50.0%p |
| Humanities | 75.0% | 83.3% | +8.3%p |
| Social Sciences | 58.3% | 83.3% | +25.0%p |
| Other | 33.3% | 58.3% | +25.0%p |

### JSONL 관찰

- Llama 3.1 8B는 대부분 짧은 선택지 응답을 생성해 지연과 출력 토큰이 작음
- 일부 Llama 응답은 단일 문자 지시를 벗어나 설명이나 메타 문장을 포함했으며, 이 경우 오답으로 이어진 사례가 있음
- Qwen3 8B는 정답률이 높지만 `Answer: X` 또는 설명을 포함한 긴 응답이 자주 발생해 출력 토큰과 지연이 크게 증가함
- 파싱 실패율은 두 모델 모두 0%이나, 실제 운영에서는 "짧고 구조화된 응답"을 별도 품질 지표로 관리할 필요가 있음

---

## Slide 5. 운영 관점 검증

### 장표 제목

**운영 관점 검증: 정확도-지연-출력량의 분리**

### 핵심 메시지

이번 비교에서 핵심 차이는 실패율이 아니라 **정확도, 지연, 출력량의 균형**이다. 같은 8B급이라도 하나의 모델이 모든 요청에 최적인 것은 아니었다.

### 검증 요약

| 검증 질문 | 결과 | 운영 해석 |
|---|---|---|
| 정확도 우선 모델이 있는가? | Qwen 79.2%, Llama 52.1% | 고난도·검증 요청은 Qwen 후보 |
| 실시간 응답 후보가 있는가? | Llama p95 2.65s | 짧은 SLA 요청은 Llama 후보 |
| 실패율이 역할 분리를 설명하는가? | 두 모델 모두 API/파싱 실패율 0% | 실패율만으로는 모델 선택 불가 |
| 출력량이 운영 부담을 만드는가? | Qwen 출력 토큰 36,207 | token control과 prompt tuning 필요 |
| 동일 입력 조건이었는가? | 입력 토큰 20,498 vs 20,790 | 결과 차이는 입력량보다 모델 응답 성향 영향이 큼 |
| 종합 점수만으로 선택 가능한가? | Qwen 83.6, Llama 80.1 | 총점 차이는 작지만 운영 특성 차이는 큼 |

### 지연 비교

```text
Llama 3.1 8B   평균 1.11s   p50 0.78s   p95 2.65s
Qwen3 8B       평균 16.17s  p50 10.79s  p95 41.92s

p95 기준:
Llama [█░░░░░░░░░░░░░░░░░░░]  2.65s
Qwen  [████████████████████] 41.92s
```

### 출력 토큰 비교

```text
Llama 3.1 8B   총 1,005 tokens   평균 20.9 tokens/question
Qwen3 8B       총 36,207 tokens  평균 754.3 tokens/question

Qwen은 Llama 대비 약 36.0배 많은 출력 토큰을 생성
```

### 운영 결론

- 실시간 질의는 Llama 3.1 8B를 우선 후보로 둘 수 있음
- 정확도와 추론 품질이 중요한 질의는 Qwen3 8B를 우선 후보로 둘 수 있음
- Qwen3 8B를 동기 응답 경로에 직접 배치하려면 timeout, max token, structured output 정책이 필요함
- Llama 3.1 8B는 빠르지만 정확도 보완을 위해 confidence 또는 escalation 기준이 필요함

---

## Slide 6. Hybrid Routing 초기 설계안

### 장표 제목

**SLA-aware Hybrid Routing 초기 설계안**

### 핵심 메시지

4월 결과를 바탕으로, Llama 3.1 8B는 빠른 기본 응답 후보로, Qwen3 8B는 정확도 우선 또는 2차 검증 후보로 배치하는 라우팅 가설을 수립한다.

### 후보 경로

| 경로 | 우선 모델 | 사용 조건 | 근거 |
|---|---|---|---|
| Fast Path | Llama 3.1 8B | 짧은 SLA, 저위험, 간단 질의 | p95 2.65s, 출력 토큰 1,005 |
| Accurate Path | Qwen3 8B | 정확도 우선, 고난도, 비동기 허용 | 정확도 79.2%, 전 카테고리 우위 |
| Escalation Path | Qwen3 8B | Llama 응답 신뢰도 낮음 | Llama 정확도 보완 |
| Token-Control Path | Qwen3 8B | 긴 설명 발생 가능 질의 | 출력 토큰 약 36배 |
| Observability | 공통 | 모든 호출 | 모델 선택, 지연, 실패, 토큰 누적 |

### Architecture Diagram

```text
사용자 요청
   |
   v
Request Classifier
난이도 / SLA / 위험도 / 출력 길이 요구 판단
   |
   +----------------------+----------------------+
   |                      |                      |
   v                      v                      v
Llama 3.1 8B          Qwen3 8B              Qwen3 8B
Fast Path             Accurate Path         Escalation Path
   |                      |                      |
   |                      +-> timeout / max_tokens / structured output
   |
   +-> low confidence or high risk -> Qwen escalation

공통 로그:
selected_model / latency / parse_result / correctness / input_tokens / output_tokens
```

### 초기 Routing Policy 후보

| 조건 | 후보 정책 |
|---|---|
| SLA가 3초 내외인 요청 | Llama 3.1 8B 우선 |
| 정확도 우선 또는 복잡한 전문 문항 | Qwen3 8B 우선 |
| Llama 응답 신뢰도 낮음 | Qwen3 8B로 재질의 또는 검증 |
| Qwen 호출 예상 | max token 제한, 단답형 system prompt, timeout 적용 |
| 모든 요청 | 문항별 로그와 집계 지표 저장 |

### 설계상 주의점

- 이번 결과는 N=48 파일럿 평가이므로 운영 정책의 확정값이 아니라 기준선으로 사용해야 함
- Qwen3 8B의 높은 정확도는 장점이지만, 현재 출력 성향 그대로는 실시간 경로에 부담이 큼
- Llama 3.1 8B는 빠르지만 오답률이 높아 고위험 요청에는 단독 사용이 적합하지 않음

---

## Slide 7. 5월 연구 계획

### 장표 제목

**5월 연구 계획: 대시보드, 출력 제어, Routing Policy**

### 핵심 메시지

4월은 동일 8B급 모델의 운영 특성을 계측한 파일럿 단계다. 5월에는 결과를 지속 추적하는 대시보드와 실제 라우팅 정책 초안을 만들고, Qwen 출력 제어와 timeout 조건을 추가 실험한다.

### 한계

| 한계 | 설명 |
|---|---|
| 표본 규모 | N=48로 전수 MMLU 성능을 대표하지 않음 |
| 단일 환경 | 로컬 PC와 Ollama 설정에 의존 |
| Router 미구현 | end-to-end 라우팅 개선율은 아직 미측정 |
| 출력 형식 | 단일 문자 응답 준수율을 별도 지표로 분리해야 함 |
| 업무 적합성 | 실제 서비스 요청 기반 평가셋이 필요 |

### 5월 주차별 계획

| 주차 | 목표 | 주요 작업 | 산출물 |
|---|---|---|---|
| 1주차 | 지표 정의와 대시보드 기획 | metrics/jsonl 스키마 정리, KPI 확정 | 지표 정의서, 화면 구성안 |
| 2주차 | 대시보드 MVP 구현 | Score Card, 정확도, p95, 토큰 차트 구현 | Dashboard MVP |
| 3주차 | Routing Policy 초안 | Fast/Accurate/Escalation 기준 정의 | Routing Policy 문서 |
| 4주차 | 추가 실험 | Qwen 출력 제어, timeout, strict answer prompt 실험 | 5월 결과 보고서 |

### 대시보드 개발 범위

| 화면 | 포함 내용 | 목적 |
|---|---|---|
| Overview | 모델별 핵심 지표 Snapshot | 전체 상태 요약 |
| Score Card | Performance, Efficiency, Capability, Total | 모델별 역할 비교 |
| Accuracy | 전체·카테고리별 정확도 | Accurate 후보 판단 |
| SLA | 평균, p50, p95 지연 | Fast 후보와 timeout 기준 판단 |
| Reliability | API 실패율, 파싱 실패율, 실패 건수 | 안정성 확인 |
| Token | 입력/출력 토큰, 문항당 출력 토큰 | 출력 제어 필요성 판단 |
| Logs | 문항별 raw output, parsed answer, latency | 원인 분석과 재현성 확보 |

### 마무리 문장

이번 비교의 핵심은 Qwen3 8B와 Llama 3.1 8B의 우열을 단정하는 것이 아니다. **동일한 8B급 모델도 정확도와 SLA 특성이 크게 다르므로, Hybrid Architecture는 모델을 하나로 고르는 방식보다 요청 조건에 따라 빠른 경로와 정확한 경로를 나누는 방식으로 설계해야 한다.**

---

## PPT 구성 요약

| # | 장표 | 핵심 내용 |
|---|---|---|
| 1 | 과제 개요 | 동일 8B급 로컬 모델 비교와 파일럿 목적 |
| 2 | 연구 질문 | 정확도, p95, 출력 토큰, 라우팅 기준 |
| 3 | 평가 방식 | MMLU 평가 흐름과 결과 파일 역할 |
| 4 | 결과 대시보드 | Score Card, 원 지표, 카테고리 정확도 |
| 5 | 운영 검증 | 정확도-지연-출력량의 역할 분리 |
| 6 | 초기 Architecture | Fast/Accurate/Escalation/Token-Control 경로 |
| 7 | 5월 계획 | 대시보드 MVP, Routing Policy, 출력 제어 실험 |

---

*본 활동 보고서는 `web/backend/fixtures/imported_mmlu/output_ollama3_1_8b/llama3.1_8b_20260510_211025_metrics.json`, `web/backend/fixtures/imported_mmlu/output_ollama3_1_8b/llama3.1_8b_20260510_211025_report.md`, `web/backend/fixtures/imported_mmlu/output_ollama3_1_8b/llama3.1_8b_20260510_210932.jsonl`, `web/backend/fixtures/imported_mmlu/output_qwen3_8b/qwen3_8b_20260510_224004_metrics.json`, `web/backend/fixtures/imported_mmlu/output_qwen3_8b/qwen3_8b_20260510_224004_report.md`, `web/backend/fixtures/imported_mmlu/output_qwen3_8b/qwen3_8b_20260510_222708.jsonl` 결과를 바탕으로 작성되었습니다.*
