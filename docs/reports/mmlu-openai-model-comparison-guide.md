# MMLU OpenAI 모델 비교 리포트

실험 실행 후 자동 생성되는 최신 결과는 `outputs/reports/mmlu_model_comparison.md`를 확인하세요.

## 본 문서 목적
- 평가 항목 정의
- 결과 해석 프레임 제시
- 의사결정 시 체크포인트 제공

## 평가 항목
- 성능: Overall/Category/Subject 정확도
- 효율: Cost per 1K Questions, Latency p50/p95, Token Efficiency
- 기능/운영: 모달리티, 기능 지원 폭, 실패율

## 종합 점수
- 기본 가중치: `Performance 0.55`, `Efficiency 0.25`, `Capability 0.20`
- 민감도 분석: `+10%` 시나리오별 순위 변동 비교

## 해석 가이드
- 최고 점수 모델이 항상 최적은 아님
- 비용 제약이 크면 Efficiency 가중치를 높여 재평가
- 고난도 도메인 중심 서비스면 Category/Subject 하위 성능을 우선 검토
