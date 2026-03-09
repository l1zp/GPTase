"""
LLM provider implementations for different model APIs
"""

from abc import ABC
from abc import abstractmethod
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from gptase.models.types import ModelConfig
from gptase.models.types import ModelProvider
from gptase.models.types import ModelResponse
from gptase.models.types import StreamChunk
from gptase.models.types import ToolCall

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)


class BaseProvider(ABC):

    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.INFO)

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        pass

    @abstractmethod
    async def validate_config(self) -> bool:
        pass

    async def health_check(self) -> Dict[str, Any]:
        try:
            await self.validate_config()
            return {"status": "healthy", "provider": self.config.provider}
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "provider": self.config.provider,
            }


class OpenAIProvider(BaseProvider):

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        if not openai:
            raise ImportError("OpenAI library not installed. Run: pip install openai")

        self.client = openai.AsyncOpenAI(api_key=config.api_key,
                                         base_url=config.base_url or None)

    async def validate_config(self) -> bool:
        if not self.config.api_key:
            raise ValueError("OpenAI API key is required")
        return True

    def _build_request_params(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        params = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "stream": self.config.provider_config.get("stream", False),
        }

        # Add tools if provided
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        # Add extra_body for thinking mode (only when explicitly enabled)
        # Supports both new 'thinking.type' format and legacy 'enable_thinking' boolean
        # Note: Only add extra_body when thinking is explicitly enabled.
        # Many providers (e.g., Gemini) don't recognize these parameters.
        if self.config.is_thinking_enabled():
            if self.config.thinking is not None:
                params["extra_body"] = {"thinking": {"type": "enabled"}}
            else:
                params["extra_body"] = {"enable_thinking": True}

        params.update(self.config.provider_config)
        return params

    async def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        params = self._build_request_params(messages, tools)
        is_stream = params.get("stream", False)

        # Disable streaming when tools are present (streaming doesn't support tool calls)
        if tools and is_stream:
            params["stream"] = False
            is_stream = False
            self.logger.info("Disabled streaming mode for tool calling")

        self.logger.info(
            "OpenAI request: model=%s stream=%s base_url=%s messages=%d tools=%d",
            params.get("model"),
            is_stream,
            self.client.base_url,
            len(messages),
            len(tools) if tools else 0,
        )
        self.logger.debug("OpenAI provider_config=%s", self.config.provider_config)
        self.logger.debug("OpenAI request params=%s", params)

        if is_stream:
            self.logger.debug("Using streaming mode")
            return await self._handle_streaming_response(params)

        self.logger.debug("Using non-streaming mode")
        response = await self.client.chat.completions.create(**params)

        self.logger.info(
            "OpenAI response (non-stream): id=%s model=%s usage=%s",
            getattr(response, "id", None),
            getattr(response, "model", None),
            getattr(response, "usage", None),
        )

        reasoning_content = None
        message = response.choices[0].message
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            reasoning_content = message.reasoning_content

        # Handle tool calls
        tool_calls = None
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ) for tc in message.tool_calls
            ]
            self.logger.info("Response contains %d tool calls", len(tool_calls))

        return ModelResponse(
            content=message.content or "",
            reasoning_content=reasoning_content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            model=response.model,
            provider=ModelProvider.OPENAI,
            metadata={"response_id": response.id},
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
        )

    async def _handle_streaming_response(self, params: Dict[str, Any]) -> ModelResponse:
        reasoning_content = ""
        answer_content = ""
        usage_info: Dict[str, int] = {}
        response_id = None
        chunk_count = 0
        reasoning_chunk_count = 0
        content_chunk_count = 0

        self.logger.debug("Starting streaming response handling")

        try:
            self.logger.debug("Creating stream connection...")
            stream = await self.client.chat.completions.create(**params)
            self.logger.debug("Stream connection established")

            async for chunk in stream:
                chunk_count += 1

                if chunk_count % 50 == 0:
                    self.logger.debug(
                        "Stream progress: chunks=%d reasoning_chunks=%d content_chunks=%d reasoning_len=%d content_len=%d",
                        chunk_count,
                        reasoning_chunk_count,
                        content_chunk_count,
                        len(reasoning_content),
                        len(answer_content),
                    )

                if not chunk.choices:
                    if chunk.usage:
                        usage_info = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        }
                        self.logger.debug("Received usage info: %s", usage_info)
                    continue

                delta = chunk.choices[0].delta

                if (hasattr(delta, "reasoning_content")
                        and delta.reasoning_content is not None):
                    reasoning_chunk_count += 1
                    reasoning_content += delta.reasoning_content
                    if reasoning_chunk_count == 1:
                        self.logger.debug("Started receiving reasoning content")

                if hasattr(delta, "content") and delta.content:
                    content_chunk_count += 1
                    answer_content += delta.content
                    if content_chunk_count == 1:
                        self.logger.debug("Started receiving answer content")

                if not response_id and hasattr(chunk, "id"):
                    response_id = chunk.id
                    self.logger.debug("Received response ID: %s", response_id)

            self.logger.info(
                "OpenAI response (stream): id=%s chunks=%d reasoning_chunks=%d content_chunks=%d reasoning_len=%d content_len=%d usage=%s",
                response_id,
                chunk_count,
                reasoning_chunk_count,
                content_chunk_count,
                len(reasoning_content),
                len(answer_content),
                usage_info,
            )

            return ModelResponse(
                content=answer_content,
                reasoning_content=reasoning_content if reasoning_content else None,
                usage=usage_info,
                model=params.get("model", "unknown"),
                provider=ModelProvider.OPENAI,
                metadata={
                    "response_id": response_id,
                    "streamed": True
                },
            )
        except Exception as e:
            self.logger.exception(
                "Error in streaming response handling (chunks=%d reasoning_chunks=%d content_chunks=%d reasoning_len=%d content_len=%d)",
                chunk_count,
                reasoning_chunk_count,
                content_chunk_count,
                len(reasoning_content),
                len(answer_content),
            )
            raise

    async def generate_stream(
            self, messages: List[Dict[str, str]]) -> AsyncGenerator[StreamChunk, None]:
        """Generate streaming response, yielding chunks as they arrive.

        This method yields StreamChunk objects in real-time, allowing for
        progressive display of thinking and response content.

        Args:
            messages: Chat messages to send to the LLM

        Yields:
            StreamChunk: Individual chunks of the response
        """
        params = self._build_request_params(messages)
        params["stream"] = True  # Force streaming mode

        self.logger.info(
            "OpenAI streaming request: model=%s base_url=%s messages=%d",
            params.get("model"),
            self.client.base_url,
            len(messages),
        )

        chunk_index = 0
        reasoning_content = ""
        answer_content = ""

        try:
            self.logger.debug("Creating stream connection...")
            stream = await self.client.chat.completions.create(**params)
            self.logger.debug("Stream connection established")

            async for chunk in stream:
                chunk_index += 1

                if not chunk.choices:
                    # Yield usage info chunk if available
                    if chunk.usage:
                        yield StreamChunk(
                            chunk_index=chunk_index,
                            is_complete=True,
                            metadata={
                                "usage": {
                                    "prompt_tokens": chunk.usage.prompt_tokens,
                                    "completion_tokens": chunk.usage.completion_tokens,
                                    "total_tokens": chunk.usage.total_tokens,
                                }
                            },
                        )
                    continue

                delta = chunk.choices[0].delta
                has_reasoning = (hasattr(delta, "reasoning_content")
                                 and delta.reasoning_content is not None)
                has_content = hasattr(delta, "content") and delta.content

                # Process reasoning content (thinking)
                if has_reasoning:
                    reasoning_content += delta.reasoning_content
                    yield StreamChunk(
                        reasoning_content=delta.reasoning_content,
                        is_thinking=True,
                        is_complete=False,
                        chunk_index=chunk_index,
                        metadata={
                            "response_id": chunk.id if hasattr(chunk, "id") else None
                        },
                    )

                # Process answer content
                elif has_content:
                    answer_content += delta.content
                    yield StreamChunk(
                        content=delta.content,
                        is_thinking=False,
                        is_complete=False,
                        chunk_index=chunk_index,
                        metadata={
                            "response_id": chunk.id if hasattr(chunk, "id") else None
                        },
                    )

            # Final completion chunk
            yield StreamChunk(
                is_complete=True,
                chunk_index=chunk_index + 1,
                metadata={"streaming_complete": True},
            )

        except Exception as e:
            self.logger.exception("Error in streaming response")
            yield StreamChunk(
                is_complete=True,
                chunk_index=chunk_index + 1,
                metadata={
                    "error": str(e),
                    "streaming_error": True
                },
            )


class LocalProvider(BaseProvider):

    async def validate_config(self) -> bool:
        return True

    async def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        last_user = next(
            (m.get("content") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        return ModelResponse(
            content=f"LocalProvider mock response: {last_user}".strip(),
            model=self.config.model_name,
            provider=ModelProvider.LOCAL,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            metadata={"mock": True},
        )
