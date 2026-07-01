import time
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

from apps.catalog.credentials import get_provider_access_token, get_provider_base_url
from apps.catalog.models import LLMModel
from apps.catalog.provider_models import parse_provider_models


def resolve_provider_connection(model: LLMModel) -> tuple[str, str]:
    credential = model.provider_credential
    if credential is not None:
        credential.mark_used()
        base_url = credential.get_base_url()
        access_token = credential.get_access_token()
        if not base_url:
            if model.provider == "openai":
                base_url = settings.OPENAI_BASE_URL
            elif model.provider == "gemini":
                base_url = settings.GEMINI_BASE_URL
            elif model.provider == "openrouter":
                base_url = settings.OPENROUTER_BASE_URL
        return base_url, access_token

    if model.provider == "ollama":
        return settings.OLLAMA_BASE_URL, ""
    if model.provider == "openai":
        return get_provider_base_url("openai", settings.OPENAI_BASE_URL), get_provider_access_token(
            "openai", settings.OPENAI_API_KEY
        )
    if model.provider == "gemini":
        return get_provider_base_url("gemini", settings.GEMINI_BASE_URL), get_provider_access_token(
            "gemini", settings.GEMINI_API_KEY
        )
    if model.provider == "openrouter":
        return get_provider_base_url("openrouter", settings.OPENROUTER_BASE_URL), get_provider_access_token(
            "openrouter", settings.OPENROUTER_API_KEY
        )
    raise ValueError(f"Unsupported provider: {model.provider}")


def request_provider_models(provider: str, base_url: str, access_token: str):
    base_url = base_url.rstrip("/")
    if provider == "ollama":
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        return requests.get(f"{base_url}/api/tags", headers=headers, timeout=5)
    if provider == "gemini":
        return requests.get(f"{base_url}/models", headers={"x-goog-api-key": access_token}, timeout=5)
    return requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {access_token}"}, timeout=5)


def fetch_provider_catalog(model: LLMModel) -> dict:
    start = time.monotonic()
    try:
        provider = model.provider
        base_url, access_token = resolve_provider_connection(model)
        response = request_provider_models(provider, base_url, access_token)
        latency_ms = int((time.monotonic() - start) * 1000)
        response.raise_for_status()
        candidates = parse_provider_models(provider, response.json())
        return {
            "ok": True,
            "model_names": {candidate["name"] for candidate in candidates},
            "latency_ms": latency_ms,
            "message": "provider catalog fetched",
            "base_url": base_url,
        }
    except Exception as exc:
        base_url = settings.OLLAMA_BASE_URL if model.provider == "ollama" else ""
        try:
            base_url, _ = resolve_provider_connection(model)
        except Exception:
            pass
        return {
            "ok": False,
            "model_names": set(),
            "latency_ms": int((time.monotonic() - start) * 1000),
            "message": str(exc),
            "base_url": base_url,
        }


def get_provider_cache_key(model: LLMModel) -> tuple[str, str]:
    credential_id = str(model.provider_credential_id or "default")
    return (model.provider, credential_id)


def check_model_connectivity(model: LLMModel, *, provider_cache: Optional[dict] = None) -> dict:
    checked_at = timezone.now()
    if not model.is_active:
        return build_connectivity_result(
            model=model,
            status_value="skipped",
            message="비활성 모델",
            checked_at=checked_at,
        )

    cache = provider_cache if provider_cache is not None else {}
    cache_key = get_provider_cache_key(model)
    if cache_key not in cache:
        cache[cache_key] = fetch_provider_catalog(model)
    catalog = cache[cache_key]

    if catalog["ok"]:
        if model.name in catalog["model_names"]:
            status_value = "online"
            message = "모델 사용 가능"
        else:
            status_value = "offline"
            message = "provider 카탈로그에 모델이 없습니다"
    else:
        status_value = "error"
        message = catalog["message"]

    return build_connectivity_result(
        model=model,
        status_value=status_value,
        message=message,
        checked_at=checked_at,
        latency_ms=catalog["latency_ms"],
    )


def check_models_connectivity(models: list[LLMModel]) -> list[dict]:
    provider_cache = {}
    return [check_model_connectivity(model, provider_cache=provider_cache) for model in models]


def validate_models_available(models: list[LLMModel]) -> tuple[bool, list[str]]:
    errors = []
    provider_cache = {}
    for model in models:
        if not model.is_active:
            errors.append(f"{model.provider}/{model.name}: 비활성 모델입니다.")
            continue
        result = check_model_connectivity(model, provider_cache=provider_cache)
        if result["status"] != "online":
            errors.append(f"{model.provider}/{model.name}: {result['message']}")
    return (len(errors) == 0, errors)


def check_ollama_status(base_url: Optional[str] = None) -> dict:
    resolved_base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    start = time.monotonic()
    try:
        response = requests.get(f"{resolved_base_url}/api/tags", timeout=5)
        latency_ms = int((time.monotonic() - start) * 1000)
        response.raise_for_status()
        payload = response.json()
        installed_models = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
        return {
            "reachable": True,
            "base_url": resolved_base_url,
            "latency_ms": latency_ms,
            "message": "Ollama 서버에 연결되었습니다.",
            "installed_models": installed_models,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "base_url": resolved_base_url,
            "latency_ms": int((time.monotonic() - start) * 1000),
            "message": str(exc),
            "installed_models": [],
        }


def build_connectivity_result(*, model, status_value, message, checked_at, latency_ms=None):
    return {
        "model_id": model.id,
        "provider": model.provider,
        "model": model.name,
        "display_name": model.display_name,
        "status": status_value,
        "latency_ms": latency_ms,
        "checked_at": checked_at.isoformat(),
        "message": message,
    }
