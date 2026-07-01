from decimal import Decimal
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.auth.hashers import identify_hasher
from django.conf import settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, SecurityPolicy, UserScreenAccess, UserSession
from apps.catalog.models import (
    LLMModel,
    ModelHealthEvent,
    ModelHealthOverride,
    ModelHealthRule,
    RecoveryStrategy,
    ResponseValidationRule,
    RoutingPolicy,
    RoutingRule,
    ThresholdRule,
    UsageQuota,
)
from apps.logs.models import RoutingLog
from apps.providers.base import LLMResponse
from apps.routing.views import ChatView


@pytest.mark.django_db
def test_login_returns_token_and_allowed_screens():
    user = User.objects.create_user(username="operator", password="pass12345")
    UserScreenAccess.objects.create(user=user, allowed_screens=["dashboard", "playground"])

    response = APIClient().post(
        "/api/auth/login/",
        {"username": "operator", "password": "pass12345"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["token"]
    assert response.data["user"]["username"] == "operator"
    assert response.data["user"]["allowed_screens"] == ["dashboard", "playground"]


@pytest.mark.django_db
def test_new_passwords_are_stored_with_bcrypt_sha256():
    user = User.objects.create_user(username="bcrypt-user", password="pass12345")

    assert user.password.startswith("bcrypt_sha256$")
    assert identify_hasher(user.password).algorithm == "bcrypt_sha256"
    assert user.check_password("pass12345")


@pytest.mark.django_db
def test_protected_api_requires_authentication():
    response = APIClient().get("/api/models/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_users_api_requires_staff_user():
    normal_user = User.objects.create_user(username="viewer", password="pass12345")
    Token.objects.create(user=normal_user)
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {normal_user.auth_token.key}")
    assert client.get("/api/users/").status_code == 403

    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/users/")
    assert response.status_code == 200
    assert any(user["username"] == "viewer" for user in response.data)


@pytest.mark.django_db
def test_staff_can_create_user_with_screen_access():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/users/",
        {
            "username": "analyst",
            "password": "pass12345",
            "is_staff": False,
            "is_active": True,
            "allowed_screens": ["dashboard", "logs"],
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["allowed_screens"] == ["dashboard", "logs"]
    created = User.objects.get(username="analyst")
    assert created.password.startswith("bcrypt_sha256$")
    assert created.screen_access.allowed_screens == ["dashboard", "logs"]


@pytest.mark.django_db
def test_staff_can_manage_dynamic_screen_ids():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/users/",
        {
            "username": "custom-access",
            "password": "pass12345",
            "is_staff": False,
            "is_active": True,
            "allowed_screens": ["dashboard", "reports", "reports", "  audit  "],
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["allowed_screens"] == ["dashboard", "reports", "audit"]


@pytest.mark.django_db
def test_staff_can_fetch_available_screens():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/screens/")

    assert response.status_code == 200
    assert any(screen["id"] == "dashboard" and screen["label"] == "Dashboard" for screen in response.data)


@pytest.mark.django_db
def test_staff_can_crud_screen_definitions():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/screens/",
        {
            "id": "reports",
            "label": "Reports",
            "description": "Report dashboard",
            "sort_order": 120,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["id"] == "reports"

    update_response = client.patch(
        f"/api/screens/{create_response.data['pk']}/",
        {"label": "Analytics Reports", "is_active": False},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["label"] == "Analytics Reports"
    assert update_response.data["is_active"] is False

    delete_response = client.delete(f"/api/screens/{create_response.data['pk']}/")
    assert delete_response.status_code == 204


@pytest.mark.django_db
def test_screen_access_is_enforced_on_backend_api():
    user = User.objects.create_user(username="limited", password="pass12345")
    UserScreenAccess.objects.create(user=user, allowed_screens=["dashboard"])
    Token.objects.create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {user.auth_token.key}")

    assert client.get("/api/dashboard/metrics/").status_code == 200
    assert client.get("/api/provider-credentials/").status_code == 403


@pytest.mark.django_db
def test_non_staff_user_can_read_allowed_screen_but_cannot_write_catalog():
    user = User.objects.create_user(username="operator", password="pass12345")
    UserScreenAccess.objects.create(user=user, allowed_screens=["models", "playground"])
    Token.objects.create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {user.auth_token.key}")
    assert client.get("/api/models/").status_code == 200
    create_response = client.post(
        "/api/models/",
        {
            "provider": "ollama",
            "name": "blocked-write",
            "display_name": "Blocked Write",
            "role": "general",
            "quality_level": 3,
            "speed_level": 3,
            "cost_level": 1,
            "privacy_level": "local",
            "context_window": 8192,
            "is_active": True,
        },
        format="json",
    )
    assert create_response.status_code == 403


@pytest.mark.django_db
def test_login_creates_managed_session_and_logout_closes_it():
    user = User.objects.create_user(username="operator", password="pass12345")

    client = APIClient()
    login_response = client.post(
        "/api/auth/login/",
        {"username": "operator", "password": "pass12345"},
        format="json",
        HTTP_USER_AGENT="pytest-browser",
        REMOTE_ADDR="127.0.0.1",
    )

    assert login_response.status_code == 200
    session = UserSession.objects.get(user=user)
    assert login_response.data["token"] == session.token_key
    assert session.user_agent == "pytest-browser"
    assert session.ip_address == "127.0.0.1"

    client.credentials(HTTP_AUTHORIZATION=f"Token {login_response.data['token']}")
    assert client.get("/api/auth/me/").status_code == 200
    logout_response = client.post("/api/auth/logout/")
    session.refresh_from_db()
    assert logout_response.status_code == 204
    assert session.status == "logged_out"
    assert client.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_session_limit_revokes_oldest_session():
    SecurityPolicy.objects.update_or_create(
        pk=1,
        defaults={
            "max_sessions_user": 1,
            "max_sessions_staff": 3,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "on_session_limit": "revoke_oldest",
        },
    )
    user = User.objects.create_user(username="operator", password="pass12345")

    client = APIClient()
    first = client.post("/api/auth/login/", {"username": "operator", "password": "pass12345"}, format="json")
    second = client.post("/api/auth/login/", {"username": "operator", "password": "pass12345"}, format="json")

    assert first.status_code == 200
    assert second.status_code == 200
    assert UserSession.objects.filter(user=user, status="active").count() == 1
    assert UserSession.objects.get(token_key=first.data["token"]).status == "revoked"
    assert UserSession.objects.get(token_key=second.data["token"]).status == "active"


@pytest.mark.django_db
def test_staff_can_update_security_policy_and_revoke_session():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    session = UserSession.objects.create(
        user=staff_user,
        token_key="managed-token",
        ip_address="127.0.0.1",
        user_agent="pytest",
        expires_at=timezone.now() + timedelta(hours=1),
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    policy_response = client.patch(
        "/api/security/policy/",
        {"idle_timeout_minutes": 45, "on_session_limit": "block_new"},
        format="json",
    )
    assert policy_response.status_code == 200
    assert policy_response.data["idle_timeout_minutes"] == 45

    sessions_response = client.get("/api/security/sessions/")
    assert sessions_response.status_code == 200
    assert sessions_response.data[0]["username"] == "admin"

    revoke_response = client.post(f"/api/security/sessions/{session.id}/revoke/")
    session.refresh_from_db()
    assert revoke_response.status_code == 200
    assert session.status == "revoked"
    assert AuditLog.objects.filter(action="security_policy.update", actor=staff_user).exists()
    assert AuditLog.objects.filter(action="session.revoke", resource_id=str(session.id)).exists()


@pytest.mark.django_db
def test_staff_can_view_audit_logs():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    AuditLog.objects.create(
        actor=staff_user,
        action="credential.update",
        resource_type="provider_credential",
        resource_id="1",
        resource_name="OpenAI Prod",
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/security/audit-logs/")

    assert response.status_code == 200
    assert response.data[0]["action"] == "credential.update"
    assert response.data[0]["actor_username"] == "admin"


@pytest.mark.django_db
def test_catalog_writes_record_audit_log():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/models/",
        {
            "provider": "ollama",
            "name": "audit-model",
            "display_name": "Audit Model",
            "model_tier": "standard",
            "role": "general",
            "quality_level": 3,
            "speed_level": 3,
            "cost_level": 1,
            "privacy_level": "local",
            "context_window": 8192,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    model_id = create_response.data["id"]
    assert AuditLog.objects.filter(action="model.create", resource_id=str(model_id), actor=staff_user).exists()

    update_response = client.patch(f"/api/models/{model_id}/", {"display_name": "Audit Model Updated"}, format="json")
    assert update_response.status_code == 200
    assert AuditLog.objects.filter(action="model.update", resource_id=str(model_id), actor=staff_user).exists()


def test_default_rate_limit_settings_are_configured():
    assert "rest_framework.throttling.AnonRateThrottle" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
    assert "rest_framework.throttling.UserRateThrottle" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user"]


@pytest.mark.django_db
def test_staff_can_run_routing_simulation():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="qwen2.5-coder:7b",
        display_name="Qwen Coder",
        role="coding",
        quality_level=4,
        speed_level=4,
        cost_level=1,
        privacy_level="local",
        context_window=32768,
        is_active=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/routing-simulator/",
        {"prompt": "Django stacktrace 에러를 분석해줘", "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["selected_model"] == "qwen2.5-coder:7b"
    assert response.data["candidates"][0]["rank"] == 1
    assert response.data["analysis"]["is_code"] is True


@pytest.mark.django_db
def test_chat_falls_back_to_next_ranked_model(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="openai",
        name="first-fails",
        display_name="First Fails",
        role="general",
        quality_level=3,
        speed_level=5,
        cost_level=1,
        privacy_level="external",
        context_window=8192,
        is_active=True,
    )
    LLMModel.objects.create(
        provider="openai",
        name="second-succeeds",
        display_name="Second Succeeds",
        role="general",
        quality_level=3,
        speed_level=4,
        cost_level=2,
        privacy_level="external",
        context_window=8192,
        is_active=True,
    )

    class FakeProvider:
        def chat(self, *, model, messages, options):
            if model == "first-fails":
                raise RuntimeError("temporary provider failure")
            return LLMResponse(text="fallback response", raw={})

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    monkeypatch.setattr(ChatView, "provider_registry", FakeRegistry())

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/chat/",
        {"prompt": "일반 질문", "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["selected_model"] == "second-succeeds"
    assert response.data["response_text"] == "fallback response"
    assert "first-fails failed" in response.data["routing_reason"]
    assert "second-succeeds succeeded" in response.data["routing_reason"]


@pytest.mark.django_db
def test_dashboard_returns_usage_and_cost_breakdowns():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingLog.objects.create(
        user=staff_user,
        prompt_summary="hello",
        policy="cost-first",
        selected_provider="openrouter",
        selected_model="openai/gpt-4.1-mini",
        routing_reason="test",
        latency_ms=100,
        estimated_tokens=10,
        estimated_cost_usd="0.00120000",
        response_text="ok",
    )
    RoutingLog.objects.create(
        user=staff_user,
        prompt_summary="hello again",
        policy="quality-first",
        selected_provider="ollama",
        selected_model="qwen3:8b",
        routing_reason="test",
        latency_ms=300,
        estimated_tokens=20,
        estimated_cost_usd="0.00000000",
        response_text="ok",
    )
    RoutingLog.objects.create(
        user=staff_user,
        prompt_summary="failed",
        policy="cost-first",
        selected_provider="openrouter",
        selected_model="openai/gpt-4.1-mini",
        routing_reason="cost-first selected; fallback attempts: openrouter failed",
        latency_ms=500,
        estimated_tokens=30,
        estimated_cost_usd="0.00000000",
        response_text="",
        error_message="provider timeout",
    )
    dashboard_model, _ = LLMModel.objects.get_or_create(
        provider="openrouter",
        name="openai/gpt-4.1-mini",
        defaults={
            "display_name": "GPT 4.1 Mini",
            "model_tier": "advanced",
            "role": "general",
            "quality_level": 4,
            "speed_level": 3,
            "cost_level": 3,
            "privacy_level": "external",
            "context_window": 128000,
            "is_active": True,
        },
    )
    dashboard_model.is_active = True
    dashboard_model.save(update_fields=["is_active"])
    ModelHealthRule.objects.create(
        name="OpenRouter failure guard",
        provider="openrouter",
        model_name="openai/gpt-4.1-mini",
        window_minutes=60,
        min_requests=2,
        max_failure_rate_percent="50.00",
        action_on_trigger="exclude",
        is_active=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/dashboard/metrics/")

    assert response.status_code == 200
    assert response.data["total_requests"] == 3
    assert response.data["total_estimated_cost_usd"] == Decimal("0.00120000000000000")
    assert response.data["provider_usage"][0]["selected_provider"] in {"openrouter", "ollama"}
    assert any(item["user__username"] == "admin" for item in response.data["user_usage"])
    assert response.data["recent_logs"][0]["username"] == "admin"
    assert response.data["failed_requests"] == 1
    assert response.data["fallback_attempts"] == 1
    assert response.data["provider_health"][0]["failures"] == 1
    assert response.data["recent_errors"][0]["error_message"] == "provider timeout"
    assert response.data["unhealthy_models"][0]["model_name"] == "openai/gpt-4.1-mini"
    assert response.data["recent_health_events"][0]["event_type"] == "triggered"
    assert response.data["recent_health_events"][0]["model_name"] == "openai/gpt-4.1-mini"
    assert ModelHealthEvent.objects.count() == 1

    duplicate_check_response = client.get("/api/dashboard/metrics/")

    assert duplicate_check_response.status_code == 200
    assert ModelHealthEvent.objects.count() == 1


@pytest.mark.django_db
def test_health_events_api_returns_model_health_transitions():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    rule = ModelHealthRule.objects.create(
        name="Failure guard",
        provider="openrouter",
        model_name="event-model",
        window_minutes=60,
        min_requests=1,
        max_failure_rate_percent="50.00",
        action_on_trigger="exclude",
        is_active=True,
    )
    ModelHealthEvent.objects.create(
        event_type="triggered",
        provider="openrouter",
        model_name="event-model",
        status="unhealthy",
        rule=rule,
        rule_name=rule.name,
        reason="health rule triggered",
        request_count=2,
        failures=1,
        failure_rate="0.5000",
        average_latency_ms=400,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/model-health-events/")

    assert response.status_code == 200
    assert response.data[0]["event_type"] == "triggered"
    assert response.data[0]["rule_name"] == "Failure guard"


@pytest.mark.django_db
def test_manual_health_override_can_force_unhealthy_model_healthy():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    model = LLMModel.objects.create(
        provider="openrouter",
        name="recovering-model",
        display_name="Recovering Model",
        model_tier="advanced",
        role="general",
        quality_level=4,
        speed_level=3,
        cost_level=3,
        privacy_level="external",
        context_window=128000,
        is_active=True,
    )
    for index in range(2):
        RoutingLog.objects.create(
            user=staff_user,
            prompt_summary=f"failed {index}",
            policy="cost-first",
            selected_provider=model.provider,
            selected_model=model.name,
            routing_reason="test",
            latency_ms=100,
            estimated_tokens=10,
            estimated_cost_usd="0.00000000",
            response_text="",
            error_message="provider timeout",
        )
    ModelHealthRule.objects.create(
        name="Recovering guard",
        provider=model.provider,
        model_name=model.name,
        window_minutes=60,
        min_requests=2,
        max_failure_rate_percent="50.00",
        action_on_trigger="exclude",
        is_active=True,
    )
    ModelHealthOverride.objects.create(
        name="Manual recovery",
        provider=model.provider,
        model_name=model.name,
        override_type="force_healthy",
        reason="provider recovered after manual check",
        expires_at=timezone.now() + timedelta(hours=1),
        created_by=staff_user,
        is_active=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/models/")

    assert response.status_code == 200
    payload = next(item for item in response.data if item["name"] == "recovering-model")
    assert payload["health_status"] == "healthy"
    assert "Manual recovery" in payload["health_reason"]


@pytest.mark.django_db
def test_staff_can_crud_model_health_override():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/model-health-overrides/",
        {
            "name": "Temporary block",
            "provider": "openrouter",
            "model_name": "blocked-model",
            "override_type": "force_unhealthy",
            "reason": "manual incident response",
            "expires_at": (timezone.now() + timedelta(hours=2)).isoformat(),
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["created_by_username"] == "admin"
    assert create_response.data["override_type"] == "force_unhealthy"

    update_response = client.patch(
        f"/api/model-health-overrides/{create_response.data['id']}/",
        {"is_active": False},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["is_active"] is False


@pytest.mark.django_db
def test_models_api_includes_health_status():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    model = LLMModel.objects.create(
        provider="openrouter",
        name="flaky-model",
        display_name="Flaky Model",
        model_tier="advanced",
        role="general",
        quality_level=4,
        speed_level=3,
        cost_level=3,
        privacy_level="external",
        context_window=128000,
        is_active=True,
    )
    for index in range(2):
        RoutingLog.objects.create(
            user=staff_user,
            prompt_summary=f"failed {index}",
            policy="cost-first",
            selected_provider=model.provider,
            selected_model=model.name,
            routing_reason="test",
            latency_ms=100,
            estimated_tokens=10,
            estimated_cost_usd="0.00000000",
            response_text="",
            error_message="provider timeout",
        )
    ModelHealthRule.objects.create(
        name="Flaky guard",
        provider=model.provider,
        model_name=model.name,
        window_minutes=60,
        min_requests=2,
        max_failure_rate_percent="50.00",
        action_on_trigger="exclude",
        is_active=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/models/")

    assert response.status_code == 200
    assert response.data[0]["health_status"] == "unhealthy"
    assert "Flaky guard" in response.data[0]["health_reason"]


@pytest.mark.django_db
def test_dashboard_metrics_can_be_filtered_by_period():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    old_log = RoutingLog.objects.create(
        user=staff_user,
        prompt_summary="old",
        policy="cost-first",
        selected_provider="ollama",
        selected_model="qwen3:8b",
        routing_reason="test",
        latency_ms=100,
        estimated_tokens=10,
        estimated_cost_usd="0.00000000",
        response_text="ok",
    )
    recent_log = RoutingLog.objects.create(
        user=staff_user,
        prompt_summary="recent",
        policy="quality-first",
        selected_provider="openrouter",
        selected_model="openai/gpt-4.1-mini",
        routing_reason="test",
        latency_ms=200,
        estimated_tokens=20,
        estimated_cost_usd="0.00100000",
        response_text="ok",
    )
    RoutingLog.objects.filter(id=old_log.id).update(created_at=timezone.now() - timedelta(days=20))
    RoutingLog.objects.filter(id=recent_log.id).update(created_at=timezone.now())

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/dashboard/metrics/?period=7d")

    assert response.status_code == 200
    assert response.data["total_requests"] == 1
    assert response.data["filter"]["period"] == "7d"
    assert response.data["provider_usage"][0]["selected_provider"] == "openrouter"

    all_response = client.get("/api/dashboard/metrics/?period=all")

    assert all_response.status_code == 200
    assert all_response.data["total_requests"] == 2


@pytest.mark.django_db
def test_routing_logs_are_paginated_and_searchable():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    for index in range(12):
        RoutingLog.objects.create(
            user=staff_user,
            prompt_summary=f"prompt {index}",
            policy="cost-first" if index != 11 else "quality-first",
            selected_provider="ollama",
            selected_model="qwen3:8b",
            routing_reason="test",
            latency_ms=100 + index,
            estimated_tokens=10,
            estimated_cost_usd="0.00000000",
            response_text="ok",
        )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    first_page = client.get("/api/routing-logs/?page=1&page_size=5")

    assert first_page.status_code == 200
    assert first_page.data["count"] == 12
    assert len(first_page.data["results"]) == 5
    assert first_page.data["next"]

    search_response = client.get("/api/routing-logs/?search=quality-first")

    assert search_response.status_code == 200
    assert search_response.data["count"] == 1
    assert search_response.data["results"][0]["policy"] == "quality-first"


@pytest.mark.django_db
def test_staff_can_crud_usage_quota():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/usage-quotas/",
        {
            "name": "OpenRouter monthly cap",
            "user": staff_user.id,
            "provider": "openrouter",
            "monthly_request_limit": 100,
            "monthly_cost_limit_usd": "5.000000",
            "action_on_exceed": "local_fallback",
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["username"] == "admin"
    assert create_response.data["provider"] == "openrouter"
    assert create_response.data["current_month_requests"] == 0
    assert create_response.data["current_month_cost_usd"] == Decimal("0")

    update_response = client.patch(
        f"/api/usage-quotas/{create_response.data['id']}/",
        {"monthly_request_limit": 50},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["monthly_request_limit"] == 50


@pytest.mark.django_db
def test_usage_quota_api_includes_monthly_usage_and_burn_rate():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    other_user = User.objects.create_user(username="other", password="pass12345")
    Token.objects.create(user=staff_user)
    quota = UsageQuota.objects.create(
        name="Admin OpenRouter cap",
        user=staff_user,
        provider="openrouter",
        monthly_request_limit=4,
        monthly_cost_limit_usd="1.000000",
        action_on_exceed="block",
        is_active=True,
    )
    for index in range(2):
        RoutingLog.objects.create(
            user=staff_user,
            prompt_summary=f"admin {index}",
            policy="cost-first",
            selected_provider="openrouter",
            selected_model="gpt-test",
            routing_reason="test",
            latency_ms=100,
            estimated_tokens=10,
            estimated_cost_usd="0.25000000",
            response_text="ok",
        )
    RoutingLog.objects.create(
        user=other_user,
        prompt_summary="other",
        policy="cost-first",
        selected_provider="openrouter",
        selected_model="gpt-test",
        routing_reason="test",
        latency_ms=100,
        estimated_tokens=10,
        estimated_cost_usd="0.90000000",
        response_text="ok",
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/usage-quotas/")

    assert response.status_code == 200
    payload = next(item for item in response.data if item["id"] == quota.id)
    assert payload["current_month_requests"] == 2
    assert payload["current_month_cost_usd"] == Decimal("0.500000000000000")
    assert payload["request_usage_ratio"] == 0.5
    assert payload["cost_usage_ratio"] == 0.5
    assert payload["is_exceeded"] is False


@pytest.mark.django_db
def test_chat_blocks_when_usage_quota_is_exceeded():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="openrouter",
        name="blocked-model",
        display_name="Blocked Model",
        role="general",
        quality_level=3,
        speed_level=5,
        cost_level=1,
        privacy_level="external",
        context_window=8192,
        is_active=True,
    )
    UsageQuota.objects.create(
        name="Block OpenRouter",
        user=staff_user,
        provider="openrouter",
        monthly_request_limit=0,
        action_on_exceed="block",
        is_active=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/chat/",
        {"prompt": "hello", "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 429
    assert "monthly request quota exceeded" in response.data["error_message"]


@pytest.mark.django_db
def test_staff_can_crud_model_health_rule():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/model-health-rules/",
        {
            "name": "OpenRouter failure guard",
            "provider": "openrouter",
            "model_name": "",
            "window_minutes": 30,
            "min_requests": 3,
            "max_failure_rate_percent": "50.00",
            "max_average_latency_ms": None,
            "action_on_trigger": "exclude",
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["provider"] == "openrouter"

    update_response = client.patch(
        f"/api/model-health-rules/{create_response.data['id']}/",
        {"max_average_latency_ms": 10000},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["max_average_latency_ms"] == 10000


@pytest.mark.django_db
def test_default_routing_rules_are_available():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.get("/api/routing-rules/")

    assert response.status_code == 200
    assert any(rule["rule_id"] == "R-07" and rule["target_tier"] == "structured" for rule in response.data)


@pytest.mark.django_db
def test_staff_can_crud_custom_routing_rule():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/routing-rules/",
        {
            "rule_id": "R-77",
            "name": "Custom structured route",
            "description": "Custom rule for structured requests.",
            "condition_key": "structured_output",
            "target_tier": "structured",
            "priority": 77,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["target_tier"] == "structured"

    update_response = client.patch(
        f"/api/routing-rules/{create_response.data['id']}/",
        {"priority": 60},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["priority"] == 60


@pytest.mark.django_db
def test_staff_can_crud_threshold_rule():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/threshold-rules/",
        {
            "rule_id": "T-77",
            "name": "Large prompt route",
            "description": "Large prompts prefer long context models.",
            "metric_key": "estimated_tokens",
            "operator": "gte",
            "threshold_value": "10.0000",
            "action_on_trigger": "prefer_tier",
            "target_tier": "long_context",
            "max_tokens": None,
            "priority": 77,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["target_tier"] == "long_context"

    update_response = client.patch(
        f"/api/threshold-rules/{create_response.data['id']}/",
        {"threshold_value": "20.0000"},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["threshold_value"] == "20.0000"


@pytest.mark.django_db
def test_routing_rule_prefers_matching_model_tier(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="standard-fast",
        display_name="Standard Fast",
        model_tier="standard",
        role="general",
        quality_level=4,
        speed_level=5,
        cost_level=1,
        privacy_level="local",
        context_window=8192,
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="structured-safe",
        display_name="Structured Safe",
        model_tier="structured",
        role="coding",
        quality_level=3,
        speed_level=3,
        cost_level=2,
        privacy_level="local",
        context_window=8192,
        is_active=True,
    )
    RoutingRule.objects.create(
        rule_id="R-97",
        name="Structured output route",
        condition_key="structured_output",
        target_tier="structured",
        priority=70,
        is_active=True,
    )

    class FakeProvider:
        def chat(self, *, model, messages, options):
            return LLMResponse(text='{"model": "' + model + '"}', raw={})

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    monkeypatch.setattr(ChatView, "provider_registry", FakeRegistry())

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/chat/",
        {"prompt": "JSON 형식으로 결과를 만들어줘", "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["selected_model"] == "structured-safe"
    assert response.data["matched_rules"][0]["rule_id"] == "R-07"


@pytest.mark.django_db
def test_threshold_rule_prefers_matching_model_tier(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="light-fast",
        display_name="Light Fast",
        model_tier="lightweight",
        role="general",
        quality_level=4,
        speed_level=5,
        cost_level=1,
        privacy_level="local",
        context_window=8192,
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="long-context-safe",
        display_name="Long Context Safe",
        model_tier="long_context",
        role="general",
        quality_level=3,
        speed_level=3,
        cost_level=2,
        privacy_level="local",
        context_window=65536,
        is_active=True,
    )
    ThresholdRule.objects.create(
        rule_id="T-97",
        name="Large prompt route",
        metric_key="estimated_tokens",
        operator="gte",
        threshold_value="10.0000",
        action_on_trigger="prefer_tier",
        target_tier="long_context",
        priority=70,
        is_active=True,
    )

    class FakeProvider:
        def chat(self, *, model, messages, options):
            return LLMResponse(text=f"{model} response", raw={})

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    monkeypatch.setattr(ChatView, "provider_registry", FakeRegistry())

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/chat/",
        {"prompt": "긴 요청입니다. " * 20, "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["selected_model"] == "long-context-safe"
    assert response.data["matched_threshold_rules"][0]["rule_id"] == "T-97"


@pytest.mark.django_db
def test_staff_can_crud_response_validation_rule():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/validation-rules/",
        {
            "rule_id": "V-77",
            "name": "JSON validation",
            "description": "Validate structured output as JSON.",
            "condition_key": "structured_output",
            "validation_type": "json",
            "action_on_fail": "strict_retry",
            "retry_prompt": "Return only valid JSON.",
            "max_retries": 1,
            "target_tier": "",
            "priority": 77,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["validation_type"] == "json"

    update_response = client.patch(
        f"/api/validation-rules/{create_response.data['id']}/",
        {"max_retries": 2},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["max_retries"] == 2


@pytest.mark.django_db
def test_staff_can_crud_recovery_strategy():
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    create_response = client.post(
        "/api/recovery-strategies/",
        {
            "strategy_id": "S-77",
            "name": "Retry once",
            "description": "Retry once after validation failure.",
            "trigger_event": "validation_fail",
            "action": "strict_retry",
            "retry_prompt": "Return only valid JSON.",
            "max_retries": 1,
            "target_tier": "",
            "priority": 77,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["strategy_id"] == "S-77"

    update_response = client.patch(
        f"/api/recovery-strategies/{create_response.data['id']}/",
        {"max_retries": 2},
        format="json",
    )

    assert update_response.status_code == 200
    assert update_response.data["max_retries"] == 2


@pytest.mark.django_db
def test_response_validation_strict_retry_recovers_invalid_json(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="structured-safe",
        display_name="Structured Safe",
        model_tier="structured",
        role="coding",
        quality_level=3,
        speed_level=3,
        cost_level=1,
        privacy_level="local",
        context_window=8192,
        is_active=True,
    )
    RoutingRule.objects.create(
        rule_id="R-88",
        name="Structured output route",
        condition_key="structured_output",
        target_tier="structured",
        priority=70,
        is_active=True,
    )
    strategy = RecoveryStrategy.objects.create(
        strategy_id="S-88",
        name="Strict JSON retry",
        trigger_event="validation_fail",
        action="strict_retry",
        retry_prompt="Return only valid JSON.",
        max_retries=1,
        priority=70,
        is_active=True,
    )
    ResponseValidationRule.objects.create(
        rule_id="V-88",
        name="JSON validation",
        recovery_strategy=strategy,
        condition_key="structured_output",
        validation_type="json",
        action_on_fail="strict_retry",
        retry_prompt="Return only valid JSON.",
        max_retries=1,
        priority=70,
        is_active=True,
    )

    class FakeProvider:
        calls = 0

        def chat(self, *, model, messages, options):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(text="not json", raw={})
            return LLMResponse(text='{"ok": true}', raw={})

    fake_provider = FakeProvider()

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return fake_provider

    monkeypatch.setattr(ChatView, "provider_registry", FakeRegistry())

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/chat/",
        {"prompt": "JSON 형식으로 결과를 만들어줘", "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["response_text"] == '{"ok": true}'
    assert response.data["validation_status"] == "passed"
    assert "strict retry #1 passed validation" in response.data["routing_reason"]


@pytest.mark.django_db
def test_chat_skips_model_when_health_rule_is_triggered(monkeypatch):
    staff_user = User.objects.create_user(username="admin", password="pass12345", is_staff=True)
    Token.objects.create(user=staff_user)
    RoutingPolicy.objects.create(
        name="cost-first",
        display_name="Cost First",
        priority_config={},
        is_active=True,
    )
    LLMModel.objects.create(
        provider="openrouter",
        name="unhealthy-model",
        display_name="Unhealthy Model",
        role="general",
        quality_level=4,
        speed_level=5,
        cost_level=1,
        privacy_level="external",
        context_window=8192,
        is_active=True,
    )
    LLMModel.objects.create(
        provider="ollama",
        name="healthy-local",
        display_name="Healthy Local",
        role="general",
        quality_level=3,
        speed_level=3,
        cost_level=2,
        privacy_level="local",
        context_window=8192,
        is_active=True,
    )
    for index in range(3):
        RoutingLog.objects.create(
            user=staff_user,
            prompt_summary=f"failed {index}",
            policy="cost-first",
            selected_provider="openrouter",
            selected_model="unhealthy-model",
            routing_reason="test",
            latency_ms=100,
            estimated_tokens=10,
            estimated_cost_usd="0.00000000",
            response_text="",
            error_message="provider timeout",
        )
    ModelHealthRule.objects.create(
        name="OpenRouter failure guard",
        provider="openrouter",
        model_name="unhealthy-model",
        window_minutes=60,
        min_requests=3,
        max_failure_rate_percent="50.00",
        action_on_trigger="exclude",
        is_active=True,
    )

    class FakeProvider:
        def chat(self, *, model, messages, options):
            return LLMResponse(text=f"{model} response", raw={})

    class FakeRegistry:
        def get(self, provider_name, credential=None):
            return FakeProvider()

    monkeypatch.setattr(ChatView, "provider_registry", FakeRegistry())

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {staff_user.auth_token.key}")
    response = client.post(
        "/api/chat/",
        {"prompt": "hello", "policy": "cost-first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["selected_model"] == "healthy-local"
    assert "health rule 'OpenRouter failure guard' triggered" in response.data["routing_reason"]
