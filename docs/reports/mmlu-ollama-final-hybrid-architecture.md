# MMLU 로컬 평가 — 최종 산출물 (SLA-aware Hybrid LLM Architecture)

> **PPT 전환 가이드**  
> 아래 `##` 제목 = **슬라이드 1장** 권장. 단순 모델 비교가 아니라, LLM 서비스를 운영할 때의 **모델 라우팅·fallback·timeout·관측 가능성** 근거로 읽어야 합니다.

**데이터 출처 (고정, legacy 산출물 요약)**  
- `llama3:latest` → legacy `outputs_ollama_3/llama3_latest_20260421_132647_*` 요약. 원본 과거 산출물 폴더는 web 중심 정리에서 제거됨.  
- `qwen3.5:9b` → legacy `outputs_qwen3_5/qwen3.5_9b_20260427_114641_*` 요약. 원본 과거 산출물 폴더는 web 중심 정리에서 제거됨.  
- 공통: **문항 수 48**, MMLU **카테고리 균형 표본**, Ollama **로컬** API  
- 범위 밖: `qwen3.5:27b`는 일부 로그만 존재하며 완주 결과가 아니므로 본 결론에서 제외

---

## 1. 표지 · 연구 결론

| 항목 | 내용 |
|------|------|
| **제목** | MMLU 기반 SLA-aware Hybrid LLM Architecture 평가 |
| **평가 대상** | `llama3:latest` vs `qwen3.5:9b` |
| **평가 조건** | 동일 MMLU 균형 표본 N=48, 동일 로컬 Ollama 환경 |
| **핵심 결론** | 본 결과는 "어느 모델이 더 좋은가"보다 **LLM 서비스를 안정적으로 운영하기 위해 요청별 SLA·위험도·난이도에 따라 모델 경로를 분리해야 한다**는 근거를 제공한다. |

### 한 줄 메시지

Qwen3.5-9B는 고정확도 경로에 적합하지만 지연·실패·출력량 제어가 필요하고, Llama 3는 기본 응답·저지연·fallback 경로에 적합하다.

### 결과 대시보드

```text
핵심 지표 Snapshot

                 Llama 3                  Qwen3.5-9B
정확도           33.3%                    92.9%
p95 지연         1.44s                    120.0s
API 실패율       0.0%                     12.5%
출력 토큰        345                      60,530
추천 경로        Fast / Fallback          Accurate / Escalation
```

```text
서비스 관점 요약

Llama 3      = 빠른 기본 응답 + 실패 대응 경로
Qwen3.5-9B   = 고정확도 처리 + 검증/상향 경로
```

---

## 2. 연구 질문과 검증 가설

### 연구 질문

1. **RQ1 SLA 적합성**: MMLU에서 높은 정확도를 보이는 모델이 실시간 LLM 서비스의 기본 응답 경로에도 적합한가?
2. **RQ2 Tail Latency**: 평균 지연보다 p95 지연과 타임아웃 구간이 운영 리스크를 더 잘 설명하는가?
3. **RQ3 Failure-Aware 운영**: 정확도가 높은 모델이라도 API 실패율이 존재하면 fallback 없이 단독 운영할 수 있는가?
4. **RQ4 Token Control**: 출력 토큰 수 증가는 지연, 자원 점유, 처리량 저하의 원인이 되는가?
5. **RQ5 Cascading 구조**: 빠른 모델을 1차 처리기로 사용하고 고난도 요청만 고성능 모델로 escalation하는 구조가 합리적인가?
6. **RQ6 Observability**: LLM 서비스 운영에는 정답률뿐 아니라 지연, 실패, 토큰, 선택 모델, fallback 여부를 추적하는 로그가 필요한가?

### 검증 가설

| ID | 가설 | 검증 지표 |
|---|---|---|
| **H1 SLA 적합성** | 전체 정확도 1위 모델이 실시간 기본 응답 모델로도 최적인 것은 아니다. | 정확도, p95 지연, 종합 점수 |
| **H2 Tail Risk** | 평균 지연보다 p95 지연이 timeout 정책 설계에 더 직접적인 근거가 된다. | 평균, p50, p95 지연 |
| **H3 Failure-Aware Routing** | 실패율이 있는 고성능 모델은 fallback 모델과 결합해야 운영 적합성이 높다. | API 실패율, 실패 건수 |
| **H4 Token Control** | 출력 토큰 수가 큰 모델은 정확도와 별개로 지연·자원 점유를 증가시킨다. | 출력 토큰, 지연 |
| **H5 Cascading Efficiency** | 빠르고 안정적인 모델과 고정확도 모델은 단일 순위가 아니라 경로별 역할로 배치해야 한다. | 정확도, 지연, 실패율, Score Card |
| **H6 Observability** | 문항 단위 로그가 있어야 품질 저하, 지연 증가, 실패 원인을 사후 분석할 수 있다. | JSONL 로그의 원시 응답·지연·오류·토큰 |

---

## 3. 평가 로직과 지표

### 평가 흐름

```text
MMLU 문항 입력
  -> Ollama 모델 응답 생성
  -> A/B/C/D 선택지 추출
  -> 정답 비교
  -> 지연·실패·토큰·원시 응답 기록
  -> 모델별 지표 집계
  -> Hybrid Architecture 역할 해석
```

### 지표 체계

| 평가 축 | 지표 | 서비스 운영상 의미 |
|---|---|---|
| 품질 | 전체 정확도 | 고난도 질의 처리 가능성 |
| 품질 | 카테고리별 정확도 | 도메인 기반 routing/elevation 기준 |
| SLA | 평균, p50, p95 지연 | 실시간 응답 가능성과 tail latency 리스크 |
| 안정성 | API 실패율 | fallback, retry, timeout guard 필요성 |
| 자동화 | 파싱 실패율 | 후처리·자동화 파이프라인 적합성 |
| 자원 | 출력 토큰 수 | 긴 생성으로 인한 지연·자원 점유 |
| 종합 | Performance/Efficiency/Capability | 단일 점수와 경로별 역할을 함께 해석 |

---

## 4. Score Card와 원 지표

**가중치:** Performance **55%** · Efficiency **25%** · Capability **20%**

| 지표 (0~100) | Llama 3 | Qwen3.5-9B | 우위 |
|--------------|--------:|------------:|:---:|
| **Performance** | 53.3 | 91.3 | Qwen |
| **Efficiency** | 94.6 | 43.5 | Llama |
| **Capability** | 100.0 | 87.5 | Llama |
| **종합 (Total)** | **73.0** | **78.6** | Qwen |

### Score Card 막대그래프

```text
Score Card (0~100)

Performance
Llama 3      [███████████░░░░░░░░░] 53.3
Qwen3.5-9B   [██████████████████░░] 91.3

Efficiency
Llama 3      [███████████████████░] 94.6
Qwen3.5-9B   [█████████░░░░░░░░░░░] 43.5

Capability
Llama 3      [████████████████████] 100.0
Qwen3.5-9B   [█████████████████░░░] 87.5

Total
Llama 3      [███████████████░░░░░] 73.0
Qwen3.5-9B   [████████████████░░░░] 78.6
```

**읽는 법:** Qwen3.5-9B는 종합 점수와 Performance에서 우세하지만, Efficiency와 Capability는 Llama 3가 우세하다. 따라서 종합 1위 모델을 모든 요청에 배치하는 방식보다, 요청 경로별 역할 분리가 더 적합하다.

### 핵심 원 지표

| 지표 | Llama 3 | Qwen3.5-9B | 운영 해석 |
|---|---:|---:|---|
| 전체 정확도 | 33.3% | 92.9% | 고난도 지식 처리에는 Qwen 우세 |
| 평균 지연 | 0.79s | 64.1s | Qwen은 실시간 기본 경로에 부담 |
| p50 지연 | 0.64s | 61.3s | Qwen은 일반 응답도 장시간 |
| p95 지연 | 1.44s | 120.0s | Qwen은 timeout guard 필요 |
| API 실패 | 0건 (0%) | 6건 (12.5%) | Qwen 단독 운영 시 fallback 필요 |
| 파싱 실패 | 0% | 0% | 두 모델 모두 relaxed 파싱 가능 |
| 입력 토큰 | 20,498 | 18,530 | 입력 규모는 유사 |
| 출력 토큰 | 345 | 60,530 | Qwen은 출력 제어 필요 |

### 해석

- 종합 점수는 Qwen3.5-9B가 높지만, Efficiency와 Capability 축에서는 Llama 3가 우세하다.
- 이 결과는 "종합 1위 모델을 모든 요청에 사용"하는 전략보다, 요청 경로별 모델 배치가 더 적합함을 보여준다.

### Accuracy vs p95 Latency 포지셔닝

```text
정확도 ↑

100% |                                      ● Qwen3.5-9B
 90% |                                        정확도 92.9%
 80% |                                        p95 120.0s
 70% |
 60% |
 50% |
 40% |
 30% | ● Llama 3
 20% |   정확도 33.3%
 10% |   p95 1.44s
  0% +----------------------------------------------------→ p95 지연
      0s          20s          40s          80s        120s
```

**아키텍처 해석:** Llama 3는 Fast/Fallback Path, Qwen3.5-9B는 Accurate/Escalation Path에 배치하는 것이 자연스럽다.

---

## 5. 가설 검증 결과

| 가설 | 근거 결과 | 판정 |
|---|---|---|
| **H1 SLA 적합성** | Qwen은 정확도 92.9%로 높지만 p95 지연 120.0초. Llama는 정확도 33.3%지만 p95 1.44초 | 지지 |
| **H2 Tail Risk** | Qwen은 평균 64.1초, p50 61.3초, p95 120.0초로 tail latency가 큼 | 지지 |
| **H3 Failure-Aware Routing** | Qwen은 48문항 중 6건 실패(12.5%), Llama는 0건 실패 | 지지 |
| **H4 Token Control** | Qwen 출력 토큰 60,530개, Llama 345개. Qwen이 약 175배 많이 생성 | 지지 |
| **H5 Cascading Efficiency** | Llama는 저지연·무실패, Qwen은 고정확도. 경로별 역할 분담 근거가 명확함 | 지지 |
| **H6 Observability** | JSONL에 문항별 응답, 지연, 오류, 토큰이 남아 지연·실패 원인 분석 가능 | 지지 |

### H2 Tail Risk: 지연 차트

```text
Latency 비교

Llama 3
평균 0.79s   [█░░░░░░░░░░░░░░░░░░░]
p50  0.64s   [█░░░░░░░░░░░░░░░░░░░]
p95  1.44s   [█░░░░░░░░░░░░░░░░░░░]

Qwen3.5-9B
평균 64.1s   [███████████░░░░░░░░░]
p50  61.3s   [██████████░░░░░░░░░░]
p95 120.0s   [████████████████████]
```

**해석:** 실시간 서비스에서는 평균 지연뿐 아니라 p95 지연이 중요하다. Qwen3.5-9B는 고정확도 모델이지만 timeout guard 없이 기본 응답 경로에 배치하기 어렵다.

### H3 Failure-Aware Routing: 실패율 차트

```text
48문항 기준 API 결과

Llama 3
정상 [████████████████████████] 48
실패 [░░░░░░░░░░░░░░░░░░░░░░░░]  0

Qwen3.5-9B
정상 [█████████████████████░░░] 42
실패 [███░░░░░░░░░░░░░░░░░░░░░]  6
```

**해석:** Qwen3.5-9B는 성공한 문항 기준 정확도가 높지만, 서비스 운영에서는 실패 6건도 사용자 경험과 SLA에 포함된다. 따라서 fallback 경로가 필요하다.

### H4 Token Control: 출력 토큰 차트

```text
총 출력 토큰 수

Llama 3       [█░░░░░░░░░░░░░░░░░░░]    345
Qwen3.5-9B    [████████████████████] 60,530

Qwen3.5-9B는 Llama 3 대비 약 175배 많은 출력 토큰을 생성
```

**해석:** Qwen3.5-9B의 지연은 모델 크기뿐 아니라 긴 출력 생성과도 연결될 수 있다. 실제 서비스에서는 `max_tokens`, 구조화 출력, stop condition이 필요하다.

### 주의

- 본 검증은 **개별 모델 평가 결과로 Hybrid Routing 필요성을 도출한 것**이다.
- 실제 router를 구현해 end-to-end 응답 품질, 평균 지연, fallback 발생률을 측정한 실험은 후속 과제다.

---

## 6. SLA-aware Hybrid Routing 제안

### 모델 역할 정의

| 경로 | 우선 모델 | 사용 조건 | 운영 정책 |
|---|---|---|---|
| **Fast Path** | Llama 3 | 간단 질의, 실시간 UX, 낮은 위험도 요청 | p95 1.44초 기반 기본 응답 경로 |
| **Accurate Path** | Qwen3.5-9B | 고난도 지식 질의, 정확도 우선 요청 | 비동기 또는 장시간 허용 경로 |
| **Fallback Path** | Llama 3 | Qwen timeout, API 실패, 장시간 지연 | 실패 감지 후 대체 응답 |
| **Escalation Path** | Qwen3.5-9B | Llama 응답 신뢰도 낮음, 고위험·고정확도 요청 | 선택 호출 또는 2차 검증 |
| **Observability Layer** | 공통 | 모든 요청 | 모델 선택, 지연, 실패, 토큰, fallback 여부 기록 |

### 라우팅 정책 예시

```text
사용자 요청
  -> 요청 분류: 난이도 / SLA / 위험도 / 지연 허용 시간
  -> 실시간·낮은 위험도: Llama 3
  -> 고난도·정확도 우선: Qwen3.5-9B
  -> Qwen timeout 또는 실패: Llama 3 fallback
  -> Llama 응답 불충분: Qwen escalation
  -> 모든 결과 로그 저장
```

### Hybrid Routing Architecture

```text
                         사용자 요청
                              │
                              ▼
                    Request Classifier
            난이도 / SLA / 위험도 / 도메인 판단
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
  실시간·저위험 요청     고난도·정확도 우선     실패·타임아웃 발생
        │                     │                     │
        ▼                     ▼                     ▼
     Llama 3             Qwen3.5-9B              Llama 3
    Fast Path           Accurate Path          Fallback Path
        │                     │
        │                     ▼
        │              Qwen 지연/실패 감지
        │                     │
        └───────────────Fallback───────────────┘

Llama 응답 신뢰도 낮음 / 고위험 요청
        └──────────────▶ Qwen3.5-9B Escalation Path

모든 경로 공통:
selected_model / latency / failure / tokens / fallback 여부 로그 저장
```

### 서비스 설계 시 유의점

- Qwen3.5-9B 호출에는 timeout guard가 필요하다.
- Qwen3.5-9B는 출력 토큰이 매우 크므로 `max_tokens`, 구조화 출력, stop condition을 적용해야 한다.
- Llama 3는 빠르고 안정적이지만 고난도 지식 요청에는 escalation 조건을 둬야 한다.
- 라우터는 모델 선택 결과뿐 아니라 실패·재시도·fallback 여부를 로그로 남겨야 한다.

---

## 7. 정확도: 전체 · 카테고리

| 구분 | Llama 3 | Qwen3.5-9B | 해석 |
|------|--------:|------------:|---|
| **전체 정확도** | 33.3% | 92.9% | Qwen 고정확도 경로 근거 |
| **Humanities** | 58.3% | 100% | Qwen 우세 |
| **STEM** | 25.0% | 90.9% | 고난도 지식 요청 escalation 근거 |
| **Social Sciences** | 25.0% | 90.9% | Qwen 우세 |
| **Other** | 25.0% | 88.9% | Qwen 우세 |
| **과목별 편차(σ)** | 0.47 | 0.26 | Qwen이 더 고른 편 |

### 카테고리별 정확도 차트

```text
카테고리별 정확도

Humanities
Llama 3      [████████████░░░░░░░░] 58.3%
Qwen3.5-9B   [████████████████████] 100.0%

STEM
Llama 3      [█████░░░░░░░░░░░░░░░] 25.0%
Qwen3.5-9B   [██████████████████░░] 90.9%

Social Sciences
Llama 3      [█████░░░░░░░░░░░░░░░] 25.0%
Qwen3.5-9B   [██████████████████░░] 90.9%

Other
Llama 3      [█████░░░░░░░░░░░░░░░] 25.0%
Qwen3.5-9B   [██████████████████░░] 88.9%
```

### 도메인 라우팅 해석

- 현재 표본에서는 Qwen3.5-9B가 모든 상위 카테고리에서 우세하다.
- Llama 3는 Humanities를 제외한 영역에서 25.0% 수준이므로, 도메인 지식이 중요한 요청은 Qwen escalation 기준을 두는 편이 적합하다.
- 단, Qwen의 실패율과 지연을 고려해 실시간 기본 경로가 아니라 정확도 우선 경로로 배치한다.

---

## 8. 한계와 후속 검증

| 한계 | 설명 |
|------|------|
| **표본** | N=48. 전수 MMLU 순위나 공개 벤치 단일 수치와 직접 비교하지 않는다. |
| **환경** | 단일 PC·Ollama 설정. 다른 GPU·컨텍스트·Ollama 버전에서는 지연과 실패율이 달라질 수 있다. |
| **27B** | `qwen3.5:27b`는 완주 결과가 아니므로 본 비교에서 제외했다. |
| **정확도 정의** | 본 산출물의 정확도는 relaxed 파싱 기준이다. strict 단일 문자 준수율은 별도 집계 시 보강한다. |
| **라우터 검증** | 현재는 개별 모델 평가 결과다. 실제 Hybrid Router의 end-to-end 개선율은 후속 실험이 필요하다. |

### 후속 실험

- Llama 3 1차 처리 후 confidence가 낮은 요청만 Qwen3.5-9B로 escalation하는 실험
- Qwen3.5-9B에 `max_tokens`와 구조화 출력 지시를 적용해 지연·출력 토큰 감소 여부 확인
- timeout 기준별 fallback 발생률과 사용자 체감 지연 측정
- MMLU 외 실제 업무 질의셋으로 라우팅 정책 재검증
- strict compliance, 처리량, GPU/메모리 사용량 추가 측정

---

## 9. PPT 슬라이드 구성 제안

| # | 제목 | 핵심 내용 |
|---|---|---|
| 1 | 연구 개요 | 모델 비교가 아니라 SLA-aware Hybrid LLM Architecture 설계 |
| 2 | 연구 질문·가설 | SLA, tail latency, failure-aware routing, token control |
| 3 | 평가 로직 | MMLU 입력부터 Score Card와 로그 기록까지 |
| 4 | 핵심 결과 대시보드 | Score Card 막대, 원 지표, Accuracy vs p95 포지셔닝 |
| 5 | 가설 검증 | H1~H6 검증 결과, 지연·실패·토큰 차트 |
| 6 | Hybrid Routing 제안 | Fast/Accurate/Fallback/Escalation Path 다이어그램 |
| 7 | 한계·확장 | 실제 router 검증, strict, token control, 업무셋 확장 |

---

*본 문서는 legacy `outputs_ollama_3`·`outputs_qwen3_5`의 `*_metrics.json`·`*_report.md` 및 `*.jsonl` 로그를 바탕으로 작성되었으며, 원본 과거 산출물 폴더는 web 중심 정리 과정에서 제거되었습니다.*
