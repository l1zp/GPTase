"""
Model Manager - Central management for LLM models
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.models.providers import AnthropicProvider
from src.models.providers import BaseProvider
from src.models.providers import CustomProvider
from src.models.providers import LocalProvider
from src.models.providers import OpenAIProvider
from src.models.types import ModelConfig
from src.models.types import ModelProvider
from src.models.types import ModelResponse
from src.models.types import ModelRole

logger = logging.getLogger(__name__)


class ModelManager:
    """Central manager for all LLM models and providers."""

    def __init__(self, default_config: ModelConfig = None):
        self.providers: Dict[str, BaseProvider] = {}
        self.role_configs: Dict[ModelRole, ModelConfig] = {}
        self.default_config = default_config or ModelConfig()

        # Register default providers
        self._register_providers()

    def _register_providers(self) -> None:
        """Register available providers."""
        self.providers = {
            ModelProvider.OPENAI: OpenAIProvider,
            ModelProvider.ANTHROPIC: AnthropicProvider,
            ModelProvider.LOCAL: LocalProvider,
            ModelProvider.CUSTOM: CustomProvider,
        }

    def set_role_config(self, role: ModelRole, config: ModelConfig) -> None:
        """Set configuration for a specific role."""
        self.role_configs[role] = config
        logger.info(f"Set model config for role {role}: {config.model_name}")

    def get_role_config(self, role: ModelRole) -> ModelConfig:
        """Get configuration for a specific role."""
        return self.role_configs.get(role, self.default_config)

    def create_provider(self, config: ModelConfig) -> BaseProvider:
        """Create a provider instance based on configuration."""
        provider_class = self.providers.get(config.provider)
        if not provider_class:
            raise ValueError(f"Unknown provider: {config.provider}")

        return provider_class(config)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.GENERAL,
        config: ModelConfig = None,
    ) -> ModelResponse:
        """Generate response using the appropriate model."""

        # Get configuration
        model_config = config or self.get_role_config(role)

        # Create provider
        provider = self.create_provider(model_config)

        # Validate provider
        await provider.validate_config()

        # Generate response
        response = await provider.generate(messages)

        logger.info(f"Generated response using {model_config.provider}:"
                    f"{model_config.model_name} for role {role}")

        return response

    async def generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.GENERAL,
        config: ModelConfig = None,
        max_retries: int = 3,
    ) -> ModelResponse:
        """Generate response with retry logic."""

        model_config = config or self.get_role_config(role)
        max_attempts = max_retries or model_config.max_retries

        for attempt in range(max_attempts):
            try:
                return await self.generate(messages, role, config)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(2**attempt)  # Exponential backoff

    async def health_check(self, provider: ModelProvider = None) -> Dict[str, Any]:
        """Check health of providers."""
        if provider:
            base_config = self.get_role_config(ModelRole.GENERAL)
            config = (base_config.model_copy(deep=True) if hasattr(
                base_config, "model_copy") else base_config.copy())
            config.provider = provider
            try:
                provider_instance = self.create_provider(config)
                return await provider_instance.health_check()
            except Exception as e:
                return {"status": "unhealthy", "error": str(e), "provider": provider}
        else:
            results = {}
            for prov in ModelProvider:
                try:
                    results[prov] = await self.health_check(prov)
                except Exception as e:
                    results[prov] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "provider": prov,
                    }
            return results

    async def list_available_models(self, provider: ModelProvider = None) -> List[str]:
        prov = provider or self.default_config.provider
        if prov == ModelProvider.OPENAI:
            return [
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-4.1-mini",
                "gpt-4.1",
            ]
        if prov == ModelProvider.ANTHROPIC:
            return ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]
        if prov == ModelProvider.LOCAL:
            return ["local"]
        if prov == ModelProvider.CUSTOM:
            return ["custom"]
        return []

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_providers": len(self.providers),
            "role_configs": len(self.role_configs),
            "default_provider": self.default_config.provider,
            "default_model": self.default_config.model_name,
        }

    def __repr__(self) -> str:
        return f"ModelManager(providers={len(self.providers)}, role_configs={len(self.role_configs)})"
