"""Model - Unified interface for agents to call LLM providers."""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

from src.models.providers import AnthropicProvider
from src.models.providers import BaseProvider
from src.models.providers import LocalProvider
from src.models.providers import OpenAIProvider
from src.models.types import ModelConfig
from src.models.types import ModelProvider
from src.models.types import ModelResponse
from src.models.types import ModelRole
from src.models.types import StreamChunk

logger = logging.getLogger(__name__)


class Model:

    def __init__(
        self,
        default_config: Optional[ModelConfig] = None,
        enable_tracking: bool = False,
        tracking_db_path: str = "data/conversations.db",
    ):
        self.providers: Dict[str, Type[BaseProvider]] = {}
        self.role_configs: Dict[ModelRole, ModelConfig] = {}
        self.default_config = default_config or ModelConfig()
        self._register_providers()

        # Conversation tracking
        self.enable_tracking = enable_tracking
        self.tracking_storage = None
        if enable_tracking:
            from src.conversations.storage import ConversationStorage

            self.tracking_storage = ConversationStorage(
                db_path=tracking_db_path,
                enabled=True,
            )

    def _register_providers(self) -> None:
        self.providers = {
            ModelProvider.OPENAI.value: OpenAIProvider,
            ModelProvider.ANTHROPIC.value: AnthropicProvider,
            ModelProvider.LOCAL.value: LocalProvider,
        }

    async def initialize_tracking(self) -> None:
        """Initialize conversation tracking storage."""
        if self.tracking_storage:
            await self.tracking_storage.initialize()

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self.tracking_storage:
            await self.tracking_storage.db.close()

    def register_provider(self, name: str, provider_class: type[BaseProvider]) -> None:
        self.providers[name] = provider_class

    def set_role_config(self, role: ModelRole, config: ModelConfig) -> None:
        self.role_configs[role] = config
        logger.info("Set model config for role %s: %s", role, config.model_name)

    def get_role_config(self, role: ModelRole) -> ModelConfig:
        return self.role_configs.get(role, self.default_config)

    def create_provider(self, config: ModelConfig) -> BaseProvider:
        # Handle both enum and string types for provider
        provider_key = config.provider
        if hasattr(provider_key, "value"):
            # It's a ModelProvider enum, extract the string value
            provider_key = provider_key.value
        elif isinstance(provider_key, str) and "." in provider_key:
            # It's an enum string like "ModelProvider.OPENAI"
            provider_key = provider_key.split(".")[-1]

        provider_class = self.providers.get(provider_key)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_key}")
        return provider_class(config)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.GENERAL,
        config: Optional[ModelConfig] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> ModelResponse:
        from src.conversations.models import ConversationStatus

        model_config = config or self.get_role_config(role)
        provider = self.create_provider(model_config)
        await provider.validate_config()

        # Start tracking
        conv_id = "tracking_disabled"
        if self.tracking_storage:
            conv_id = await self.tracking_storage.start_conversation(
                model_name=model_config.model_name,
                provider=str(model_config.provider),
                config=model_config,
                agent_id=agent_id,
            )
            await self.tracking_storage.add_messages(conv_id, messages)

            # Link step to conversation if step_id provided
            if step_id:
                await self.tracking_storage.link_step_to_conversation(
                    step_id=step_id,
                    conversation_id=conv_id,
                )

        start_time = time.time()
        try:
            response = await provider.generate(messages)
            latency = time.time() - start_time

            # Store response
            if self.tracking_storage and conv_id != "tracking_disabled":
                await self.tracking_storage.add_response(
                    conversation_id=conv_id,
                    response_content=response.content,
                    reasoning_content=response.reasoning_content,
                    usage=response.usage,
                    latency_seconds=latency,
                )
                await self.tracking_storage.complete_conversation(
                    conv_id, ConversationStatus.COMPLETED)
        except Exception as e:
            if self.tracking_storage and conv_id != "tracking_disabled":
                await self.tracking_storage.complete_conversation(
                    conv_id, ConversationStatus.ERROR, error_message=str(e))
            raise

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

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.GENERAL,
        config: Optional[ModelConfig] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Generate a streaming response, yielding chunks as they arrive.

        This is useful for real-time display of thinking and response content.
        The provider must support streaming (e.g., OpenAI-compatible APIs).

        Args:
            messages: Chat messages to send to the LLM
            role: Model role to use for configuration
            config: Optional model config override
            agent_id: Optional agent ID for session tracking
            session_id: Optional session ID for session tracking
            step_id: Optional step ID for linking to extraction steps

        Yields:
            StreamChunk: Individual chunks of the response with thinking/content
        """
        from src.conversations.models import ConversationStatus

        model_config = config or self.get_role_config(role)
        provider = self.create_provider(model_config)
        await provider.validate_config()

        # Check if provider supports streaming
        if not hasattr(provider, "generate_stream"):
            raise NotImplementedError(
                f"Provider {model_config.provider} does not support streaming")

        # Start tracking
        conv_id = "tracking_disabled"
        response_id = "tracking_disabled"
        if self.tracking_storage:
            conv_id = await self.tracking_storage.start_conversation(
                model_name=model_config.model_name,
                provider=str(model_config.provider),
                config=model_config,
                agent_id=agent_id,
            )
            await self.tracking_storage.add_messages(conv_id, messages)

            # Link step to conversation if step_id provided
            if step_id:
                await self.tracking_storage.link_step_to_conversation(
                    step_id=step_id,
                    conversation_id=conv_id,
                )

            # Create a placeholder response for streaming chunks
            response_id = await self.tracking_storage.add_response(
                conversation_id=conv_id,
                response_content="",
                reasoning_content="",
                usage=None,
                latency_seconds=0,
                metadata={"streaming": True},
            )

        logger.info(
            "Starting streaming response using %s:%s for role %s",
            model_config.provider,
            model_config.model_name,
            role,
        )

        start_time = time.time()
        all_content = []
        all_reasoning = []

        try:
            async for chunk in provider.generate_stream(messages):
                # Store streaming chunks
                if self.tracking_storage and conv_id != "tracking_disabled":
                    await self.tracking_storage.add_stream_chunk(
                        response_id=response_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        reasoning_content=chunk.reasoning_content,
                        is_thinking=chunk.is_thinking,
                        is_complete=chunk.is_complete,
                    )

                if chunk.content:
                    all_content.append(chunk.content)
                if chunk.reasoning_content:
                    all_reasoning.append(chunk.reasoning_content)

                yield chunk

        except Exception as e:
            if self.tracking_storage and conv_id != "tracking_disabled":
                await self.tracking_storage.complete_conversation(
                    conv_id, ConversationStatus.ERROR, error_message=str(e))
            raise

        else:
            # Update final response
            latency = time.time() - start_time
            if self.tracking_storage and conv_id != "tracking_disabled":
                # Extract usage from final chunk if available
                usage = None
                if all_content:
                    # Try to get usage from metadata
                    usage = chunk.metadata.get("usage") if hasattr(chunk,
                                                                   "metadata") else None

                await self.tracking_storage.update_response(
                    response_id=response_id,
                    response_content="".join(all_content),
                    reasoning_content="".join(all_reasoning) if all_reasoning else None,
                    usage=usage,
                    latency_seconds=latency,
                )
                await self.tracking_storage.complete_conversation(conv_id)

        logger.info("Streaming response completed for role %s", role)

    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]:
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
