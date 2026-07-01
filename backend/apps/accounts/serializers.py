from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers

from apps.accounts.models import AuditLog, ScreenDefinition, SecurityPolicy, UserScreenAccess, UserSession
from apps.accounts.screens import get_available_screen_ids, normalize_allowed_screens
from apps.accounts.session_control import revoke_user_sessions


def get_allowed_screens(user: User) -> list[str]:
    # staff/superuser는 운영자 역할이므로 모든 화면 접근을 허용합니다.
    # 일반 사용자는 UserScreenAccess에 저장된 화면 목록만 사용할 수 있습니다.
    if user.is_staff or user.is_superuser:
        return get_available_screen_ids(include_inactive=True)
    access, _ = UserScreenAccess.objects.get_or_create(user=user)
    return access.allowed_screens


class UserSerializer(serializers.ModelSerializer):
    # allowed_screens는 Django User 기본 필드가 아니므로 serializer에서 별도로
    # 받아 UserScreenAccess 모델에 저장합니다.
    allowed_screens = serializers.ListField(
        child=serializers.CharField(max_length=64, allow_blank=False, trim_whitespace=True),
        required=False,
    )
    # 비밀번호는 응답으로 노출하지 않고, 생성/수정 요청에서만 받습니다.
    # 실제 저장은 Django set_password/create_user를 통해 PASSWORD_HASHERS 설정을 탑니다.
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "is_staff",
            "is_active",
            "allowed_screens",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 프론트가 로그인 직후 메뉴를 구성할 수 있도록 사용자 응답에 화면 권한을 포함합니다.
        data["allowed_screens"] = get_allowed_screens(instance)
        return data

    def create(self, validated_data):
        allowed_screens = normalize_allowed_screens(validated_data.pop("allowed_screens", []))
        password = validated_data.pop("password")
        # create_user는 set_password를 호출하므로 평문 비밀번호가 DB에 저장되지 않습니다.
        # 현재 설정에서는 BCryptSHA256PasswordHasher가 사용됩니다.
        user = User.objects.create_user(password=password, **validated_data)
        UserScreenAccess.objects.update_or_create(
            user=user,
            defaults={"allowed_screens": allowed_screens},
        )
        return user

    def update(self, instance, validated_data):
        allowed_screens = validated_data.pop("allowed_screens", None)
        if allowed_screens is not None:
            allowed_screens = normalize_allowed_screens(allowed_screens)
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            # 비밀번호가 빈 문자열이면 기존 비밀번호를 유지합니다.
            # 새 값이 들어온 경우에만 Bcrypt 해시로 재저장합니다.
            instance.set_password(password)
        instance.save()
        if allowed_screens is not None:
            # 화면 권한은 사용자의 인증 정보와 별도로 갱신합니다.
            UserScreenAccess.objects.update_or_create(
                user=instance,
                defaults={"allowed_screens": allowed_screens},
            )
            if SecurityPolicy.get_active().revoke_sessions_on_permission_change:
                revoke_user_sessions(instance)
        return instance


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        # authenticate는 Django password hasher 체인을 사용합니다.
        # 따라서 Bcrypt 계정과 기존 PBKDF2 계정 모두 검증할 수 있습니다.
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user or not user.is_active:
            raise serializers.ValidationError("Invalid username or password.")
        attrs["user"] = user
        return attrs


class ScreenDefinitionSerializer(serializers.ModelSerializer):
    # API 응답에서는 프론트 권한 키로 쓰는 screen_id를 id라는 이름으로 내려줍니다.
    id = serializers.CharField(source="screen_id")

    class Meta:
        model = ScreenDefinition
        fields = ["pk", "id", "label", "description", "sort_order", "is_active"]

    def validate_id(self, value):
        return value.strip()


class SecurityPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityPolicy
        fields = [
            "id",
            "max_sessions_user",
            "max_sessions_staff",
            "idle_timeout_minutes",
            "absolute_timeout_hours",
            "on_session_limit",
            "revoke_sessions_on_permission_change",
            "block_inactive_user_login",
            "updated_at",
        ]


class UserSessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "username",
            "ip_address",
            "user_agent",
            "login_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
            "logout_at",
            "status",
            "is_expired",
        ]

    def get_is_expired(self, instance):
        return instance.is_expired()


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_username",
            "action",
            "resource_type",
            "resource_id",
            "resource_name",
            "metadata",
            "ip_address",
            "user_agent",
            "created_at",
        ]
