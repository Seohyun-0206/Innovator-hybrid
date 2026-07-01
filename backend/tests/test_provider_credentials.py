import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.catalog.crypto import decrypt_value, encrypt_value
from apps.catalog.credentials import get_provider_access_token, get_provider_base_url
from apps.catalog.models import LLMModel, ProviderCredential
from apps.catalog.serializers import LLMModelSerializer, ProviderCredentialSerializer
from apps.providers.registry import ProviderRegistry
from apps.accounts.models import AuditLog


@pytest.mark.django_db
def test_provider_credential_encrypts_url_and_token_in_database():
    credential = ProviderCredential.objects.create(
        provider="openai",
        display_name="OpenAI Production",
    )
    credential.set_base_url("https://api.openai.com/v1")
    credential.set_access_token("sk-test-token")
    credential.save()

    stored = ProviderCredential.objects.get(id=credential.id)

    assert stored.encrypted_base_url != "https://api.openai.com/v1"
    assert stored.encrypted_access_token != "sk-test-token"
    assert stored.get_base_url() == "https://api.openai.com/v1"
    assert stored.get_access_token() == "sk-test-token"


def test_encrypt_value_round_trips_plaintext():
    encrypted = encrypt_value("secret")

    assert encrypted != "secret"
    assert decrypt_value(encrypted) == "secret"


@pytest.mark.django_db
def test_provider_credential_lookup_prefers_active_database_value():
    credential = ProviderCredential.objects.create(
        provider="openai",
        display_name="OpenAI Production",
        is_active=True,
    )
    credential.set_base_url("https://stored.example/v1")
    credential.set_access_token("stored-token")
    credential.save()

    assert get_provider_base_url("openai", "https://fallback.example/v1") == "https://stored.example/v1"
    assert get_provider_access_token("openai", "fallback-token") == "stored-token"


@pytest.mark.django_db
def test_provider_credential_serializer_reads_and_updates_decrypted_fields():
    credential = ProviderCredential.objects.create(
        provider="gemini",
        display_name="Gemini Dev",
    )
    credential.set_base_url("https://generativelanguage.googleapis.com/v1beta")
    credential.set_access_token("gemini-token")
    credential.save()

    assert ProviderCredentialSerializer(credential).data["base_url"] == (
        "https://generativelanguage.googleapis.com/v1beta"
    )
    assert ProviderCredentialSerializer(credential).data["access_token_masked"] == "gemi********oken"
    assert "access_token" not in ProviderCredentialSerializer(credential).data

    serializer = ProviderCredentialSerializer(
        credential,
        data={
            "provider": "gemini",
            "display_name": "Gemini Updated",
            "base_url": "https://example.test/gemini",
            "access_token": "new-token",
            "is_active": True,
        },
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    credential.refresh_from_db()

    assert credential.display_name == "Gemini Updated"
    assert credential.encrypted_base_url != "https://example.test/gemini"
    assert credential.encrypted_access_token != "new-token"
    assert credential.get_base_url() == "https://example.test/gemini"
    assert credential.get_access_token() == "new-token"
    assert credential.token_rotated_at is not None


@pytest.mark.django_db
def test_multiple_credentials_can_exist_for_same_provider():
    first = ProviderCredential.objects.create(provider="openrouter", display_name="OpenRouter Dev")
    first.set_base_url("https://dev.example/v1")
    first.set_access_token("dev-token")
    first.save()

    second = ProviderCredential.objects.create(provider="openrouter", display_name="OpenRouter Prod")
    second.set_base_url("https://prod.example/v1")
    second.set_access_token("prod-token")
    second.save()

    assert ProviderCredential.objects.filter(provider="openrouter").count() == 2
    assert {first.get_access_token(), second.get_access_token()} == {"dev-token", "prod-token"}


@pytest.mark.django_db
def test_model_serializer_accepts_matching_provider_credential():
    credential = ProviderCredential.objects.create(provider="openrouter", display_name="OpenRouter Prod")
    credential.set_base_url("https://openrouter.ai/api/v1")
    credential.set_access_token("prod-token")
    credential.save()

    serializer = LLMModelSerializer(
        data={
            "provider": "openrouter",
            "name": "openai/gpt-4.1-nano",
            "display_name": "GPT via OpenRouter",
            "provider_credential": credential.id,
            "role": "general",
            "quality_level": 4,
            "speed_level": 4,
            "cost_level": 3,
            "privacy_level": "external",
            "context_window": 128000,
            "is_active": True,
        }
    )

    assert serializer.is_valid(), serializer.errors
    model = serializer.save()
    assert model.provider_credential == credential
    assert LLMModelSerializer(model).data["provider_credential_display_name"] == "OpenRouter Prod"


@pytest.mark.django_db
def test_model_serializer_rejects_mismatched_provider_credential():
    credential = ProviderCredential.objects.create(provider="openai", display_name="OpenAI Prod")
    credential.set_base_url("https://api.openai.com/v1")
    credential.set_access_token("openai-token")
    credential.save()

    serializer = LLMModelSerializer(
        data={
            "provider": "openrouter",
            "name": "openai/gpt-4.1-nano",
            "display_name": "GPT via OpenRouter",
            "provider_credential": credential.id,
            "role": "general",
            "quality_level": 4,
            "speed_level": 4,
            "cost_level": 3,
            "privacy_level": "external",
            "context_window": 128000,
            "is_active": True,
        }
    )

    assert not serializer.is_valid()
    assert "provider_credential" in serializer.errors


@pytest.mark.django_db
def test_provider_registry_uses_model_specific_credential():
    credential = ProviderCredential.objects.create(provider="openrouter", display_name="OpenRouter Prod")
    credential.set_base_url("https://prod.example/v1")
    credential.set_access_token("prod-token")
    credential.save()

    provider = ProviderRegistry().get("openrouter", credential=credential)

    assert provider.api_key == "prod-token"
    assert provider.base_url == "https://prod.example/v1"
    credential.refresh_from_db()
    assert credential.last_used_at is not None


@pytest.mark.django_db
def test_model_serializer_accepts_remote_ollama_credential_when_external():
    credential = ProviderCredential.objects.create(provider="ollama", display_name="RunPod Ollama")
    credential.set_base_url("https://runpod.example")
    credential.set_access_token("")
    credential.save()

    serializer = LLMModelSerializer(
        data={
            "provider": "ollama",
            "name": "llama3.1:8b",
            "display_name": "RunPod Llama 3.1",
            "provider_credential": credential.id,
            "role": "general",
            "quality_level": 3,
            "speed_level": 3,
            "cost_level": 1,
            "privacy_level": "external",
            "context_window": 8192,
            "is_active": True,
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.save().provider_credential == credential


@pytest.mark.django_db
def test_model_serializer_rejects_remote_ollama_credential_marked_local():
    credential = ProviderCredential.objects.create(provider="ollama", display_name="RunPod Ollama")
    credential.set_base_url("https://runpod.example")
    credential.set_access_token("")
    credential.save()

    serializer = LLMModelSerializer(
        data={
            "provider": "ollama",
            "name": "llama3.1:8b",
            "display_name": "RunPod Llama 3.1",
            "provider_credential": credential.id,
            "role": "general",
            "quality_level": 3,
            "speed_level": 3,
            "cost_level": 1,
            "privacy_level": "local",
            "context_window": 8192,
            "is_active": True,
        }
    )

    assert not serializer.is_valid()
    assert "privacy_level" in serializer.errors


@pytest.mark.django_db
def test_provider_registry_uses_remote_ollama_credential():
    credential = ProviderCredential.objects.create(provider="ollama", display_name="RunPod Ollama")
    credential.set_base_url("https://runpod.example")
    credential.set_access_token("runpod-token")
    credential.save()

    provider = ProviderRegistry().get("ollama", credential=credential)

    assert provider.api_key == "runpod-token"
    assert provider.base_url == "https://runpod.example"
    credential.refresh_from_db()
    assert credential.last_used_at is not None


@pytest.mark.django_db
def test_staff_can_test_provider_credential(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"data": []}

    calls = []

    def fake_get(url, headers, timeout):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("apps.catalog.views.requests.get", fake_get)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/provider-credentials/test/",
        {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "access_token": "secret-token",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["ok"] is True
    assert calls[0]["url"] == "https://openrouter.ai/api/v1/models"
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert calls[0]["timeout"] == 15


@pytest.mark.django_db
def test_staff_can_test_ollama_provider_credential_without_token(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"models": []}

    calls = []

    def fake_get(url, headers, timeout):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("apps.catalog.views.requests.get", fake_get)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/provider-credentials/test/",
        {
            "provider": "ollama",
            "base_url": "https://runpod.example",
            "access_token": "",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["ok"] is True
    assert calls[0]["url"] == "https://runpod.example/api/tags"
    assert calls[0]["headers"] == {}
    assert calls[0]["timeout"] == 15


@pytest.mark.django_db
def test_staff_can_preview_provider_models(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    credential = ProviderCredential.objects.create(provider="openrouter", display_name="OpenRouter Prod", is_active=True)
    credential.set_base_url("https://openrouter.ai/api/v1")
    credential.set_access_token("secret-token")
    credential.save()
    LLMModel.objects.create(
        provider="openrouter",
        name="existing-model",
        display_name="Existing Model",
        model_tier="standard",
        role="general",
        quality_level=3,
        speed_level=3,
        cost_level=3,
        privacy_level="external",
        context_window=8192,
        is_active=True,
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "existing-model", "context_length": 8192},
                    {"id": "new-model", "context_length": 32768},
                ]
            }

    def fake_get(url, headers, timeout):
        assert url == "https://openrouter.ai/api/v1/models"
        assert headers["Authorization"] == "Bearer secret-token"
        assert timeout == 20
        return FakeResponse()

    monkeypatch.setattr("apps.catalog.provider_models.requests.get", fake_get)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get(f"/api/provider-credentials/{credential.id}/models/preview/")

    assert response.status_code == 200
    assert response.data["models"][0]["name"] == "existing-model"
    assert response.data["models"][0]["exists"] is True
    assert response.data["models"][1]["name"] == "new-model"
    assert response.data["models"][1]["exists"] is False
    assert response.data["models"][1]["context_window"] == 32768


@pytest.mark.django_db
def test_staff_can_preview_ollama_provider_models(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    credential = ProviderCredential.objects.create(provider="ollama", display_name="RunPod Ollama", is_active=True)
    credential.set_base_url("https://runpod.example")
    credential.set_access_token("runpod-token")
    credential.save()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "models": [
                    {"name": "llama3.1:8b"},
                    {"model": "qwen2.5-coder:7b"},
                ]
            }

    def fake_get(url, headers, timeout):
        assert url == "https://runpod.example/api/tags"
        assert headers["Authorization"] == "Bearer runpod-token"
        assert timeout == 20
        return FakeResponse()

    monkeypatch.setattr("apps.catalog.provider_models.requests.get", fake_get)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get(f"/api/provider-credentials/{credential.id}/models/preview/")

    assert response.status_code == 200
    assert response.data["models"][0]["name"] == "llama3.1:8b"
    assert response.data["models"][1]["name"] == "qwen2.5-coder:7b"


@pytest.mark.django_db
def test_staff_can_import_provider_models():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    credential = ProviderCredential.objects.create(provider="openai", display_name="OpenAI Prod", is_active=True)
    credential.set_base_url("https://api.openai.com/v1")
    credential.set_access_token("secret-token")
    credential.save()
    LLMModel.objects.create(
        provider="openai",
        name="existing-model",
        display_name="Existing Model",
        model_tier="standard",
        role="general",
        quality_level=3,
        speed_level=3,
        cost_level=3,
        privacy_level="external",
        context_window=8192,
        is_active=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        f"/api/provider-credentials/{credential.id}/models/import/",
        {"model_names": ["existing-model", "gpt-new"]},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["skipped"] == ["existing-model"]
    assert response.data["imported"][0]["name"] == "gpt-new"
    imported_model = LLMModel.objects.get(provider="openai", name="gpt-new")
    assert imported_model.provider_credential == credential
    assert imported_model.privacy_level == "external"
    assert AuditLog.objects.filter(action="provider_models.import", resource_id=str(credential.id)).exists()


@pytest.mark.django_db
def test_staff_credential_update_records_audit_and_does_not_expose_token():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    credential = ProviderCredential.objects.create(provider="openai", display_name="OpenAI Prod", is_active=True)
    credential.set_base_url("https://api.openai.com/v1")
    credential.set_access_token("old-token")
    credential.save()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.patch(
        f"/api/provider-credentials/{credential.id}/",
        {
            "display_name": "OpenAI Prod Rotated",
            "access_token": "new-token",
        },
        format="json",
    )

    credential.refresh_from_db()
    assert response.status_code == 200
    assert "access_token" not in response.data
    assert response.data["access_token_masked"] == "new-********oken"
    assert credential.get_access_token() == "new-token"
    assert credential.token_rotated_at is not None
    assert AuditLog.objects.filter(action="credential.rotate_token", resource_id=str(credential.id)).exists()
