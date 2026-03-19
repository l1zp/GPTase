"""Model - Unified interface for agents to call LLM providers."""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from gptase.models.providers import LocalProvider
from gptase.models.providers import OpenAIProvider
from gptase.models.types import ModelConfig
from gptase.models.types import ModelResponse
from gptase.models.types import StreamChunk

logger = logging.getLogger(__name__)


class Model:

    def __init__(
        self,
        default_config: Optional[ModelConfig] = None,
        enable_tracking: bool = False,
        tracking_db_path: str = "data/conversations.db",
    ):
        self._provider_cache: Dict[tuple, object] = {}
        self._framework_config: Optional["FrameworkConfig"] = None

        if default_config is None:
            from gptase.utils.config import FrameworkConfig
            self._framework_config = FrameworkConfig()
            default_config = self._framework_config.to_model_config()

        self.default_config = default_config

        # Conversation tracking
        self.enable_tracking = enable_tracking
        self.tracking_storage = None
        if enable_tracking:
            from gptase.memory.storage import ConversationStorage

            self.tracking_storage = ConversationStorage(
                db_path=tracking_db_path,
                enabled=True,
            )

    async def initialize_tracking(self) -> None:
        """Initialize conversation tracking storage."""
        if self.tracking_storage:
            await self.tracking_storage.initialize()

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self.tracking_storage:
            await self.tracking_storage.db.close()

    def get_config_for_agent(
            self,
            agent_name: str,
            default_config: Optional[ModelConfig] = None) -> ModelConfig:
        """Get model configuration for a specific agent by name.

        Args:
            agent_name: The agent name (e.g., "vision_image_analyzer").
            default_config: Default config to use if no agent-specific config found.

        Returns:
            ModelConfig for the agent, using agent-specific config if available,
            otherwise falling back to default_config or self.default_config.
        """
        from gptase.utils.config import FrameworkConfig

        # Use cached FrameworkConfig to avoid repeated file I/O
        if self._framework_config is None:
            self._framework_config = FrameworkConfig()

        agent_config = self._framework_config.get_config_for_agent(agent_name)

        if agent_config:
            logger.info(
                "Using agent-specific config for %s: %s",
                agent_name,
                agent_config.model_name,
            )
            return agent_config

        # Fall back to provided default or instance default
        result = default_config if default_config else self.default_config
        if result is None:
            result = self.default_config

        logger.info("Using default config for %s: %s", agent_name, result.model_name)
        return result

    def create_provider(self, config: ModelConfig):
        """Create or reuse a provider instance for the given config.

        Uses LocalProvider for mock testing (use_mock=True),
        OpenAIProvider for all production calls.
        """
        if config.use_mock:
            return LocalProvider(config)

        # Cache OpenAI provider instances by (base_url, api_key) for connection reuse
        cache_key = (config.base_url, config.api_key)
        if cache_key not in self._provider_cache:
            self._provider_cache[cache_key] = OpenAIProvider(config)
        return self._provider_cache[cache_key]

    async def generate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        from gptase.memory.models import ConversationStatus

        # Get agent-specific config if agent_name provided, otherwise use config or default
        if agent_name and not config:
            model_config = self.get_config_for_agent(agent_name,
                                                     default_config=self.default_config)
        else:
            model_config = config or self.default_config

        provider = self.create_provider(model_config)
        await provider.validate_config()

        # Start tracking
        conv_id = "tracking_disabled"
        if self.tracking_storage:
            conv_id = await self.tracking_storage.start_conversation(
                model_name=model_config.model_name,
                provider="openai",
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
            response = await provider.generate(messages, tools=tools)
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
            "Generated response using %s",
            model_config.model_name,
        )

        return response

    async def generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        max_retries: int = 3,
        agent_name: Optional[str] = None,
    ) -> ModelResponse:
        # Get agent-specific config if agent_name provided, otherwise use config or default
        if agent_name and not config:
            model_config = self.get_config_for_agent(agent_name,
                                                     default_config=self.default_config)
        else:
            model_config = config or self.default_config

        max_attempts = max_retries or model_config.max_retries

        for attempt in range(max_attempts):
            try:
                return await self.generate(messages, config, agent_name=agent_name)
            except Exception as e:
                logger.warning("Attempt %d failed: %s", attempt + 1, e)
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(2**attempt)

        raise RuntimeError("unreachable")

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Generate a streaming response, yielding chunks as they arrive.

        This is useful for real-time display of thinking and response content.
        The provider must support streaming (e.g., OpenAI-compatible APIs).

        Args:
            messages: Chat messages to send to the LLM
            config: Optional model config override
            agent_id: Optional agent ID for session tracking
            agent_name: Optional agent name for agent-specific model config
            session_id: Optional session ID for session tracking
            step_id: Optional step ID for linking to extraction steps

        Yields:
            StreamChunk: Individual chunks of the response with thinking/content
        """
        from gptase.memory.models import ConversationStatus

        # Get agent-specific config if agent_name provided, otherwise use config or default
        if agent_name and not config:
            model_config = self.get_config_for_agent(agent_name,
                                                     default_config=self.default_config)
        else:
            model_config = config or self.default_config

        provider = self.create_provider(model_config)
        await provider.validate_config()

        # Check if provider supports streaming
        if not hasattr(provider, "generate_stream"):
            raise NotImplementedError(f"Provider does not support streaming")

        # Start tracking
        conv_id = "tracking_disabled"
        response_id = "tracking_disabled"
        if self.tracking_storage:
            conv_id = await self.tracking_storage.start_conversation(
                model_name=model_config.model_name,
                provider="openai",
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
            "Starting streaming response using %s",
            model_config.model_name,
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

        logger.info("Streaming response completed")

    async def health_check(self,
                           config: Optional[ModelConfig] = None) -> Dict[str, Any]:
        """Run health check on a provider."""
        check_config = config or self.default_config
        try:
            provider = self.create_provider(check_config)
            return await provider.health_check()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "provider": "openai"}

    def get_usage_stats(self) -> Dict[str, Any]:
        return {
            "default_model": self.default_config.model_name,
            "base_url": self.default_config.base_url,
        }

    def __repr__(self) -> str:
        return f"Model(model={self.default_config.model_name})"
