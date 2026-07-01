from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import filters

from apps.accounts.audit import record_audit_log
from apps.accounts.models import AuditLog, ScreenDefinition, SecurityPolicy, UserSession
from apps.accounts.serializers import (
    AuditLogSerializer,
    LoginSerializer,
    ScreenDefinitionSerializer,
    SecurityPolicySerializer,
    UserSerializer,
    UserSessionSerializer,
)
from apps.accounts.screens import get_available_screens
from apps.accounts.session_control import create_user_session


class IsStaffUser(permissions.BasePermission):
    # 사용자 생성/수정은 화면 권한 자체를 바꿀 수 있는 기능이므로 staff에게만 허용합니다.
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class LoginView(APIView):
    # 로그인 전에는 토큰이 없으므로 전역 TokenAuthentication/IsAuthenticated를 우회합니다.
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        # 새 로그인은 관리형 세션 토큰을 발급합니다. 기존 DRF Token은 테스트/레거시
        # 호환을 위해 인증에서만 fallback으로 지원합니다.
        session = create_user_session(user=user, request=request)
        return Response(
            {
                "token": session.token_key,
                "user": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    # 프론트가 새로고침 후 저장된 토큰으로 현재 사용자와 화면 권한을 복구할 때 사용합니다.
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    def post(self, request):
        if isinstance(request.auth, UserSession):
            request.auth.logout()
        else:
            # 레거시 DRF token으로 들어온 요청은 기존 방식대로 토큰을 삭제합니다.
            Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListView(generics.ListCreateAPIView):
    # 사용자 목록과 생성은 staff 전용입니다. 일반 사용자는 자신에게 허용된 화면만 볼 수 있습니다.
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsStaffUser]


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    # 사용자별 화면 권한을 변경할 수 있으므로 상세/수정/삭제도 staff 전용입니다.
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsStaffUser]

    def perform_update(self, serializer):
        before_is_active = serializer.instance.is_active
        user = serializer.save()
        record_audit_log(
            request=self.request,
            action="user.update",
            resource_type="user",
            resource_id=user.id,
            resource_name=user.username,
        )
        if before_is_active and not user.is_active:
            UserSession.objects.filter(user=user, status="active").update(status="revoked", revoked_at=timezone.now())


class ScreenListView(generics.ListCreateAPIView):
    # 사용자 권한 모달과 화면 관리 페이지가 같은 목록을 사용하도록 DB 기준으로 제공합니다.
    queryset = ScreenDefinition.objects.all()
    serializer_class = ScreenDefinitionSerializer
    permission_classes = [IsStaffUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data or get_available_screens(include_inactive=True))


class ScreenDetailView(generics.RetrieveUpdateDestroyAPIView):
    # 화면 id를 수정/삭제하면 기존 사용자 권한의 문자열 값은 자동 변경되지 않습니다.
    # 운영에서는 label/description 중심으로 수정하고, id 변경은 신중하게 다루는 전제입니다.
    queryset = ScreenDefinition.objects.all()
    serializer_class = ScreenDefinitionSerializer
    permission_classes = [IsStaffUser]


class SecurityPolicyView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        return Response(SecurityPolicySerializer(SecurityPolicy.get_active()).data)

    def patch(self, request):
        policy = SecurityPolicy.get_active()
        serializer = SecurityPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_audit_log(
            request=request,
            action="security_policy.update",
            resource_type="security_policy",
            resource_id=policy.id,
            resource_name="Security Policy",
        )
        return Response(serializer.data)


class UserSessionListView(generics.ListAPIView):
    queryset = UserSession.objects.select_related("user").all()
    serializer_class = UserSessionSerializer
    permission_classes = [IsStaffUser]


class UserSessionRevokeView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request, pk):
        session = generics.get_object_or_404(UserSession, pk=pk)
        session.revoke()
        record_audit_log(
            request=request,
            action="session.revoke",
            resource_type="user_session",
            resource_id=session.id,
            resource_name=session.user.username,
        )
        return Response(UserSessionSerializer(session).data)


class AuditLogListView(generics.ListAPIView):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsStaffUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["actor__username", "action", "resource_type", "resource_name", "ip_address"]
    ordering_fields = ["created_at", "action", "resource_type", "resource_name"]
    ordering = ["-created_at"]
