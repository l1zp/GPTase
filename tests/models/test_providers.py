"""Unit tests for gptase.models.providers.OpenAIProvider.

LocalProvider was deleted in the L1 #17 refactor (see prior commit) so
this file mocks at the openai.AsyncOpenAI client layer directly via
AsyncMock + SimpleNamespace to drive the real response-unpacking,
streaming, and tool-call extraction paths.

Coverage:
- Module helpers (_safe_json / _truncate / _request_size_summary)
- _build_request_params extra_body assembly (thinking + provider
  routing + tools)
- OpenAIProvider.validate_config gate
- generate() non-stream flow including tool-call extraction and the
  auto-disable-streaming-when-tools-present rule
- _handle_streaming_response (accumulating) + generate_stream
  (chunk-by-chunk yield)
- close() cleanup of the underlying httpx client
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gptase.models.providers import _request_size_summary
from gptase.models.providers import _safe_json
from gptase.models.providers import _truncate
from gptase.models.providers import OpenAIProvider
from gptase.models.types import ModelConfig
from gptase.models.types import StreamChunk


def _make_config(**overrides) -> ModelConfig:
    """ModelConfig with sensible test defaults; override per case."""
    base = {
        "model_name": "gpt-4",
        "api_key": "sk-test",
        "base_url": "https://test.local",
        "temperature": 0.1,
        "max_tokens": 1000,
        "timeout": 30,
        "stream": False,
        "enable_thinking": True,
        "provider": None,
    }
    base.update(overrides)
    return ModelConfig(**base)


def _ok_response_namespace(*,
                           content="hi",
                           tool_calls=None,
                           reasoning_content=None) -> SimpleNamespace:
    """SimpleNamespace shaped like the OpenAI non-stream response."""
    return SimpleNamespace(
        id="resp-1",
        model="gpt-4",
        provider=None,  # aiping.cn populates this; openai.com does not
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                    reasoning_content=reasoning_content,
                ),
                finish_reason="stop" if tool_calls is None else "tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class TestModuleHelpers:
    """_safe_json / _truncate / _request_size_summary."""

    def test_safe_json_serialization_and_repr_fallback(self):
        # Normal dict serializes cleanly.
        assert _safe_json({"a": 1}) == '{"a":1}'

        # Non-serializable falls through to default=str (datetime etc.),
        # and an outright-broken object lands in repr.
        class _BadRepr:

            def __repr__(self):
                return "<BadRepr>"

            def __str__(self):
                raise RuntimeError("no str")

        # default=str raises -> outer except catches -> repr fallback.
        assert _safe_json(_BadRepr()) == "<BadRepr>"

    def test_truncate_with_and_without_overflow(self):
        # No overflow: return as-is.
        assert _truncate("short", limit=20) == "short"

        # Overflow: append marker reporting how much was cut.
        out = _truncate("x" * 100, limit=10)
        assert out.startswith("xxxxxxxxxx")
        assert "<truncated 90 chars>" in out

    def test_request_size_summary_counts_messages_tools(self):
        params = {
            "messages": [
                {
                    "role": "user",
                    "content": "hello"
                },
                {
                    "role": "assistant",
                    "content": "world"
                },
            ],
            "tools": [{
                "name": "Read"
            }],
        }

        summary = _request_size_summary(params)

        assert summary["message_count"] == 2
        assert summary["message_content_chars"] == len("hello") + len("world")
        assert summary["tools_count"] == 1
        assert len(summary["message_breakdown"]) == 2
        # Each breakdown entry has index/role/chars.
        assert summary["message_breakdown"][0]["role"] == "user"
        assert summary["message_breakdown"][0]["chars"] == 5


class TestBuildRequestParams:
    """_build_request_params constructs the OpenAI call dict + extra_body."""

    def test_thinking_enabled_by_default_adds_extra_body(self):
        provider = OpenAIProvider(_make_config())

        params = provider._build_request_params([{"role": "user", "content": "x"}])

        assert params["extra_body"] == {"enable_thinking": True}

    def test_thinking_disabled_omits_extra_body(self):
        provider = OpenAIProvider(_make_config(enable_thinking=False))

        params = provider._build_request_params([{"role": "user", "content": "x"}])

        # Both enable_thinking and provider unset -> no extra_body key at all.
        assert "extra_body" not in params

    def test_provider_routing_in_extra_body_without_thinking(self):
        provider = OpenAIProvider(
            _make_config(enable_thinking=False, provider={"sort": "input_length"}))

        params = provider._build_request_params([{"role": "user", "content": "x"}])

        # Provider key set, enable_thinking absent.
        assert params["extra_body"] == {"provider": {"sort": "input_length"}}

    def test_provider_routing_coexists_with_thinking(self):
        provider = OpenAIProvider(_make_config(
            provider={"sort": "input_length"}))  # enable_thinking=True default

        params = provider._build_request_params([{"role": "user", "content": "x"}])

        assert params["extra_body"] == {
            "enable_thinking": True,
            "provider": {
                "sort": "input_length"
            },
        }

    def test_tools_param_added_with_auto_choice(self):
        provider = OpenAIProvider(_make_config())
        tools = [{"type": "function", "function": {"name": "Read"}}]

        params = provider._build_request_params([{
            "role": "user",
            "content": "x"
        }],
                                                tools=tools)

        assert params["tools"] == tools
        assert params["tool_choice"] == "auto"


class TestOpenAIProviderValidate:
    """validate_config gates on api_key presence."""

    async def test_validate_config_raises_without_api_key(self):
        provider = OpenAIProvider(_make_config(api_key=""))

        with pytest.raises(ValueError, match="API key"):
            await provider.validate_config()


class TestOpenAIProviderGenerate:
    """generate() non-stream flow + auto-disable streaming for tools."""

    async def test_generate_non_stream_returns_model_response_with_usage(self):
        provider = OpenAIProvider(_make_config())
        provider.client.chat.completions.create = AsyncMock(
            return_value=_ok_response_namespace(content="hello world"))

        result = await provider.generate([{"role": "user", "content": "hi"}])

        assert result.content == "hello world"
        assert result.model == "gpt-4"
        assert result.provider == "openai"  # falls back when not in response
        assert result.usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
        assert result.finish_reason == "stop"
        assert result.tool_calls is None

    async def test_generate_disables_streaming_when_tools_present(self):
        # config has stream=True but tools force a non-stream call —
        # the OpenAI tool-calling API does not support streaming.
        provider = OpenAIProvider(_make_config(stream=True))
        captured = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return _ok_response_namespace()

        provider.client.chat.completions.create = fake_create

        await provider.generate(
            [{
                "role": "user",
                "content": "x"
            }],
            tools=[{
                "type": "function",
                "function": {
                    "name": "Read"
                }
            }],
        )

        # The provider must have flipped stream=False before the call.
        assert captured["stream"] is False

    async def test_generate_extracts_tool_calls(self):
        provider = OpenAIProvider(_make_config())
        tool_call_response = SimpleNamespace(
            id="tc-1",
            function=SimpleNamespace(name="Read", arguments='{"path":"/x"}'),
        )
        provider.client.chat.completions.create = AsyncMock(
            return_value=_ok_response_namespace(content="",
                                                tool_calls=[tool_call_response]))

        result = await provider.generate([{"role": "user", "content": "x"}])

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.id == "tc-1"
        assert tc.name == "Read"
        assert tc.arguments == '{"path":"/x"}'
        assert result.finish_reason == "tool_calls"


class TestOpenAIProviderStream:
    """Streaming paths: accumulator and chunk-by-chunk yield."""

    @staticmethod
    def _stream_chunk(*, content=None, reasoning_content=None, finish_reason=None):
        return SimpleNamespace(
            id="stream-resp",
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=content,
                                          reasoning_content=reasoning_content),
                    finish_reason=finish_reason,
                )
            ],
            usage=None,
        )

    @staticmethod
    def _final_usage_chunk():
        return SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=4, completion_tokens=6,
                                  total_tokens=10),
        )

    async def test_handle_streaming_response_accumulates_thinking_and_content(self):
        provider = OpenAIProvider(_make_config(stream=True))

        async def fake_stream(**kwargs):

            async def gen():
                yield TestOpenAIProviderStream._stream_chunk(
                    reasoning_content="step 1: ")
                yield TestOpenAIProviderStream._stream_chunk(reasoning_content="done")
                yield TestOpenAIProviderStream._stream_chunk(content="answer ")
                yield TestOpenAIProviderStream._stream_chunk(content="here")
                yield TestOpenAIProviderStream._final_usage_chunk()

            return gen()

        provider.client.chat.completions.create = fake_stream

        result = await provider.generate([{"role": "user", "content": "x"}])

        assert result.content == "answer here"
        assert result.reasoning_content == "step 1: done"
        assert result.usage == {
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
        }
        assert result.metadata["streamed"] is True

    async def test_generate_stream_yields_thinking_then_content_chunks(self):
        provider = OpenAIProvider(_make_config(stream=False))

        async def fake_stream(**kwargs):

            async def gen():
                yield TestOpenAIProviderStream._stream_chunk(
                    reasoning_content="thinking...")
                yield TestOpenAIProviderStream._stream_chunk(content="hello")
                yield TestOpenAIProviderStream._final_usage_chunk()

            return gen()

        provider.client.chat.completions.create = fake_stream

        chunks = []
        async for chunk in provider.generate_stream([{"role": "user", "content": "x"}]):
            chunks.append(chunk)

        # First chunk is thinking, second is content, plus a usage and a
        # final-completion sentinel chunk.
        thinking_chunks = [c for c in chunks if c.is_thinking]
        content_chunks = [c for c in chunks if c.content and not c.is_thinking]
        completion_chunks = [c for c in chunks if c.is_complete]

        assert len(thinking_chunks) == 1
        assert thinking_chunks[0].reasoning_content == "thinking..."
        assert len(content_chunks) == 1
        assert content_chunks[0].content == "hello"
        # The provider yields a usage chunk (is_complete=True) AND a
        # final completion chunk; both are is_complete, so >= 1.
        assert len(completion_chunks) >= 1
        # Every yielded item is a StreamChunk.
        assert all(isinstance(c, StreamChunk) for c in chunks)


class TestOpenAIProviderClose:
    """close() releases the underlying httpx client to avoid CLOSE_WAIT leaks."""

    async def test_close_invokes_aclose_on_client(self):
        provider = OpenAIProvider(_make_config())
        # Replace with a controllable mock; aclose is the preferred name.
        provider.client = SimpleNamespace(aclose=AsyncMock())

        await provider.close()

        provider.client.aclose.assert_awaited_once()
