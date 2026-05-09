"""Unit tests for gptase.memory.storage.ConversationStorage.

Covers the live surface after L1 #14 refactor (-442 lines): conversation
CRUD, streaming chunks, agent state/messages/working-memory upserts,
list_conversations, and the schema-version reset behavior. Dead methods
removed in the immediately prior refactor commit (get_conversation,
search_conversations, the entire extraction_session_* family,
link_step_to_conversation, save_extraction_result) are intentionally
not covered.
"""
from datetime import datetime

import pytest

from gptase.memory.models import AgentMessage
from gptase.memory.models import AgentWorkingMemory
from gptase.memory.models import ConversationStatus
from gptase.memory.models import PersistedAgentState
from gptase.memory.storage import ConversationStorage


@pytest.fixture
async def storage(tmp_path):
    """Initialized ConversationStorage on a tmp sqlite file; auto-closes."""
    s = ConversationStorage(db_path=str(tmp_path / "storage.db"))
    await s.initialize()
    try:
        yield s
    finally:
        await s.close()


class TestStorageInit:
    """Initialize / close lifecycle and the disabled short-circuit."""

    async def test_initialize_creates_database(self, tmp_path):
        s = ConversationStorage(db_path=str(tmp_path / "init.db"))
        await s.initialize()
        try:
            # Schema bootstrap inserts a version row in agent_states.
            cursor = await s.db.execute("SELECT COUNT(*) FROM agent_states")
            (count, ) = await cursor.fetchone()
            assert count == 1
        finally:
            await s.close()

    async def test_disabled_storage_short_circuits_writes(self, tmp_path):
        s = ConversationStorage(db_path=str(tmp_path / "disabled.db"), enabled=False)
        # initialize is a no-op when disabled; sentinel string returned.
        await s.initialize()
        conv_id = await s.start_conversation("m", "p", config=None)

        assert conv_id == "tracking_disabled"
        # close() is also a no-op when disabled (does not touch self.db).
        await s.close()

    async def test_initialize_is_idempotent(self, storage):
        # Second initialize() must not double-init or raise.
        await storage.initialize()
        # Schema version row count stays 1, not 2.
        cursor = await storage.db.execute(
            "SELECT COUNT(*) FROM agent_states "
            "WHERE agent_id = '__storage_schema_version__'")
        (count, ) = await cursor.fetchone()
        assert count == 1


class TestConversationCRUD:
    """Conversation lifecycle: start, add messages, add/update response,
    complete."""

    async def test_start_conversation_returns_uuid(self, storage):
        conv_id = await storage.start_conversation(model_name="gpt-4",
                                                   provider="openai",
                                                   config=None,
                                                   agent_id="my-agent")

        assert isinstance(conv_id, str)
        assert conv_id != "tracking_disabled"

        # Row landed in conversations table.
        cursor = await storage.db.execute(
            "SELECT model_name, provider, agent_id, status FROM conversations "
            "WHERE id = ?", (conv_id, ))
        row = await cursor.fetchone()
        assert row == ("gpt-4", "openai", "my-agent", "in_progress")

    async def test_start_conversation_disabled_returns_sentinel(self, tmp_path):
        s = ConversationStorage(db_path=str(tmp_path / "off.db"), enabled=False)

        result = await s.start_conversation("m", "p", config=None)

        assert result == "tracking_disabled"

    async def test_add_messages_serializes_list_content_for_multimodal(self, storage):
        # Pin the multimodal contract: list-typed content (vision messages)
        # is JSON-serialized so the TEXT column accepts it.
        conv_id = await storage.start_conversation("m", "p", config=None)

        multimodal_payload = [
            {
                "type": "text",
                "text": "describe"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;..."
                }
            },
        ]
        messages = [
            {
                "role": "user",
                "content": multimodal_payload
            },
            {
                "role": "assistant",
                "content": "ok"
            },
        ]
        await storage.add_messages(conv_id, messages)

        cursor = await storage.db.execute(
            "SELECT role, content FROM messages "
            "WHERE conversation_id = ? ORDER BY sequence_number", (conv_id, ))
        rows = await cursor.fetchall()
        assert rows[0][0] == "user"
        # Multimodal content stored as JSON string.
        assert rows[0][1].startswith("[")
        assert "image_url" in rows[0][1]
        # Plain string content stored verbatim.
        assert rows[1][1] == "ok"

    async def test_add_response_with_full_metadata(self, storage):
        conv_id = await storage.start_conversation("m", "p", config=None)
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        resp_id = await storage.add_response(
            conversation_id=conv_id,
            response_content="hello world",
            reasoning_content="step 1",
            usage=usage,
            latency_seconds=1.25,
            metadata={"finish_reason": "stop"},
        )

        cursor = await storage.db.execute(
            "SELECT content, reasoning_content, prompt_tokens, "
            "completion_tokens, total_tokens, latency_seconds "
            "FROM responses WHERE id = ?", (resp_id, ))
        row = await cursor.fetchone()
        assert row == ("hello world", "step 1", 10, 5, 15, 1.25)

    async def test_update_response_only_changes_specified_fields(self, storage):
        # Pin the dynamic-UPDATE contract: only fields explicitly passed
        # are written; others retain their pre-update values.
        conv_id = await storage.start_conversation("m", "p", config=None)
        resp_id = await storage.add_response(conv_id,
                                             "draft",
                                             usage={
                                                 "prompt_tokens": 1,
                                                 "completion_tokens": 2,
                                                 "total_tokens": 3
                                             })

        await storage.update_response(resp_id, response_content="final")

        cursor = await storage.db.execute(
            "SELECT content, prompt_tokens, total_tokens "
            "FROM responses WHERE id = ?", (resp_id, ))
        row = await cursor.fetchone()
        # content updated; tokens preserved.
        assert row == ("final", 1, 3)

    async def test_complete_conversation_updates_status(self, storage):
        conv_id = await storage.start_conversation("m", "p", config=None)

        await storage.complete_conversation(conv_id,
                                            status=ConversationStatus.ERROR,
                                            error_message="rate limited")

        cursor = await storage.db.execute(
            "SELECT status, error_message FROM conversations WHERE id = ?", (conv_id, ))
        row = await cursor.fetchone()
        assert row == ("error", "rate limited")


class TestStreamChunks:
    """add_stream_chunk batches without immediate commit."""

    async def test_add_stream_chunk_persists_without_commit(self, storage):
        conv_id = await storage.start_conversation("m", "p", config=None)
        resp_id = await storage.add_response(conv_id, "")

        # add_stream_chunk does NOT commit per-chunk; the row is still
        # visible inside the same connection because aiosqlite returns
        # uncommitted reads from the same connection. After an explicit
        # commit (via update_response or complete_conversation) the
        # chunks survive a reopen — but here we just pin same-connection
        # visibility + the lack of an internal commit.
        await storage.add_stream_chunk(resp_id,
                                       chunk_index=0,
                                       content="hi",
                                       is_complete=False)
        await storage.add_stream_chunk(resp_id,
                                       chunk_index=1,
                                       content=" there",
                                       is_complete=True)

        cursor = await storage.db.execute(
            "SELECT chunk_index, content FROM stream_chunks "
            "WHERE response_id = ? ORDER BY chunk_index", (resp_id, ))
        rows = await cursor.fetchall()
        assert rows == [(0, "hi"), (1, " there")]


class TestQueryAPIs:
    """list_conversations pagination + agent_id filter."""

    async def test_list_conversations_returns_dict_rows(self, storage):
        await storage.start_conversation("m1", "p1", config=None, agent_id="a1")
        await storage.start_conversation("m2", "p2", config=None, agent_id="a2")

        rows = await storage.list_conversations()

        assert len(rows) == 2
        assert all(isinstance(r, dict) for r in rows)
        assert {r["model_name"] for r in rows} == {"m1", "m2"}

    async def test_list_conversations_filtered_by_agent_id(self, storage):
        await storage.start_conversation("m1", "p", config=None, agent_id="alpha")
        await storage.start_conversation("m2", "p", config=None, agent_id="beta")
        await storage.start_conversation("m3", "p", config=None, agent_id="alpha")

        rows = await storage.list_conversations(agent_id="alpha")

        assert len(rows) == 2
        assert all(r["agent_id"] == "alpha" for r in rows)


class TestAgentState:
    """Agent state upsert + lookup."""

    async def test_store_agent_state_upserts(self, storage):
        first = PersistedAgentState(agent_id="planner", state_data='{"step": 1}')
        await storage.store_agent_state(first)
        # Overwrite same agent_id.
        second = PersistedAgentState(agent_id="planner", state_data='{"step": 2}')
        await storage.store_agent_state(second)

        cursor = await storage.db.execute(
            "SELECT state_data FROM agent_states WHERE agent_id = 'planner'")
        rows = await cursor.fetchall()
        # INSERT OR REPLACE keeps a single row per agent_id.
        assert len(rows) == 1
        assert rows[0][0] == '{"step": 2}'

    async def test_get_agent_state_returns_parsed_dict(self, storage):
        await storage.store_agent_state(
            PersistedAgentState(agent_id="x", state_data='{"counter": 7}'))

        result = await storage.get_agent_state("x")

        assert result == {"counter": 7}

    async def test_get_agent_state_returns_none_when_missing(self, storage):
        assert await storage.get_agent_state("nonexistent") is None


class TestAgentMessages:
    """Inter-agent message storage + filtered queries."""

    async def test_store_agent_message_returns_uuid(self, storage):
        msg = AgentMessage(sender="planner",
                           recipient="executor",
                           content={"task": "extract"},
                           message_type="task_request")

        returned_id = await storage.store_agent_message(msg)

        assert returned_id == msg.id

    async def test_get_agent_messages_filter_by_participation(self, storage):
        # 'agent_id' filter matches when the agent is sender OR recipient.
        await storage.store_agent_message(
            AgentMessage(sender="alice", recipient="bob", content="hi"))
        await storage.store_agent_message(
            AgentMessage(sender="bob", recipient="charlie", content="forwarded"))
        await storage.store_agent_message(
            AgentMessage(sender="dave", recipient="eve", content="other"))

        bob_messages = await storage.get_agent_messages(agent_id="bob")

        assert len(bob_messages) == 2  # bob is recipient of #1, sender of #2
        senders = {m["sender"] for m in bob_messages}
        recipients = {m["recipient"] for m in bob_messages}
        assert "bob" in senders | recipients

    async def test_get_agent_messages_since_timestamp_filter(self, storage):
        old = datetime(2026, 1, 1, 0, 0, 0)
        new = datetime(2026, 6, 1, 0, 0, 0)

        await storage.store_agent_message(
            AgentMessage(sender="a", recipient="b", content="old", timestamp=old))
        await storage.store_agent_message(
            AgentMessage(sender="a", recipient="b", content="new", timestamp=new))

        # `since` is exclusive (strict >).
        cutoff = datetime(2026, 3, 1, 0, 0, 0)
        results = await storage.get_agent_messages(since=cutoff)

        assert len(results) == 1
        assert results[0]["content"] == "new"


class TestAgentWorkingMemory:
    """Working memory upsert + dict-shaped read."""

    async def test_store_working_memory_upsert_overwrites(self, storage):
        await storage.store_agent_working_memory(
            AgentWorkingMemory(agent_id="enzymes", summary="first pass"))
        await storage.store_agent_working_memory(
            AgentWorkingMemory(agent_id="enzymes", summary="updated pass"))

        cursor = await storage.db.execute("SELECT summary FROM agent_working_memory "
                                          "WHERE agent_id = 'enzymes'")
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "updated pass"

    async def test_get_working_memory_returns_dict_with_metadata(self, storage):
        await storage.store_agent_working_memory(
            AgentWorkingMemory(agent_id="vision",
                               summary="3 papers analyzed",
                               metadata={"source": "test"}))

        result = await storage.get_agent_working_memory("vision")

        assert result is not None
        assert result["agent_id"] == "vision"
        assert result["summary"] == "3 papers analyzed"
        assert result["metadata"] == {"source": "test"}


class TestSchemaVersionReset:
    """_ensure_storage_schema_version wipes legacy data on version mismatch."""

    async def test_initialize_clears_data_when_version_changes(self, tmp_path):
        # Seed a DB at a "legacy" version with persisted data.
        db_path = str(tmp_path / "legacy.db")
        seed = ConversationStorage(db_path=db_path)
        await seed.initialize()
        try:
            # Force a non-current version + add a working-memory row.
            await seed.db.execute(
                "INSERT OR REPLACE INTO agent_states "
                "(agent_id, state_data, last_updated) VALUES (?, ?, ?)",
                ("__storage_schema_version__", '{"version": "ancient"}',
                 "2026-01-01T00:00:00"),
            )
            await seed.store_agent_working_memory(
                AgentWorkingMemory(agent_id="memory-agent", summary="old data"))
            await seed.db.commit()
        finally:
            await seed.close()

        # Reopen — schema version mismatch must trigger _reset_legacy_history.
        reopened = ConversationStorage(db_path=db_path)
        await reopened.initialize()
        try:
            wm = await reopened.get_agent_working_memory("memory-agent")
            # Reset wiped the working memory row.
            assert wm is None
            # Version row was rewritten to current.
            cursor = await reopened.db.execute(
                "SELECT state_data FROM agent_states "
                "WHERE agent_id = '__storage_schema_version__'")
            row = await cursor.fetchone()
            assert row is not None
            import json
            assert json.loads(row[0])["version"] != "ancient"
        finally:
            await reopened.close()

    async def test_initialize_preserves_data_when_version_unchanged(self, tmp_path):
        db_path = str(tmp_path / "stable.db")
        first = ConversationStorage(db_path=db_path)
        await first.initialize()
        try:
            await first.store_agent_working_memory(
                AgentWorkingMemory(agent_id="persistent", summary="kept"))
        finally:
            await first.close()

        # Same version on reopen — data must survive.
        second = ConversationStorage(db_path=db_path)
        await second.initialize()
        try:
            wm = await second.get_agent_working_memory("persistent")
            assert wm is not None
            assert wm["summary"] == "kept"
        finally:
            await second.close()
