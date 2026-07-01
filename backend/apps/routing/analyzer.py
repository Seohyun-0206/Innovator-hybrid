import re
from dataclasses import dataclass


SENSITIVE_PATTERNS = [
    # MVP 단계의 개인정보 신호입니다. 주민등록번호 형태, 이메일, 휴대폰 번호가
    # 감지되면 로컬/비공개 모델을 우선 사용하도록 라우팅합니다.
    re.compile(r"\b\d{6}-\d{7}\b"),
    re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
]

CODE_KEYWORDS = {
    "code",
    "python",
    "django",
    "vue",
    "java",
    "sql",
    "stacktrace",
    "exception",
    "에러",
    "코드",
}

STRUCTURED_OUTPUT_KEYWORDS = {
    "json",
    "sql",
    "schema",
    "structured",
    "구조화",
    "쿼리",
}

REASONING_KEYWORDS = {
    "분석",
    "비교",
    "추론",
    "설계",
    "리스크",
    "architecture",
    "analyze",
    "compare",
    "reason",
}


@dataclass(frozen=True)
class PromptAnalysis:
    has_sensitive_data: bool
    is_code: bool
    is_long_context: bool
    requires_reasoning: bool
    estimated_tokens: int
    is_structured_output: bool = False


class PromptAnalyzer:
    def analyze(self, prompt: str) -> PromptAnalysis:
        normalized = prompt.lower()
        # 라우팅 판단에는 가벼운 근사치면 충분합니다. 비용 계산 정확도가 중요해지면
        # provider별 tokenizer로 교체할 수 있습니다.
        estimated_tokens = max(1, len(prompt) // 4)
        return PromptAnalysis(
            has_sensitive_data=any(pattern.search(prompt) for pattern in SENSITIVE_PATTERNS),
            is_code=any(keyword in normalized for keyword in CODE_KEYWORDS),
            is_structured_output=any(keyword in normalized for keyword in STRUCTURED_OUTPUT_KEYWORDS),
            is_long_context=estimated_tokens > 3000,
            requires_reasoning=any(keyword in normalized for keyword in REASONING_KEYWORDS),
            estimated_tokens=estimated_tokens,
        )
