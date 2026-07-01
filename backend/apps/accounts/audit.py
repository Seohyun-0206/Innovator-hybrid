from apps.accounts.models import AuditLog
from apps.accounts.session_control import get_client_ip
from typing import Optional


def record_audit_log(
    *,
    request=None,
    actor=None,
    action: str,
    resource_type: str,
    resource_id: str = "",
    resource_name: str = "",
    metadata: Optional[dict] = None,
):
    if request is not None:
        actor = actor or getattr(request, "user", None)
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        resource_name=resource_name or "",
        metadata=metadata or {},
        ip_address=get_client_ip(request) if request is not None else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request is not None else "",
    )
