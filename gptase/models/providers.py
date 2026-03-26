"""
LLM provider implementations.

All production models go through OpenAI-compatible APIs (e.g. aiping.cn).
LocalProvider exists only for testing.
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from gptase.models.types import ModelConfig
from gptase.models.types import ModelResponse
from gptase.models.types import StreamChunk
from gptase.models.types import ToolCall

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        return repr(value)


def _truncate(value: Any, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else _safe_json(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"


def _message_content_chars(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        else:
            total += len(_safe_json(content))
    return total


def _message_breakdown(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    breakdown: List[Dict[str, Any]] = []
    for idx, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, str):
            chars = len(content)
        else:
            chars = len(_safe_json(content))
        entry: Dict[str, Any] = {
            "index": idx,
            "role": msg.get("role"),
            "chars": chars,
        }

        tool_call_id = msg.get("tool_call_id")
        if tool_call_id:
            entry["tool_call_id"] = tool_call_id

        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            entry["tool_calls"] = [{
                "id":
                tool_call.get("id"),
                "name": (tool_call.get("function") or {}).get("name"),
            } for tool_call in tool_calls]

        breakdown.append(entry)
    return breakdown


def _request_size_summary(params: Dict[str, Any]) -> Dict[str, Any]:
    messages = params.get("messages") or []
    tools = params.get("tools") or []
    tools_json = _safe_json(tools)
    request_json = _safe_json(params)
    return {
        "message_count": len(messages),
        "message_content_chars": _message_content_chars(messages),
        "message_breakdown": _message_breakdown(messages),
        "tools_count": len(tools),
        "tools_json_chars": len(tools_json),
        "request_json_chars": len(request_json),
    }


def _interesting_response_headers(headers: Any) -> Dict[str, str]:
    if not headers:
        return {}

    interesting: Dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in {
                "x-request-id",
                "content-type",
                "content-length",
                "server",
                "via",
                "date",
                "cf-ray",
                "cf-cache-status",
        } or any(token in lowered
                 for token in ("request", "trace", "provider", "aiping", "route")):
            interesting[key] = value
    return interesting


class OpenAIProvider:
    """OpenAI-compatible provider for all production LLM calls."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.INFO)

        if not openai:
            raise ImportError("OpenAI library not installed. Run: pip install openai")

        self.client = openai.AsyncOpenAI(api_key=config.api_key,
                                         base_url=config.base_url or None)

    async def validate_config(self) -> bool:
        if not self.config.api_key:
            raise ValueError("API key is required")
        return True

    def _format_api_status_error(self, exc: Exception, params: Dict[str, Any]) -> str:
        status_code = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        body = getattr(exc, "body", None)
        response = getattr(exc, "response", None)
        request = getattr(response, "request", None) if response is not None else None
        headers = _interesting_response_headers(
            getattr(response, "headers", None) if response is not None else None)
        request_summary = _request_size_summary(params)

        parts = [
            f"OpenAI-compatible request failed: {type(exc).__name__}",
            f"status_code={status_code}",
            f"request_id={request_id}",
        ]

        if request is not None:
            parts.append(f"request_method={getattr(request, 'method', None)}")
            parts.append(f"request_url={getattr(request, 'url', None)}")

        parts.append(f"request_size={_safe_json(request_summary)}")

        if headers:
            parts.append(f"response_headers={_safe_json(headers)}")

        if body is not None:
            parts.append(f"response_body={_truncate(body)}")
        else:
            parts.append(f"error={_truncate(str(exc))}")

        return " | ".join(parts)

    def _raise_with_diagnostics(self, exc: Exception, params: Dict[str, Any]) -> None:
        if openai and isinstance(exc, getattr(openai, "APIStatusError")):
            message = self._format_api_status_error(exc, params)
            self.logger.error("%s", message)
            raise RuntimeError(message) from exc

        if openai and isinstance(exc, getattr(openai, "APIError")):
            request_summary = _request_size_summary(params)
            message = (
                f"OpenAI-compatible request failed: {type(exc).__name__} | "
                f"request_size={_safe_json(request_summary)} | error={_truncate(str(exc))}"
            )
            self.logger.error("%s", message)
            raise RuntimeError(message) from exc

        raise exc

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
            "stream": self.config.stream,
        }

        # Add tools if provided
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        extra_body: Dict[str, Any] = {}

        if self.config.enable_thinking:
            extra_body["enable_thinking"] = True

        if self.config.provider:
            extra_body["provider"] = self.config.provider

        if extra_body:
            params["extra_body"] = extra_body

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
            "OpenAI request: model=%s stream=%s timeout=%s base_url=%s messages=%d tools=%d request_size=%s",
            params.get("model"),
            is_stream,
            params.get("timeout"),
            self.client.base_url,
            len(messages),
            len(tools) if tools else 0,
            _safe_json(_request_size_summary(params)),
        )
        self.logger.debug("OpenAI request params=%s", params)

        if is_stream:
            self.logger.debug("Using streaming mode")
            return await self._handle_streaming_response(params)

        self.logger.debug("Using non-streaming mode")
        try:
            response = await self.client.chat.completions.create(**params)
        except Exception as e:
            self._raise_with_diagnostics(e, params)

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

        # Extract provider from response if available (aiping.cn returns this)
        provider_name = getattr(response, "provider", None) or "openai"

        return ModelResponse(
            content=message.content or "",
            reasoning_content=reasoning_content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            model=response.model,
            provider=provider_name,
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
                provider="openai",
                metadata={
                    "response_id": response_id,
                    "streamed": True
                },
            )
        except Exception as e:
            if openai and isinstance(e, getattr(openai, "APIError")):
                self._raise_with_diagnostics(e, params)

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

    async def health_check(self) -> Dict[str, Any]:
        try:
            await self.validate_config()
            return {"status": "healthy", "provider": "openai"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "provider": "openai"}


class LocalProvider:
    """Mock provider for testing. Not used in production."""

    def __init__(self, config: ModelConfig):
        self.config = config

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
            provider="local",
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            metadata={"mock": True},
        )

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "provider": "local"}
