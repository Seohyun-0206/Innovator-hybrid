from apps.catalog.evaluation import PilotEvaluationRunner
from apps.catalog.model_metrics import (
    extract_answer,
    is_generation_correct,
    is_strict_answer,
    strip_thinking_output,
)


def test_strip_thinking_output_removes_closed_think_block():
    text = "<think>이 문제는 B가 맞아 보인다</think>정답: B"
    assert strip_thinking_output(text) == "정답: B"


def test_strip_thinking_output_returns_empty_when_think_block_never_closes():
    # max_tokens가 작아서 <think> 추론 도중 응답이 끊긴 경우 — 실제 답은 아직 안 나온 것이므로
    # 추론 텍스트 속 글자를 답으로 오인하면 안 됩니다.
    text = "<think>이 문제는 아마도 B나 C 중 하나일 것 같은데 좀 더 생각해보면"
    assert strip_thinking_output(text) == ""


def test_strip_thinking_output_passthrough_when_no_think_tag():
    assert strip_thinking_output("정답: A") == "정답: A"


def test_extract_answer_ignores_letters_inside_think_block():
    # <think> 안에서 다른 답(B, D)을 언급하다가 최종적으로 C로 결론내는 경우,
    # think 블록 안의 B/D가 아니라 실제 답 C만 추출되어야 합니다.
    text = "<think>처음엔 B 같았는데 D일 수도 있겠다</think>정답: C"
    assert extract_answer(text) == "C"


def test_extract_answer_returns_empty_when_only_truncated_think_present():
    text = "<think>letter A로 시작하는 이유를 설명하자면 B는 아니고"
    assert extract_answer(text) == ""


def test_is_strict_answer_ignores_think_block():
    assert is_strict_answer("<think>추론중...</think>B") is True
    assert is_strict_answer("<think>추론중...</think>정답: B") is False


def test_is_generation_correct_ignores_think_block():
    assert is_generation_correct("<think>정답은 파리가 아니라</think>런던입니다", "런던") is True
    assert is_generation_correct("<think>런던일 수도 있음</think>사실은 파리입니다", "런던") is False


def test_parse_router_choice_treats_truncated_think_as_small_fallback():
    runner = PilotEvaluationRunner()
    # <think> 도중 잘려서 "large"라는 exact 텍스트가 실제로 나온 적 없음 -> small로 폴백
    assert runner.parse_router_choice("<think>large가 필요할 수도 있는데 확실하지 않다") == "small"


def test_parse_router_choice_uses_answer_after_closed_think_block():
    runner = PilotEvaluationRunner()
    assert runner.parse_router_choice("<think>이 문제는 복잡하니 large로 보내는게 낫겠다</think>large") == "large"
    assert runner.parse_router_choice("<think>이 정도는 small이 처리 가능하다</think>small") == "small"
