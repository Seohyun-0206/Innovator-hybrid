import json
import time
from typing import Optional

import requests
from django.conf import settings

from apps.catalog.credentials import get_vllm_access_token, get_vllm_base_url
from apps.providers.base import BaseLLMProvider, LLMResponse


class VLLMProvider(BaseLLMProvider):
    KV_CACHE_METRIC_NAMES = ("vllm:gpu_cache_usage_perc", "vllm:kv_cache_usage_perc")

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key if api_key is not None else get_vllm_access_token()
        if base_url is not None:
            resolved_base_url = base_url
        elif api_key is not None:
            resolved_base_url = settings.VLLM_BASE_URL
        else:
            resolved_base_url = get_vllm_base_url()
        self.base_url = resolved_base_url.rstrip("/")

    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        if model == "Qwen/Qwen3.5-122B-A10B":
            print(f"model: {model}-thinking")
            payload = {
                "model": model,
                "messages": messages,
                "chat_template_kwargs": {"enable_thinking": True},   
            }
        else:
            payload = {
                "model": model,
                "messages": messages,
                "chat_template_kwargs": {"enable_thinking": False},   
            }

        payload.update(options or {})

        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        started = time.perf_counter()
        ttft_ms = None
        usage = None
        last_event = None
        chunks = []

        with requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()
            # decode_unicode=True는 서버가 응답 헤더에 charset을 명시하지 않으면 requests가
            # ISO-8859-1로 잘못 추측해 한글 등 비ASCII 응답을 깨뜨립니다. SSE 페이로드는
            # 항상 UTF-8이므로 바이트로 받아 직접 디코딩합니다.
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8")
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break

                event = json.loads(data)
                last_event = event

                event_usage = event.get("usage")
                if event_usage:
                    usage = event_usage

                choices = event.get("choices") or []
                if not choices:
                    continue
                content = (choices[0].get("delta") or {}).get("content")
                if content:
                    if ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - started) * 1000)
                    chunks.append(content)

        return LLMResponse(
            text="".join(chunks),
            raw=last_event or {},
            usage=usage,
            ttft_ms=ttft_ms,
        )

    def fetch_kv_cache_usage(self) -> Optional[float]:
        """vLLM의 Prometheus `/metrics`에서 KV 캐시 사용률(0~1)을 읽어옵니다.

        요청 단위 지표가 아니라 서버의 현재 순간 상태이므로, 평가 루프 중
        주기적으로 폴링해 min/avg/max로 집계하는 용도로 씁니다."""
        metrics_url = f"{self._metrics_root()}/metrics"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = requests.get(metrics_url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return None
        return self._parse_kv_cache_usage(response.text)

    def _metrics_root(self) -> str:
        if self.base_url.endswith("/v1"):
            return self.base_url[: -len("/v1")]
        return self.base_url

    @classmethod
    def _parse_kv_cache_usage(cls, metrics_text: str) -> Optional[float]:
        for line in metrics_text.splitlines():
            if line.startswith("#"):
                continue
            if line.startswith(cls.KV_CACHE_METRIC_NAMES):
                try:
                    return float(line.rsplit(" ", 1)[-1])
                except ValueError:
                    return None
        return None
