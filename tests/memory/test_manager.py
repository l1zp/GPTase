"""Unit tests for gptase.memory.manager.MemoryManager.

Covers the live surface after L1 #15 dead-code purge: lifecycle,
db_path resolution from dict / pydantic config, polymorphic dispatch
on store_agent_state and store_agent_working_memory, the
pydantic-shaped get_agent_working_memory, and the get_usage probe.

The polymorphic dispatch tests are the most valuable — they pin the
contract that MemoryManager accepts both raw dicts (web/API JSON
input) and pydantic models (typed Python callers) without forcing
either shape on the caller.
"""
import pytest

from gptase.memory.manager import MemoryManager
from gptase.memory.models import AgentWorkingMemory
from gptase.memory.models import PersistedAgentState
from gptase.memory.storage import ConversationStorage


@pytest.fixture
async def manager(tmp_path):
    """Initialized MemoryManager backed by a tmp sqlite db; auto-closes."""
    storage = ConversationStorage(db_path=str(tmp_path / "manager.db"))
    m = MemoryManager(storage=storage)
    await m.initialize()
    try:
        yield m
    finally:
        await m.close()


class TestMemoryManagerInit:
    """Constructor: storage injection + db_path resolution from config."""

    def test_init_with_default_storage_creates_conversation_storage(self):
        m = MemoryManager()

        assert isinstance(m.storage, ConversationStorage)
        # Default db_path used when no config provided.
        assert "conversations.db" in str(m.storage.db.db_path)

    def test_init_uses_custom_db_path_from_dict_config(self, tmp_path):
        custom = str(tmp_path / "custom.db")

        m = MemoryManager(config={"db_path": custom})

        assert str(m.storage.db.db_path) == custom

    def test_init_uses_custom_db_path_from_pydantic_memory_config(self, tmp_path):
        # Simulate the pydantic config object via getattr access.
        custom = str(tmp_path / "pydantic.db")

        class _FakePydanticConfig:
            db_path = custom

        m = MemoryManager(config=_FakePydanticConfig())

        assert str(m.storage.db.db_path) == custom


class TestLifecycle:
    """initialize() / close() pass through to storage."""

    async def test_initialize_then_close_round_trip(self, tmp_path):
        storage = ConversationStorage(db_path=str(tmp_path / "lifecycle.db"))
        m = MemoryManager(storage=storage)

        await m.initialize()
        # Connection is open after initialize.
        assert storage.db._connection is not None

        await m.close()
        # close() resets the underlying connection.
        assert storage.db._connection is None


class TestAgentState:
    """store_agent_state polymorphic dispatch + get_agent_state round-trip."""

    async def test_store_agent_state_with_pydantic_model(self, manager):
        state = PersistedAgentState(agent_id="planner", state_data='{"step": 5}')

        # Note: MemoryManager wraps the input differently than storage —
        # it constructs its OWN PersistedAgentState from agent_state.agent_id
        # and the JSON-encoded state_data, so passing a pydantic model in
        # gets re-serialized.
        agent_id = await manager.store_agent_state(state)

        assert agent_id == "planner"
        # Round-trip via get_agent_state.
        result = await manager.get_agent_state("planner")
        # The re-encoding wraps the model_dump() under outer JSON.
        assert result is not None
        assert result["agent_id"] == "planner"

    async def test_store_agent_state_with_plain_dict(self, manager):
        # Pin the dict-input branch: agent_state.get("agent_id") is used
        # to extract the id, and the dict itself becomes state_data.
        agent_state = {"agent_id": "executor", "step": 2, "tools": ["Read"]}

        returned = await manager.store_agent_state(agent_state)

        assert returned == "executor"
        result = await manager.get_agent_state("executor")
        assert result == agent_state

    async def test_get_agent_state_returns_none_when_missing(self, manager):
        assert await manager.get_agent_state("nonexistent") is None


class TestAgentWorkingMemory:
    """store_agent_working_memory polymorphic + get returns pydantic."""

    async def test_store_working_memory_accepts_object_or_dict(self, manager):
        # Object form:
        await manager.store_agent_working_memory(
            AgentWorkingMemory(agent_id="vision", summary="from object"))
        # Dict form (gets unpacked into AgentWorkingMemory(**memory_state)):
        await manager.store_agent_working_memory({
            "agent_id": "vision",
            "summary": "from dict overwrite"
        })

        result = await manager.get_agent_working_memory("vision")

        assert result is not None
        # INSERT OR REPLACE behavior: second store overwrites first.
        assert result.summary == "from dict overwrite"

    async def test_get_working_memory_returns_pydantic_with_parsed_timestamp(
            self, manager):
        await manager.store_agent_working_memory(
            AgentWorkingMemory(agent_id="enzymes",
                               summary="3 papers analyzed",
                               metadata={"count": 3}))

        result = await manager.get_agent_working_memory("enzymes")

        # Must be the pydantic class, not a raw dict — pin the contract
        # used by orchestrator.get_agent_working_memory.
        assert isinstance(result, AgentWorkingMemory)
        assert result.agent_id == "enzymes"
        assert result.summary == "3 papers analyzed"
        assert result.metadata == {"count": 3}
        # last_updated is a real datetime, not an iso string.
        from datetime import datetime
        assert isinstance(result.last_updated, datetime)


class TestGetUsage:
    """get_usage feeds AgentOrchestrator.get_system_status."""

    async def test_get_usage_returns_proxy_stats(self, manager):
        usage = await manager.get_usage()

        assert usage == {
            "has_conversations": False,
            "storage_type": "ConversationStorage",
        }
