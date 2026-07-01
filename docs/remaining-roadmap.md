# LLM Policy Gateway Remaining Roadmap

이 문서는 현재까지 구현된 Hybrid LLM Routing Policy 서비스에서 다음 단계로 개발할 항목을 정리한다.

## 현재 구현된 주요 기능

- Django + DRF 기반 백엔드 API
- Vue 3 Composition API + Tailwind 기반 관리자 대시보드
- Ollama, OpenAI, Gemini, OpenRouter provider 연동 구조
- Provider Credential 저장/수정/삭제/조회 및 양방향 암호화 저장
- 모델, 정책, 사용자, 화면 권한 관리
- 사용자 로그인 및 화면 접근 제어
- 관리형 사용자 세션 및 동시 접속 제어
- 화면 접근 권한과 쓰기/실행 권한 분리
- Bcrypt 기반 비밀번호 저장
- 라우팅 시뮬레이터
- Playground 기반 라우팅 테스트
- Routing Logs 및 상세 팝업
- 테이블 페이징
- Routing Logs 폰트 크기 옵션
- 탭 기반 화면 유지
- 사용자별 Allowed Screens 동적 관리
- 외부 LLM 모델별 Credential 지정
- 비용/요청량 기반 Usage Quota
- Dashboard 기간 필터
- Provider/Model health 지표
- Health Rules 기반 unhealthy 모델 자동 제외
- Model Tier 관리
- Routing Rules 관리 및 Tier 기반 라우팅
- Threshold Rules 관리 및 estimated token 기반 Tier 우선 라우팅
- Response Validation Rules 관리 및 JSON/SQL/non-empty 검증
- Recovery Strategies 관리 및 Validation Rule 연동
- 현재 비정상 모델 현황 표시
- Health 이벤트 이력 저장 및 조회

## 완료됨: Model Tier 및 Routing Rules

### 구현 내용

- 모델별 Tier 필드 추가:
  - Lightweight
  - Standard
  - Advanced
  - Long Context
  - Structured
- Models 화면에서 Tier 조회/수정 지원
- Routing Rules 화면 추가
- PDF 기준 기본 rule seed:
  - R-01 Simple FAQ fast path
  - R-04 Sensitive accuracy guard
  - R-05 Reasoning escalation path
  - R-06 Long context path
  - R-07 Structured output path
- 프롬프트 분석 결과와 Routing Rule 조건이 매칭되면 target tier 모델을 우선 선택
- Chat/Simulator 응답에 matched rules 포함

## 완료됨: Threshold Rules

### 구현 내용

- Threshold Rules 화면 추가
- Threshold Rule CRUD API 추가
- 지원 metric:
  - estimated tokens
  - p95 latency ms
  - timeout seconds
  - parse fail rate
  - failure rate
- 지원 action:
  - prefer model tier
  - set max tokens
- 기본 threshold seed:
  - T-08 Token control path
- 현재 라우팅 적용 범위:
  - `estimated_tokens` 조건이 매칭되면 target tier 모델을 우선 선택
  - threshold rule은 일반 Routing Rule보다 우선 적용
- Chat/Simulator 응답에 matched threshold rules 포함

## 완료됨: Response Validation Rules

### 구현 내용

- Validation Rules 화면 추가
- Response Validation Rule CRUD API 추가
- 지원 validation:
  - JSON parse validation
  - SQL format validation
  - non-empty response validation
- 지원 recovery action:
  - strict retry
  - fallback
  - escalate to tier
  - block response
- 기본 validation seed:
  - V-07 Structured JSON validation
- 현재 라우팅 적용 범위:
  - 매칭된 validation rule이 있으면 provider 응답 이후 검증 수행
  - JSON 검증 실패 시 strict retry 수행
  - retry 성공/실패 내역을 routing reason에 기록
  - validation status와 validation errors를 Routing Log에 저장
- Chat/Simulator 응답에 matched validation rules 포함

## 완료됨: Recovery Strategies

### 구현 내용

- Recovery Strategies 화면 추가
- Recovery Strategy CRUD API 추가
- 지원 trigger:
  - validation failure
  - timeout
  - API failure
  - parse failure
  - low confidence
- 지원 action:
  - strict retry
  - fallback
  - escalate to tier
  - block response
- Response Validation Rule에서 Recovery Strategy 지정 가능
- 기본 strategy seed:
  - S-01 Strict retry then fallback
- 현재 라우팅 적용 범위:
  - Validation Rule에 strategy가 지정되어 있으면 기존 inline action보다 strategy를 우선 적용
  - strict retry의 retry prompt/max retries를 strategy에서 제어
  - escalation/fallback/block 액션을 strategy 단위로 관리 가능

## 완료됨: 현재 차단/비정상 모델 현황

### 구현 내용

- Health Rule 평가 로직을 공통 유틸로 분리
- Models API에 health status/reason/metrics 포함
- Models 화면에 Health 컬럼 추가
- Dashboard API에 현재 unhealthy models 포함
- Dashboard에 Currently Unhealthy Models 패널 추가
- 표시 정보:
  - provider/model
  - 적용된 health rule
  - 실패율
  - 요청 수
  - 실패 수
  - 평균 latency
  - 차단 사유
- Chat 라우팅과 Dashboard/Models 화면이 동일한 health rule 평가 결과 사용

## 1. 현재 차단/비정상 모델 현황

### 목적

Health Rules가 발동했을 때 어떤 provider/model이 현재 라우팅에서 제외되고 있는지 운영자가 바로 확인할 수 있어야 한다.

### 개발 내용

- Dashboard에 현재 unhealthy 모델 목록 추가
- Models 화면에 health status 배지 추가
- Health Rules별 최근 발동 상태 표시
- 모델별 최근 실패율, 평균 latency, 샘플 수 표시
- 제외 사유와 적용된 rule 이름 표시

### 우선순위

높음

### 기대 효과

운영자가 라우팅 실패 원인을 Routing Logs를 뒤지지 않고도 빠르게 파악할 수 있다.

## 완료됨: Health 이벤트 이력

### 구현 내용

- `ModelHealthEvent` 모델 추가
- Health 상태가 healthy/unhealthy로 전환될 때만 이벤트 저장
- 중복 dashboard 조회로 같은 이벤트가 반복 생성되지 않도록 방지
- Health Events API 및 화면 추가
- Dashboard 최근 health events 카드 추가

### 남은 확장 포인트

- 이벤트별 상세 팝업
- rule별 발동 횟수 집계
- 알림 채널 연동

## 완료됨: 수동 복구 / 일시 무시

### 구현 내용

- `ModelHealthOverride` 모델 추가
- override 유형:
  - `force_healthy`
  - `force_unhealthy`
- provider/model 범위 지정 지원
- 만료 시간 기반 자동 비활성 처리
- 라우팅 health 평가에서 override를 Health Rule보다 우선 적용
- Health Overrides API 및 화면 추가
- 생성자, 사유, 활성 상태, 만료 시간 조회/수정/삭제 지원

### 남은 확장 포인트

- override 변경 이력 전용 audit log
- Models 화면에서 바로 override 생성
- 만료 임박 override 알림

## 4. 라우팅 결과 품질 평가

### 목적

성공/실패와 비용뿐 아니라 실제 응답 품질을 라우팅 정책에 반영할 수 있게 한다.

### 개발 내용

- Playground 응답에 thumbs up/down 또는 점수 입력 추가
- `RoutingFeedback` 모델 추가
- 로그 상세 팝업에서 feedback 표시
- 모델별 평균 feedback score 집계
- 정책 엔진에서 품질 점수를 optional weight로 반영

### 우선순위

중간

### 기대 효과

단순 비용/latency 최적화를 넘어 실제 사용자 만족도를 반영한 라우팅이 가능해진다.

## 완료됨: 비용/크레딧 고도화

### 구현 내용

- Usage Quota API에 이번 달 사용량 필드 추가
  - 요청 수
  - 비용 합계
  - 요청 한도 소진율
  - 비용 한도 소진율
  - 초과 여부
- quota scope 기준 집계 지원
  - 전체 사용자 / 특정 사용자
  - 전체 provider / 특정 provider
- Chat quota 검사와 Usage Quota 조회가 같은 월 기준 helper를 사용하도록 정리
- Usage Quotas 화면에 월간 사용량 progress bar 추가
- 초과된 quota는 `exceeded` 상태로 표시

### 남은 확장 포인트

- quota 임박 경고
- quota 초과 전 알림 상태 추가
- 비용 집계 정확도 개선:
  - 실제 input/output token 사용량 저장
  - provider 응답의 usage metadata 파싱

예상 비용 기반이 아니라 실제 월간 사용량 기반으로 크레딧과 예산을 관리할 수 있다.

## 완료됨: Provider별 모델 자동 동기화

### 구현 내용

- Credential 기준 `/models` 호출
- provider별 응답 parser 구현
  - OpenAI/OpenRouter `data`
  - Gemini `models`
- Provider Credentials 화면에서 모델 동기화 모달 추가
- 기존 모델과 신규 모델 비교
- 신규 모델 선택 import
- import 시 provider credential 자동 연결
- 중복 모델은 skipped 처리

### 남은 확장 포인트

- 기존 모델 bulk update
- OpenRouter 모델별 가격 정보 연동
- provider별 context/가격 metadata 정규화

### 기대 효과

외부 provider 모델 변경에 빠르게 대응하고 모델 등록 실수를 줄일 수 있다.

## 7. 알림

### 목적

운영자가 화면을 보고 있지 않아도 quota 초과, provider 장애, health rule 발동을 알 수 있게 한다.

### 개발 내용

- Webhook 설정 모델 추가
- Slack 또는 generic webhook 전송
- 알림 대상 이벤트:
  - Health Rule 발동
  - quota 초과
  - provider credential test 실패
  - 특정 failure rate 이상
- 알림 재시도 및 중복 억제

### 우선순위

중간

### 기대 효과

서비스 장애나 비용 초과를 더 빠르게 감지할 수 있다.

## 진행 중: API 보안/운영 보강

### 구현 내용

- `SecurityPolicy` 모델 추가
- `UserSession` 모델 추가
- 로그인 시 관리형 세션 토큰 발급
- 세션별 IP/User-Agent/login/last seen/expires/status 저장
- idle timeout, absolute timeout 설정 지원
- 사용자/staff 최대 동시 세션 수 설정 지원
- 동시 접속 초과 시 기존 세션 종료 또는 새 로그인 차단 설정 지원
- 로그아웃/관리자 강제 종료 시 세션 상태 변경
- 권한 변경 시 기존 세션 revoke 옵션 적용
- `Security Settings` 화면 추가
- `User Sessions` 화면 추가
- 일반 사용자는 allowed screen의 조회 API만 접근 가능
- Playground/Simulator 같은 실행성 API는 해당 화면 권한이 있으면 POST 허용
- 설정 변경 API는 staff 전용으로 제한
- Provider Credential 응답에서 access token 원문 비노출
- 새 token 입력 시에만 credential token rotation 수행
- credential 마지막 사용 시각 저장
- credential token rotation 시각 저장
- `AuditLog` 모델 추가
- `Audit Logs` 화면 추가
- audit log 기록:
  - credential 생성/수정/삭제/token rotation
  - provider model import / preview 실패
  - user 권한 변경
  - security policy 변경
  - session revoke
  - model/policy/quota/routing rule/threshold rule/validation rule/recovery strategy/health rule/health override 변경
- DRF 기본 rate limit 설정 추가
  - anonymous 요청 제한
  - authenticated user 요청 제한

### 남은 확장 포인트

- CSRF/CORS 운영 설정 점검
- production secret 분리 가이드

### 기대 효과

외부 API token과 관리자 권한 변경을 더 안전하게 추적하고 보호할 수 있다.

## 추천 개발 순서

1. 알림
2. API 보안/운영 보강 잔여 항목
3. 라우팅 결과 품질 평가

## 다음 작업 추천

다음 구현은 `알림`을 추천한다. Health Event, quota exceeded, provider model sync 실패 같은 운영 이벤트가 이미 쌓이고 있으므로 Slack 또는 generic webhook 전송을 붙이면 장애 대응성이 좋아진다.
