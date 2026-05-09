"""Unit tests for gptase.models.types — pydantic dataclasses for the LLM layer.

Covers the live surface after L0 #9 refactor: TextContent, ImageUrlContent,
ModelConfig, ToolCall, ModelResponse, StreamChunk. Dead members removed in
the immediately prior refactor commit (save_json, persist_response,
system_prompt, MultimodalContent) are intentionally not covered.
"""
from gptase.models.types import ImageUrlContent
from gptase.models.types import ModelConfig
from gptase.models.types import ModelResponse
from gptase.models.types import StreamChunk
from gptase.models.types import TextContent
from gptase.models.types import ToolCall


class TestTextContent:
    """Plain text part of a multimodal message."""

    def test_creation_and_serialization(self):
        content = TextContent(text="Hello, world!")

        assert content.type == "text"
        assert content.text == "Hello, world!"

        dumped = content.model_dump()
        assert dumped == {"type": "text", "text": "Hello, world!"}


class TestImageUrlContent:
    """Image URL part of a multimodal message (base64 data URL or remote URL)."""

    def test_creation_and_serialization(self):
        url = "data:image/png;base64,iVBORw0KGgo="
        content = ImageUrlContent(image_url={"url": url})

        assert content.type == "image_url"
        assert content.image_url == {"url": url}

        dumped = content.model_dump()
        assert dumped == {"type": "image_url", "image_url": {"url": url}}


class TestModelConfig:
    """LLM call configuration shared across providers."""

    def test_default_values(self):
        cfg = ModelConfig()

        assert cfg.model_name == "gpt-4"
        assert cfg.api_key is None
        assert cfg.base_url is None
        assert cfg.temperature == 0.1
        assert cfg.max_tokens == 131072
        assert cfg.timeout == 30
        assert cfg.max_retries == 3
        assert cfg.stream is True
        assert cfg.enable_thinking is True
        assert cfg.provider is None

    def test_provider_routing_carried_through(self):
        cfg = ModelConfig(provider={"sort": "input_length"})

        assert cfg.provider == {"sort": "input_length"}


class TestToolCall:
    """Single tool call requested by the LLM."""

    def test_minimal_creation(self):
        call = ToolCall(id="call_42", name="Read", arguments='{"path": "/tmp/x"}')

        assert call.id == "call_42"
        assert call.name == "Read"
        assert call.arguments == '{"path": "/tmp/x"}'


class TestModelResponse:
    """Full response from a non-streaming LLM call."""

    def test_minimal_required_fields(self):
        resp = ModelResponse(content="hi", model="gpt-4", provider="openai")

        assert resp.content == "hi"
        assert resp.model == "gpt-4"
        assert resp.provider == "openai"
        # Defaults for optional metadata + tool fields:
        assert resp.reasoning_content is None
        assert resp.usage == {}
        assert resp.metadata == {}
        assert resp.tool_calls is None
        assert resp.finish_reason is None

    def test_with_tool_calls(self):
        call = ToolCall(id="c1", name="Bash", arguments='{"cmd": "ls"}')
        resp = ModelResponse(
            content="",
            model="gpt-4",
            provider="openai",
            tool_calls=[call],
            finish_reason="tool_calls",
        )

        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "Bash"
        assert resp.finish_reason == "tool_calls"


class TestStreamChunk:
    """Single chunk in a streaming LLM response."""

    def test_default_chunk(self):
        chunk = StreamChunk()

        assert chunk.content == ""
        assert chunk.reasoning_content == ""
        assert chunk.is_thinking is False
        assert chunk.is_complete is False
        assert chunk.chunk_index == 0
        assert chunk.metadata == {}

    def test_full_chunk_with_thinking_and_completion(self):
        chunk = StreamChunk(
            content="final answer",
            reasoning_content="step 1: ...",
            is_thinking=False,
            is_complete=True,
            chunk_index=42,
            metadata={"finish_reason": "stop"},
        )

        assert chunk.content == "final answer"
        assert chunk.reasoning_content == "step 1: ..."
        assert chunk.is_complete is True
        assert chunk.chunk_index == 42
        assert chunk.metadata == {"finish_reason": "stop"}
