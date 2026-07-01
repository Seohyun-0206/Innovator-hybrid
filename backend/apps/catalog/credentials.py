from typing import Optional

from django.conf import settings

from apps.catalog.models import ProviderCredential


def get_provider_credential(provider: str) -> Optional[ProviderCredential]:
    return ProviderCredential.objects.filter(provider=provider, is_active=True).first()


def get_provider_base_url(provider: str, fallback: str) -> str:
    credential = get_provider_credential(provider)
    if credential and credential.get_base_url():
        return credential.get_base_url()
    return fallback


def get_provider_access_token(provider: str, fallback: str) -> str:
    credential = get_provider_credential(provider)
    if credential and credential.get_access_token():
        return credential.get_access_token()
    return fallback


def get_openai_base_url() -> str:
    return get_provider_base_url("openai", settings.OPENAI_BASE_URL)


def get_openai_access_token() -> str:
    return get_provider_access_token("openai", settings.OPENAI_API_KEY)


def get_gemini_base_url() -> str:
    return get_provider_base_url("gemini", settings.GEMINI_BASE_URL)


def get_gemini_access_token() -> str:
    return get_provider_access_token("gemini", settings.GEMINI_API_KEY)


def get_openrouter_base_url() -> str:
    return get_provider_base_url("openrouter", settings.OPENROUTER_BASE_URL)


def get_openrouter_access_token() -> str:
    return get_provider_access_token("openrouter", settings.OPENROUTER_API_KEY)
