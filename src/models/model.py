"""Model - Unified interface for agents to call LLM providers."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

from src.models.providers import (
    AnthropicProvider,
    BaseProvider,
    LocalProvider,
    OpenAIProvider,
)
from src.models.types import ModelConfig, ModelProvider, ModelResponse, ModelRole

logger = logging.getLogger(__name__)


class Model:
    def __init__(self, default_config: Optional[ModelConfig] = None):
        self.providers: Dict[str, Type[BaseProvider]] = {}
        self.role_configs: Dict[ModelRole, ModelConfig] = {}
        self.default_config = default_config or ModelConfig()
        self._register_providers()

    def _register_providers(self) -> None:
        self.providers = {
            ModelProvider.OPENAI.value: OpenAIProvider,
            ModelProvider.ANTHROPIC.value: AnthropicProvider,
            ModelProvider.LOCAL.value: LocalProvider,
        }

    def register_provider(self, name: str, provider_class: type[BaseProvider]) -> None:
        self.providers[name] = provider_class

    def set_role_config(self, role: ModelRole, config: ModelConfig) -> None:
        self.role_configs[role] = config
        logger.info("Set model config for role %s: %s", role, config.model_name)

    def get_role_config(self, role: ModelRole) -> ModelConfig:
        return self.role_configs.get(role, self.default_config)

    def create_provider(self, config: ModelConfig) -> BaseProvider:
        provider_class = self.providers.get(str(config.provider))
        if not provider_class:
            raise ValueError(f"Unknown provider: {config.provider}")
        return provider_class(config)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.GENERAL,
        config: Optional[ModelConfig] = None,
    ) -> ModelResponse:
        model_config = config or self.get_role_config(role)
        provider = self.create_provider(model_config)
        await provider.validate_config()
        response = await provider.generate(messages)

        logger.info(
            "Generated response using %s:%s for role %s",
            model_config.provider,
            model_config.model_name,
            role,
        )

        return response

    async def generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.GENERAL,
        config: Optional[ModelConfig] = None,
        max_retries: int = 3,
    ) -> ModelResponse:
        model_config = config or self.get_role_config(role)
        max_attempts = max_retries or model_config.max_retries

        for attempt in range(max_attempts):
            try:
                return await self.generate(messages, role, config)
            except Exception as e:
                logger.warning("Attempt %d failed: %s", attempt + 1, e)
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(2**attempt)

        raise RuntimeError("unreachable")

    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]:
        if provider:
            base_config = self.get_role_config(ModelRole.GENERAL)
            config = (
                base_config.model_copy(deep=True)
                if hasattr(base_config, "model_copy")
                else base_config.copy()
            )
            config.provider = provider
            try:
                provider_instance = self.create_provider(config)
                return await provider_instance.health_check()
            except Exception as e:
                return {"status": "unhealthy", "error": str(e), "provider": provider}

        results: Dict[str, Dict[str, Any]] = {}
        for prov in self.providers.keys():
            try:
                results[prov] = await self.health_check(prov)
            except Exception as e:
                results[prov] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "provider": prov,
                }
        return results

    async def list_available_models(self, provider: Optional[str] = None) -> List[str]:
        prov = provider or str(self.default_config.provider)
        if prov == ModelProvider.OPENAI.value:
            return [
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-4.1-mini",
                "gpt-4.1",
            ]
        if prov == ModelProvider.ANTHROPIC.value:
            return ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]
        if prov == ModelProvider.LOCAL.value:
            return ["local"]
        return []

    def get_usage_stats(self) -> Dict[str, Any]:
        return {
            "total_providers": len(self.providers),
            "role_configs": len(self.role_configs),
            "default_provider": self.default_config.provider,
            "default_model": self.default_config.model_name,
        }

    def __repr__(self) -> str:
        return f"Model(providers={len(self.providers)}, role_configs={len(self.role_configs)})"
