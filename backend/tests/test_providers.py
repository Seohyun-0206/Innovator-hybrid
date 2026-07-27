import json

import pytest

from apps.providers.anthropic import AnthropicProvider
from apps.providers.gemini import GeminiProvider
from apps.providers.openai import OpenAIProvider
from apps.providers.openrouter import OpenRouterProvider
from apps.providers.vllm import VLLMProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_openai_provider_extracts_output_text(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse({"output_text": "hello from openai"})

    monkeypatch.setattr("apps.providers.openai.requests.post", fake_post)

    response = OpenAIProvider(api_key="test-key").chat(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "hello"}],
        options={"temperature": 0.2},
    )

    assert response.text == "hello from openai"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "gpt-4.1-mini"
    assert captured["json"]["input"] == [{"role": "user", "content": "hello"}]
    assert captured["json"]["temperature"] == 0.2


def test_gemini_provider_extracts_candidate_text(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "hello "},
                                {"text": "from gemini"},
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("apps.providers.gemini.requests.post", fake_post)

    response = GeminiProvider(api_key="test-key").chat(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "hello"}],
        options={"temperature": 0.1},
    )

    assert response.text == "hello from gemini"
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["json"]["contents"][0]["parts"] == [{"text": "hello"}]
    assert captured["json"]["generationConfig"]["temperature"] == 0.1


def test_openrouter_provider_extracts_chat_completion_text(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "hello from openrouter",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("apps.providers.openrouter.requests.post", fake_post)

    response = OpenRouterProvider(api_key="openrouter-token").chat(
        model="openai/gpt-4.1-mini",
        messages=[{"role": "user", "content": "hello"}],
        options={"temperature": 0.2},
    )

    assert response.text == "hello from openrouter"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer openrouter-token"
    assert captured["json"]["model"] == "openai/gpt-4.1-mini"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["json"]["temperature"] == 0.2


def test_anthropic_provider_extracts_message_text(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "content": [
                    {"type": "text", "text": "hello "},
                    {"type": "text", "text": "from anthropic"},
                ]
            }
        )

    monkeypatch.setattr("apps.providers.anthropic.requests.post", fake_post)

    response = AnthropicProvider(api_key="anthropic-token").chat(
        model="claude-haiku-4-5-20251001",
        messages=[{"role": "user", "content": "hello"}],
        options={"temperature": 0.2},
    )

    assert response.text == "hello from anthropic"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "anthropic-token"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["model"] == "claude-haiku-4-5-20251001"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["json"]["temperature"] == 0.2


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = lines

    def raise_for_status(self):
        return None

    def iter_lines(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _sse_lines(events):
    lines = [f"data: {json.dumps(event, ensure_ascii=False)}".encode("utf-8") for event in events]
    lines.append(b"data: [DONE]")
    return lines


def test_vllm_provider_streams_text_usage_and_ttft(monkeypatch):
    captured = {}
    events = [
        {"choices": [{"delta": {"content": "A"}}]},
        {"choices": [{"delta": {"content": "nswer: B"}}]},
        {
            "choices": [],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
        },
    ]

    def fake_post(url, *, headers, json, stream, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["stream"] = stream
        captured["timeout"] = timeout
        return FakeStreamResponse(_sse_lines(events))

    monkeypatch.setattr("apps.providers.vllm.requests.post", fake_post)

    response = VLLMProvider(api_key="vllm-token", base_url="https://runpod-host/v1").chat(
        model="Qwen/Qwen3-8B",
        messages=[{"role": "user", "content": "hello"}],
        options={"temperature": 0.2, "max_tokens": 8},
    )

    assert response.text == "Answer: B"
    assert response.usage == {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}
    assert response.ttft_ms is not None
    assert captured["url"] == "https://runpod-host/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer vllm-token"
    assert captured["json"]["model"] == "Qwen/Qwen3-8B"
    assert captured["json"]["stream"] is True
    assert captured["json"]["stream_options"] == {"include_usage": True}
    assert captured["json"]["temperature"] == 0.2
    assert captured["json"]["max_tokens"] == 8


def test_vllm_provider_decodes_non_ascii_content_as_utf8(monkeypatch):
    # 서버가 응답 헤더에 charset을 명시하지 않아도(예: text/event-stream만) SSE 페이로드는
    # 항상 UTF-8이므로 한글 등 비ASCII 응답이 깨지지 않아야 합니다.
    events = [
        {"choices": [{"delta": {"content": "정답"}}]},
        {"choices": [{"delta": {"content": ": B"}}]},
    ]

    def fake_post(url, *, headers, json, stream, timeout):
        return FakeStreamResponse(_sse_lines(events))

    monkeypatch.setattr("apps.providers.vllm.requests.post", fake_post)

    response = VLLMProvider(api_key="vllm-token", base_url="https://runpod-host/v1").chat(
        model="Qwen/Qwen3-8B",
        messages=[{"role": "user", "content": "hello"}],
        options={},
    )

    assert response.text == "정답: B"


def test_vllm_provider_does_not_require_api_key():
    provider = VLLMProvider(api_key="", base_url="https://runpod-host/v1")
    assert provider.api_key == ""


def test_vllm_provider_fetch_kv_cache_usage(monkeypatch):
    captured = {}

    class FakeMetricsResponse:
        text = (
            "# HELP vllm:gpu_cache_usage_perc GPU KV-cache usage.\n"
            "# TYPE vllm:gpu_cache_usage_perc gauge\n"
            'vllm:gpu_cache_usage_perc{model_name="Qwen/Qwen3-8B"} 0.42\n'
        )

        def raise_for_status(self):
            return None

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return FakeMetricsResponse()

    monkeypatch.setattr("apps.providers.vllm.requests.get", fake_get)

    provider = VLLMProvider(api_key="", base_url="https://runpod-host/v1")
    usage = provider.fetch_kv_cache_usage()

    assert usage == 0.42
    assert captured["url"] == "https://runpod-host/metrics"
    assert captured["headers"] == {}


def test_vllm_provider_fetch_kv_cache_usage_supports_v1_engine_metric_name(monkeypatch):
    class FakeMetricsResponse:
        text = (
            "# HELP vllm:kv_cache_usage_perc KV-cache usage.\n"
            "# TYPE vllm:kv_cache_usage_perc gauge\n"
            'vllm:kv_cache_usage_perc{model_name="Qwen/Qwen3-8B"} 0.57\n'
        )

        def raise_for_status(self):
            return None

    def fake_get(url, headers=None, timeout=None):
        return FakeMetricsResponse()

    monkeypatch.setattr("apps.providers.vllm.requests.get", fake_get)

    provider = VLLMProvider(api_key="", base_url="https://runpod-host/v1")
    usage = provider.fetch_kv_cache_usage()

    assert usage == 0.57


def test_vllm_provider_fetch_kv_cache_usage_sends_auth_header(monkeypatch):
    """RunPod처럼 인증이 필요한 vLLM 엔드포인트는 /metrics 요청에도 Authorization 헤더가 있어야 합니다."""
    captured = {}

    class FakeMetricsResponse:
        text = 'vllm:gpu_cache_usage_perc{model_name="Qwen/Qwen3-8B"} 0.42\n'

        def raise_for_status(self):
            return None

    def fake_get(url, headers=None, timeout=None):
        captured["headers"] = headers
        return FakeMetricsResponse()

    monkeypatch.setattr("apps.providers.vllm.requests.get", fake_get)

    provider = VLLMProvider(api_key="secret-token", base_url="https://runpod-host/v1")
    provider.fetch_kv_cache_usage()

    assert captured["headers"] == {"Authorization": "Bearer secret-token"}


def test_external_providers_require_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key="")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key="")

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key="")
