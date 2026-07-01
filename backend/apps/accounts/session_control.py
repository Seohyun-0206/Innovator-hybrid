import secrets

from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import SecurityPolicy, UserSession


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def create_user_session(*, user, request):
    policy = SecurityPolicy.get_active()
    if policy.block_inactive_user_login and not user.is_active:
        raise AuthenticationFailed("Inactive users cannot login.")

    active_sessions = UserSession.objects.filter(user=user, status="active").order_by("last_seen_at")
    for session in active_sessions:
        if session.is_expired(policy):
            session.mark_expired()
    active_sessions = UserSession.objects.filter(user=user, status="active").order_by("last_seen_at")

    max_sessions = policy.max_sessions_staff if user.is_staff or user.is_superuser else policy.max_sessions_user
    if active_sessions.count() >= max_sessions:
        if policy.on_session_limit == "block_new":
            raise AuthenticationFailed("Maximum active sessions exceeded.")
        sessions_to_revoke = active_sessions[: active_sessions.count() - max_sessions + 1]
        for session in sessions_to_revoke:
            session.revoke()

    return UserSession.objects.create(
        user=user,
        token_key=secrets.token_hex(32),
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        expires_at=timezone.now() + timezone.timedelta(hours=policy.absolute_timeout_hours),
    )


def revoke_user_sessions(user):
    now = timezone.now()
    UserSession.objects.filter(user=user, status="active").update(status="revoked", revoked_at=now)
