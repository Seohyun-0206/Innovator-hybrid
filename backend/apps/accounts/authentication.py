from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import SecurityPolicy, UserSession


class ManagedTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        session = UserSession.objects.select_related("user").filter(token_key=key).first()
        if session is None:
            return super().authenticate_credentials(key)

        if session.status != "active":
            raise AuthenticationFailed("Session is not active.")
        if not session.user.is_active:
            raise AuthenticationFailed("User inactive or deleted.")

        policy = SecurityPolicy.get_active()
        if session.is_expired(policy):
            session.mark_expired()
            raise AuthenticationFailed("Session expired.")

        session.last_seen_at = timezone.now()
        session.save(update_fields=["last_seen_at"])
        return (session.user, session)
