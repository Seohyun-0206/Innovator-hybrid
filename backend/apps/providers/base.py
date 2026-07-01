from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: dict


class BaseLLMProvider:
    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        raise NotImplementedError
