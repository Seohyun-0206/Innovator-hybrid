from typing import Optional

import requests
from django.conf import settings

from apps.catalog.credentials import get_openai_access_token, get_openai_base_url
from apps.providers.base import BaseLLMProvider, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key if api_key is not None else get_openai_access_token()
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        if base_url is not None:
            resolved_base_url = base_url
        elif api_key is not None:
            resolved_base_url = settings.OPENAI_BASE_URL
        else:
            resolved_base_url = get_openai_base_url()
        self.base_url = resolved_base_url.rstrip("/")

    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        payload = {
            "model": model,
            "input": messages,
        }
        payload.update(options or {})

        response = requests.post(
            f"{self.base_url}/responses",
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
        if payload.get("output_text"):
            return payload["output_text"]

        chunks = []
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(content["text"])
        return "".join(chunks)
