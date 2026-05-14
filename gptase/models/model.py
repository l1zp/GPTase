"""Model - Unified interface for agents to call LLM providers."""

import asyncio
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from gptase.memory.models import ConversationStatus
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
        """Clean up resources.

        Closes both the tracking-storage DB and any cached
        OpenAIProvider httpx clients. Without the provider close, the
        process accumulates CLOSE_WAIT sockets and stalls on exit
        (Slice 1 retro: chat-p shutdown hang).
        """
        for provider in self._provider_cache.values():
            close_fn = getattr(provider, "close", None)
            if close_fn is None:
                continue
            try:
                result = close_fn()
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:  # noqa: BLE001
                logger.debug("Model.shutdown provider close ignored: %s", exc)
        self._provider_cache.clear()
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
        """Create or reuse an OpenAIProvider instance for the given config.

        Cached by (base_url, api_key) so connection pooling reuses the
        underlying httpx client across calls.
        """
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
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        # Get agent-specific config if agent_name provided, otherwise use config or default
        if agent_name and not config:
            model_config = self.get_config_for_agent(agent_name,
                                                     default_config=self.default_config)
        else:
            model_config = config or self.default_config

        provider = self.create_provider(model_config)
        await provider.validate_config()

        logger.info(
            "Model.generate start | agent_id=%s | agent_name=%s | model=%s | timeout=%s | stream=%s | messages=%d",
            agent_id,
            agent_name,
            model_config.model_name,
            model_config.timeout,
            model_config.stream,
            len(messages),
        )

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
            "Generated response using %s in %.2fs",
            model_config.model_name,
            latency,
        )

        return response

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Generate a streaming response, yielding chunks as they arrive.

        This is useful for real-time display of thinking and response content.
        The provider must support streaming (e.g., OpenAI-compatible APIs).

        Args:
            messages: Chat messages to send to the LLM
            config: Optional model config override
            agent_id: Optional agent ID for session tracking
            agent_name: Optional agent name for agent-specific model config

        Yields:
            StreamChunk: Individual chunks of the response with thinking/content
        """
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
        response_id = "tracking_disabled"
        if self.tracking_storage:
            conv_id = await self.tracking_storage.start_conversation(
                model_name=model_config.model_name,
                provider="openai",
                config=model_config,
                agent_id=agent_id,
            )
            await self.tracking_storage.add_messages(conv_id, messages)

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

    async def health_check(
        self,
        agent_name: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        *,
        timeout_s: float = 15.0,
    ) -> Dict[str, Any]:
        """Verify the configured LLM endpoint is reachable + authenticated.

        Sends a single minimal completion (``ping`` with ``max_tokens=8``,
        ``stream=False``, thinking off, timeout-capped) to surface auth /
        network / rate-limit issues before downstream pipelines spawn
        dozens of parallel calls. Tracking storage is bypassed — health
        probes don't appear in conversation history.

        Args:
            agent_name: When provided, resolves the agent-specific config
                via ``get_config_for_agent`` so per-agent overrides are
                actually exercised.
            config: Explicit override; takes precedence over ``agent_name``.
            timeout_s: Hard cap on the test request. Default 15s.

        Returns:
            dict with keys:
              - ``ok`` (bool): True iff the endpoint responded with content.
              - ``status`` (str): one of ``ok`` / ``auth_failed`` /
                ``rate_limited`` / ``server_error`` / ``timeout`` /
                ``network_error`` / ``other_error``.
              - ``model_name`` (str): the configured model tested.
              - ``base_url`` (str): the endpoint hit.
              - ``latency_s`` (float): wall-clock seconds for the probe.
              - ``response_chars`` (int): chars of content in the reply.
              - ``error`` (Optional[str]): one-line error excerpt on failure.
              - ``status_code`` (Optional[int]): HTTP status when extractable.
        """
        if config is None and agent_name:
            config = self.get_config_for_agent(agent_name)
        if config is None:
            config = self.default_config

        # Minimal probe config — short, non-streaming, no thinking.
        probe_config = config.model_copy(
            update={
                "stream": False,
                "max_tokens": 8,
                "timeout": int(timeout_s),
                "enable_thinking": False,
                "max_retries": 0,  # surface auth failure on the first attempt
            })
        provider = self.create_provider(probe_config)
        messages = [{"role": "user", "content": "ping"}]

        status = "ok"
        error_msg: Optional[str] = None
        status_code: Optional[int] = None
        response_chars = 0

        t0 = time.time()
        try:
            response = await asyncio.wait_for(
                provider.generate(messages, tools=None),
                timeout=timeout_s,
            )
            response_chars = len(response.content or "")
            if response_chars == 0:
                status = "other_error"
                error_msg = "endpoint returned empty content"
        except asyncio.TimeoutError:
            status = "timeout"
            error_msg = f"no response within {timeout_s}s"
        except RuntimeError as exc:
            msg = str(exc)
            m = re.search(r"status_code=(\d+)", msg)
            if m:
                status_code = int(m.group(1))
                if status_code in (401, 403):
                    status = "auth_failed"
                elif status_code == 429:
                    status = "rate_limited"
                elif status_code >= 500:
                    status = "server_error"
                else:
                    status = "other_error"
            else:
                lower = msg.lower()
                if any(k in lower for k in ("connect", "timeout", "dns", "resolve")):
                    status = "network_error"
                else:
                    status = "other_error"
            # First diagnostic segment is the most informative snippet.
            error_msg = msg.split(" | ")[0][:200]
        except Exception as exc:  # noqa: BLE001
            status = "other_error"
            error_msg = f"{type(exc).__name__}: {exc!s}"[:200]

        elapsed = time.time() - t0
        result = {
            "ok": status == "ok",
            "status": status,
            "model_name": probe_config.model_name,
            "base_url": probe_config.base_url,
            "latency_s": round(elapsed, 2),
            "response_chars": response_chars,
            "error": error_msg,
            "status_code": status_code,
        }
        log_fn = logger.info if status == "ok" else logger.warning
        log_fn(
            "Model.health_check %s | model=%s | base_url=%s | %.2fs | %s",
            status.upper(),
            probe_config.model_name,
            probe_config.base_url,
            elapsed,
            error_msg or f"{response_chars} chars",
        )
        return result

    def __repr__(self) -> str:
        return f"Model(model={self.default_config.model_name})"
