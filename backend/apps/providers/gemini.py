from typing import Optional

import requests
from django.conf import settings

from apps.catalog.credentials import get_gemini_access_token, get_gemini_base_url
from apps.providers.base import BaseLLMProvider, LLMResponse


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key if api_key is not None else get_gemini_access_token()
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        if base_url is not None:
            resolved_base_url = base_url
        elif api_key is not None:
            resolved_base_url = settings.GEMINI_BASE_URL
        else:
            resolved_base_url = get_gemini_base_url()
        self.base_url = resolved_base_url.rstrip("/")

    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        payload = {
            "contents": self._to_contents(messages),
        }
        if options:
            payload["generationConfig"] = options

        response = requests.post(
            f"{self.base_url}/models/{model}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json()
        return LLMResponse(text=self._extract_text(raw), raw=raw)

    def _to_contents(self, messages: list[dict]) -> list[dict]:
        contents = []
        for message in messages:
            role = "model" if message.get("role") == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": message.get("content", "")}],
                }
            )
        return contents

    def _extract_text(self, payload: dict) -> str:
        chunks = []
        for candidate in payload.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                if part.get("text"):
                    chunks.append(part["text"])
        return "".join(chunks)
