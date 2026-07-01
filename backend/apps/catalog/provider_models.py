import re

import requests

from apps.catalog.models import LLMModel


def fetch_provider_models(credential):
    credential.mark_used()
    provider = credential.provider
    base_url = credential.get_base_url().rstrip("/")
    access_token = credential.get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    if provider == "gemini":
        headers = {"x-goog-api-key": access_token}
    if provider == "ollama":
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        response = requests.get(f"{base_url}/api/tags", headers=headers, timeout=20)
        response.raise_for_status()
        return parse_provider_models(provider, response.json())

    response = requests.get(f"{base_url}/models", headers=headers, timeout=20)
    response.raise_for_status()
    return parse_provider_models(provider, response.json())


def parse_provider_models(provider, payload):
    raw_models = payload.get("data") if isinstance(payload, dict) else None
    if raw_models is None and isinstance(payload, dict):
        raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raw_models = []

    candidates = []
    for item in raw_models:
        model_name = extract_model_name(provider, item)
        if not model_name:
            continue
        candidates.append(
            {
                "name": model_name,
                "display_name": humanize_model_name(model_name),
                "context_window": extract_context_window(item),
                "exists": LLMModel.objects.filter(provider=provider, name=model_name).exists(),
            }
        )
    return candidates


def extract_model_name(provider, item):
    if not isinstance(item, dict):
        return ""
    name = item.get("id") or item.get("name") or item.get("model")
    if not name:
        return ""
    if provider == "gemini" and name.startswith("models/"):
        return name.removeprefix("models/")
    return name


def extract_context_window(item):
    if not isinstance(item, dict):
        return 8192
    for key in ("context_length", "context_window", "input_token_limit"):
        value = item.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 8192


def humanize_model_name(name):
    words = re.split(r"[-_/.:]+", name)
    return " ".join(word.upper() if word.isdigit() else word.capitalize() for word in words if word)
