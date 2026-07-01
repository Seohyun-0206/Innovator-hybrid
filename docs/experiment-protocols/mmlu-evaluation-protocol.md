# MMLU 평가 프로토콜

## 목적
- OpenAI/Ollama MMLU 비교 평가의 공통 조건과 web 앱에서 보존하는 평가 결과의 해석 기준을 정의한다.

## 데이터셋
- 출처: `https://github.com/hendrycks/test`
- 입력 파일:
  - `data/dev/{subject}_dev.csv` (few-shot 예시)
  - `data/test/{subject}_test.csv` (평가 문항)
- CSV 스키마: `question, A, B, C, D, label`

## 프롬프트 규칙
- few-shot: 과목별 `k=5` (기본값)
- system 지시: 반드시 `A/B/C/D` 중 하나만 출력
- 출력 형식: 공백/설명 없이 단일 문자 (`A|B|C|D`)

## API 파라미터
- 엔드포인트: OpenAI Responses API
- `temperature=0`
- `max_output_tokens=8` (실제 답은 1토큰 성격이나 안정성을 위해 여유)
- `reasoning.effort`: 기본 `minimal` (비교 시 동일값 유지)

## 채점 규칙
- 정규식으로 `A|B|C|D` 첫 매치 추출
- 추출 실패 시 오답 처리
- 정답 일치 여부를 `is_correct`로 기록

## 로깅/재현성
- 모델/과목 단위 JSONL 로그 저장
- 문항별 요청/응답/토큰/지연시간/오류를 모두 기록
- 동일 실험 식별자(run_id), 실행 시각, 모델명, 파라미터 고정 저장
- 연구계획서(카테고리 균형 표본)에 맞춰 `outputs/summary/eval_manifest.json`(또는 Ollama 출력 디렉터리)에 평가 과목·CLI 조건을 기록

## 평가 범위(과목 선택)
- 기본: `data/test`의 모든 과목
- `--categories`: 상위 카테고리(`STEM` 등)에 속한 과목만
- `--subjects-per-category N`: 카테고리당 최대 N개 과목(균형 표본; `--seed`로 재현)
- `--subjects`: 과목 slug를 명시(다른 subset 옵션과 배타)
- 기본: 상위 카테고리별로 가능한 한 균등하게 **총 100문항** (`--total-questions` 기본값). `N`으로 변경 가능.
- `--full-eval`: 예전 모드(전 과목 또는 `--max-questions-per-subject`). 이 경우 `--total-questions`는 무시.
- 과거 CLI 실행: `python -m openai_mmlu.run_eval` 또는 `python -m ollama_mmlu.run_eval`로 수행했다. 현재 저장소는 web 앱 중심으로 정리되어 해당 CLI 패키지는 제거되었으며, 보존 산출물 import는 `cd web/backend && python manage.py seed_demo`로 수행한다.

## 공정성 원칙
- 동일 데이터, 동일 프롬프트 템플릿, 동일 파라미터 사용
- 실패 재시도 정책(지수 백오프) 동일 적용
- 누락 정보(예: 파라미터 수 비공개)는 `N/A`로 명시하고 불이익 점수 미부여
