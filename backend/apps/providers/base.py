from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: dict
    usage: Optional[dict] = None
    ttft_ms: Optional[int] = None


class BaseLLMProvider:
    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        raise NotImplementedError
