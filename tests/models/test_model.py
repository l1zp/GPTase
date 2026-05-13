"""Unit tests for gptase.models.model.Model.

Covers Model live surface after the L1 #18 dead-code purge:
construction (default-config + tracking), provider caching by
(base_url, api_key), agent-specific config resolution, generate /
generate_stream wiring to provider + tracking storage, error-path
conversation completion, and shutdown cleanup.
"""
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from gptase.models.model import Model
from gptase.models.providers import OpenAIProvider
from gptase.models.types import ModelConfig
from gptase.models.types import ModelResponse
from gptase.models.types import StreamChunk


def _make_config(**overrides) -> ModelConfig:
    base = {
        "model_name": "gpt-4",
        "api_key": "sk-test",
        "base_url": "https://test.local",
        "stream": False,
    }
    base.update(overrides)
    return ModelConfig(**base)


def _inject_mock_provider(model: Model,
                          *,
                          response=None,
                          stream_chunks=None,
                          raises=None) -> MagicMock:
    """Pre-populate Model's provider cache with a controllable mock.

    Bypasses real OpenAIProvider construction so tests don't touch the
    network or instantiate AsyncOpenAI.
    """
    provider = MagicMock()
    provider.validate_config = AsyncMock(return_value=True)
    provider.close = AsyncMock()

    if raises is not None:
        provider.generate = AsyncMock(side_effect=raises)
    elif response is not None:
        provider.generate = AsyncMock(return_value=response)

    if stream_chunks is not None:

        async def _stream(messages):
            for chunk in stream_chunks:
                yield chunk

        provider.generate_stream = _stream

    cfg = model.default_config
    model._provider_cache[(cfg.base_url, cfg.api_key)] = provider
    return provider


def _ok_response(content="hi") -> ModelResponse:
    return ModelResponse(
        content=content,
        model="gpt-4",
        provider="openai",
        usage={
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3
        },
    )


@pytest.fixture
def basic_model():
    """Model with explicit config + no tracking; cheap to construct."""
    return Model(default_config=_make_config())


@pytest.fixture
async def tracked_model(tmp_path):
    """Model with real ConversationStorage on a tmp sqlite db; auto-shutdown."""
    cfg = _make_config()
    m = Model(default_config=cfg,
              enable_tracking=True,
              tracking_db_path=str(tmp_path / "model.db"))
    await m.initialize_tracking()
    try:
        yield m
    finally:
        await m.shutdown()


class TestModelInit:
    """Construction: explicit config, framework-config fallback, tracking."""

    def test_init_with_explicit_default_config(self):
        cfg = _make_config(model_name="claude-opus-4-7")
        m = Model(default_config=cfg)

        assert m.default_config is cfg
        assert m.enable_tracking is False
        assert m.tracking_storage is None
        assert m._provider_cache == {}

    def test_init_loads_framework_config_when_default_omitted(self, monkeypatch):
        # Patch FrameworkConfig at the import site inside Model.__init__ so
        # we don't actually load the project template config from disk.
        from gptase.utils import config as config_module

        fake_cfg = _make_config(model_name="from-framework")
        fake_framework = MagicMock()
        fake_framework.to_model_config.return_value = fake_cfg
        monkeypatch.setattr(config_module, "FrameworkConfig",
                            MagicMock(return_value=fake_framework))

        m = Model()

        assert m.default_config is fake_cfg
        assert m._framework_config is fake_framework

    def test_init_creates_tracking_storage_when_enabled(self, tmp_path):
        m = Model(default_config=_make_config(),
                  enable_tracking=True,
                  tracking_db_path=str(tmp_path / "trk.db"))

        assert m.enable_tracking is True
        assert m.tracking_storage is not None


class TestCreateProvider:
    """Provider cache: keyed by (base_url, api_key), reuses on repeat call."""

    def test_creates_openai_provider_for_new_config(self, basic_model):
        provider = basic_model.create_provider(basic_model.default_config)

        assert isinstance(provider, OpenAIProvider)
        assert basic_model._provider_cache[(
            basic_model.default_config.base_url,
            basic_model.default_config.api_key,
        )] is provider

    def test_caches_provider_by_base_url_and_api_key(self, basic_model):
        cfg_same = _make_config()
        cfg_other = _make_config(api_key="sk-other")

        first = basic_model.create_provider(cfg_same)
        second = basic_model.create_provider(cfg_same)
        third = basic_model.create_provider(cfg_other)

        assert first is second  # same key -> reuse
        assert first is not third  # different key -> new instance


class TestGetConfigForAgent:
    """Agent-specific config resolution via FrameworkConfig."""

    def test_returns_agent_specific_config_when_available(self, basic_model):
        agent_cfg = _make_config(model_name="claude-opus-4-7", temperature=0.0)
        # Inject a fake FrameworkConfig that returns agent_cfg for the lookup.
        fake_framework = MagicMock()
        fake_framework.get_config_for_agent.return_value = agent_cfg
        basic_model._framework_config = fake_framework

        result = basic_model.get_config_for_agent("vision-image-analyzer")

        assert result is agent_cfg
        fake_framework.get_config_for_agent.assert_called_once_with(
            "vision-image-analyzer")

    def test_falls_back_to_default_when_no_agent_config(self, basic_model):
        fake_framework = MagicMock()
        fake_framework.get_config_for_agent.return_value = None
        basic_model._framework_config = fake_framework

        result = basic_model.get_config_for_agent("unknown-agent")

        assert result is basic_model.default_config


class TestGenerate:
    """generate() wires provider + tracking storage; surfaces error status."""

    async def test_generate_returns_provider_response(self, basic_model):
        _inject_mock_provider(basic_model, response=_ok_response("hello"))

        result = await basic_model.generate([{"role": "user", "content": "hi"}])

        assert result.content == "hello"

    async def test_generate_tracks_conversation_when_storage_enabled(
            self, tracked_model):
        provider = _inject_mock_provider(tracked_model, response=_ok_response("answer"))

        await tracked_model.generate([{"role": "user", "content": "hi"}])

        # Conversation row written.
        cursor = await tracked_model.tracking_storage.db.execute(
            "SELECT status FROM conversations")
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "completed"

        # Response row written with provider's content.
        cursor = await tracked_model.tracking_storage.db.execute(
            "SELECT content FROM responses")
        resp_rows = await cursor.fetchall()
        assert resp_rows[0][0] == "answer"

        provider.generate.assert_awaited_once()

    async def test_generate_marks_conversation_error_on_provider_failure(
            self, tracked_model):
        _inject_mock_provider(tracked_model, raises=RuntimeError("provider boom"))

        with pytest.raises(RuntimeError, match="provider boom"):
            await tracked_model.generate([{"role": "user", "content": "x"}])

        # Conversation must be marked error so the row's not stuck IN_PROGRESS.
        cursor = await tracked_model.tracking_storage.db.execute(
            "SELECT status, error_message FROM conversations")
        row = await cursor.fetchone()
        assert row == ("error", "provider boom")


class TestGenerateStream:
    """generate_stream yields provider chunks; persists each via tracking."""

    async def test_generate_stream_yields_provider_chunks(self, basic_model):
        chunks = [
            StreamChunk(reasoning_content="thinking", is_thinking=True, chunk_index=1),
            StreamChunk(content="hello", chunk_index=2),
            StreamChunk(is_complete=True,
                        chunk_index=3,
                        metadata={"streaming_complete": True}),
        ]
        _inject_mock_provider(basic_model, stream_chunks=chunks)

        received = []
        async for chunk in basic_model.generate_stream([{
                "role": "user",
                "content": "x"
        }]):
            received.append(chunk)

        assert received == chunks  # passthrough preserves chunk identity

    async def test_generate_stream_tracks_chunks_when_storage_enabled(
            self, tracked_model):
        chunks = [
            StreamChunk(content="part1", chunk_index=1),
            StreamChunk(content="part2", chunk_index=2),
            StreamChunk(is_complete=True,
                        chunk_index=3,
                        metadata={"streaming_complete": True}),
        ]
        _inject_mock_provider(tracked_model, stream_chunks=chunks)

        async for _ in tracked_model.generate_stream([{
                "role": "user",
                "content": "x"
        }]):
            pass

        # Each chunk persisted.
        cursor = await tracked_model.tracking_storage.db.execute(
            "SELECT COUNT(*) FROM stream_chunks")
        (count, ) = await cursor.fetchone()
        assert count == 3

        # Final response row updated with concatenated content.
        cursor = await tracked_model.tracking_storage.db.execute(
            "SELECT content FROM responses")
        row = await cursor.fetchone()
        assert row[0] == "part1part2"


class TestShutdown:
    """shutdown() closes cached providers + tracking-storage DB connection."""

    async def test_shutdown_closes_cached_providers(self, basic_model):
        provider = _inject_mock_provider(basic_model)

        await basic_model.shutdown()

        provider.close.assert_awaited_once()
        # Cache cleared so subsequent generate() rebuilds providers fresh.
        assert basic_model._provider_cache == {}

    async def test_shutdown_closes_tracking_storage(self, tmp_path):
        # Build + tear down through shutdown explicitly (not via fixture).
        m = Model(default_config=_make_config(),
                  enable_tracking=True,
                  tracking_db_path=str(tmp_path / "shutdown.db"))
        await m.initialize_tracking()

        assert m.tracking_storage.db._connection is not None

        await m.shutdown()

        # Underlying connection released.
        assert m.tracking_storage.db._connection is None
