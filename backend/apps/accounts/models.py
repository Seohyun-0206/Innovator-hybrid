from django.conf import settings
from django.db import models
from django.utils import timezone


class ScreenDefinition(models.Model):
    # 권한에서 사용할 화면 목록을 DB에서 관리합니다.
    # screen_id는 프론트 탭 id와 백엔드 required_screen 값에 대응되는 안정적인 키입니다.
    screen_id = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "screen_id"]

    def __str__(self):
        return f"{self.label} ({self.screen_id})"


class UserScreenAccess(models.Model):
    # Django 기본 User 모델은 인증 정보만 담당하게 두고, 화면 접근 권한은
    # 별도 1:1 모델에 보관합니다. 이렇게 하면 User 모델 커스터마이징 없이
    # 화면 권한만 독립적으로 확장할 수 있습니다.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="screen_access",
    )
    allowed_screens = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.user.username} screen access"


class SecurityPolicy(models.Model):
    SESSION_LIMIT_CHOICES = [
        ("revoke_oldest", "Revoke oldest session"),
        ("block_new", "Block new login"),
    ]

    max_sessions_user = models.PositiveIntegerField(default=1)
    max_sessions_staff = models.PositiveIntegerField(default=3)
    idle_timeout_minutes = models.PositiveIntegerField(default=30)
    absolute_timeout_hours = models.PositiveIntegerField(default=12)
    on_session_limit = models.CharField(max_length=32, choices=SESSION_LIMIT_CHOICES, default="revoke_oldest")
    revoke_sessions_on_permission_change = models.BooleanField(default=True)
    block_inactive_user_login = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Security Policy"
        verbose_name_plural = "Security Policy"

    def __str__(self):
        return "Security Policy"

    @classmethod
    def get_active(cls):
        policy, _ = cls.objects.get_or_create(pk=1)
        return policy


class UserSession(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
        ("logged_out", "Logged out"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="managed_sessions",
    )
    token_key = models.CharField(max_length=80, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    login_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    logout_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="active")

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self):
        return f"{self.user.username} {self.status}"

    def is_expired(self, policy=None):
        policy = policy or SecurityPolicy.get_active()
        now = timezone.now()
        idle_deadline = self.last_seen_at + timezone.timedelta(minutes=policy.idle_timeout_minutes)
        return now >= self.expires_at or now >= idle_deadline

    def mark_expired(self):
        if self.status == "active":
            self.status = "expired"
            self.save(update_fields=["status"])

    def revoke(self):
        self.status = "revoked"
        self.revoked_at = timezone.now()
        self.save(update_fields=["status", "revoked_at"])

    def logout(self):
        self.status = "logged_out"
        self.logout_at = timezone.now()
        self.save(update_fields=["status", "logout_at"])


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=80, blank=True, default="")
    resource_name = models.CharField(max_length=200, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        actor_name = self.actor.username if self.actor else "system"
        return f"{actor_name} {self.action} {self.resource_type}"
