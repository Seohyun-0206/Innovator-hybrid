import pytest

from apps.providers.gemini import GeminiProvider
from apps.providers.openai import OpenAIProvider
from apps.providers.openrouter import OpenRouterProvider


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


def test_external_providers_require_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key="")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key="")
