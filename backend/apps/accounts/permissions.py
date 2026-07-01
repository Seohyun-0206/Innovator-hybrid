from rest_framework.permissions import BasePermission

from apps.accounts.serializers import get_allowed_screens


class HasScreenAccess(BasePermission):
    execute_screens = {"playground", "simulator", "policy-draft", "service-features"}

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # 운영자는 모든 백엔드 API에 접근할 수 있습니다.
        if request.user.is_staff or request.user.is_superuser:
            return True

        # 각 API view가 required_screen을 선언하면 해당 화면 권한이 있는지 검사합니다.
        # 프론트에서 탭을 숨기는 것과 별개로, 직접 API 호출도 서버에서 차단합니다.
        required_screen = getattr(view, "required_screen", None)
        if not required_screen:
            return True
        if required_screen not in get_allowed_screens(request.user):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return required_screen in self.execute_screens
