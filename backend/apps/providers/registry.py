from apps.providers.anthropic import AnthropicProvider
from apps.providers.gemini import GeminiProvider
from apps.providers.ollama import OllamaProvider
from apps.providers.openai import OpenAIProvider
from apps.providers.openrouter import OpenRouterProvider


class ProviderRegistry:
    def __init__(self):
        self._provider_factories = {
            "ollama": OllamaProvider,
            "openai": OpenAIProvider,
            "gemini": GeminiProvider,
            "openrouter": OpenRouterProvider,
            "anthropic": AnthropicProvider,
        }
        self._providers = {}

    def get(self, provider_name: str, credential=None):
        if provider_name not in self._provider_factories:
            raise ValueError(f"Provider '{provider_name}' is not configured yet.")
        if credential is not None:
            credential.mark_used()
            return self._provider_factories[provider_name](
                api_key=credential.get_access_token() or None,
                base_url=credential.get_base_url() or None,
            )
        if provider_name not in self._providers:
            self._providers[provider_name] = self._provider_factories[provider_name]()
        return self._providers[provider_name]
