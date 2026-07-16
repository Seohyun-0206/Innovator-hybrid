from typing import Optional

import requests
from django.conf import settings

from apps.catalog.credentials import get_anthropic_access_token, get_anthropic_base_url
from apps.providers.base import BaseLLMProvider, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key if api_key is not None else get_anthropic_access_token()
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        if base_url is not None:
            resolved_base_url = base_url
        elif api_key is not None:
            resolved_base_url = settings.ANTHROPIC_BASE_URL
        else:
            resolved_base_url = get_anthropic_base_url()
        self.base_url = resolved_base_url.rstrip("/")

    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        payload = {
            "model": model,
            "max_tokens": 256,
            "messages": self._to_messages(messages),
        }
        payload.update(options or {})

        response = requests.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json()
        return LLMResponse(text=self._extract_text(raw), raw=raw)

    def _to_messages(self, messages: list[dict]) -> list[dict]:
        normalized = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            normalized.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": message.get("content", ""),
                }
            )
        return normalized

    def _extract_text(self, payload: dict) -> str:
        chunks = []
        for item in payload.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                chunks.append(item["text"])
        return "".join(chunks)
