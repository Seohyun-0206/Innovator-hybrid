from typing import Optional

import requests
from django.conf import settings

from apps.catalog.credentials import get_openrouter_access_token, get_openrouter_base_url
from apps.providers.base import BaseLLMProvider, LLMResponse


class OpenRouterProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key if api_key is not None else get_openrouter_access_token()
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured.")
        if base_url is not None:
            resolved_base_url = base_url
        elif api_key is not None:
            resolved_base_url = settings.OPENROUTER_BASE_URL
        else:
            resolved_base_url = get_openrouter_base_url()
        self.base_url = resolved_base_url.rstrip("/")

    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        payload = {
            "model": model,
            "messages": messages,
        }
        payload.update(options or {})

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json()
        return LLMResponse(text=self._extract_text(raw), raw=raw)

    def _extract_text(self, payload: dict) -> str:
        chunks = []
        for choice in payload.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                chunks.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("text"):
                        chunks.append(item["text"])
        return "".join(chunks)
