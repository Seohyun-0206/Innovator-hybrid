import requests
from django.conf import settings
from typing import Optional

from apps.providers.base import BaseLLMProvider, LLMResponse


class OllamaProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        # base URL을 설정 가능하게 두면 로컬 Docker, 원격 Ollama, 테스트 서버를
        # 라우팅 코드 변경 없이 바꿔 사용할 수 있습니다.
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        # 로컬 Ollama는 보통 토큰이 없지만, RunPod/프록시 앞단에서 bearer token을
        # 요구하는 구성이 있을 수 있어 선택적으로 Authorization header를 붙입니다.
        self.api_key = api_key or ""

    def chat(self, *, model: str, messages: list[dict], options: Optional[dict] = None) -> LLMResponse:
        # stream=False를 사용하면 gateway가 단일 응답 payload를 받아 로그 저장과
        # REST API 반환을 단순하게 처리할 수 있습니다. streaming은 별도 경로로 추가할 수 있습니다.
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            f"{self.base_url}/api/chat",
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": options or {},
            },
            timeout=120,
        )
        # 모델 미설치나 Ollama 런타임 오류는 호출자에게 올려보냅니다.
        # 이후 RoutingLog.error_message에 저장되어 대시보드와 디버깅에서 확인할 수 있습니다.
        response.raise_for_status()
        payload = response.json()
        return LLMResponse(
            text=payload.get("message", {}).get("content", ""),
            raw=payload,
        )
