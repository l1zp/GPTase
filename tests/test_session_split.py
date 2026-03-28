"""Tests for split chat/agent/plan session storage."""

import json
import logging
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from gptase.agents.types import DirectSession
from gptase.agents.types import GoalSession
from gptase.agents.types import SessionType
from gptase.core.orchestrator import AgentOrchestrator
from gptase.memory.manager import MemoryManager
from gptase.memory.storage import ConversationStorage


async def _row_count(db, table_name: str, where: str = "", params=()) -> int:
    query = f"SELECT COUNT(*) FROM {table_name}"
    if where:
        query += f" WHERE {where}"
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return int(row[0])


def _make_orchestrator(memory_manager: MemoryManager, agents):
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator.agent_id = "orchestrator"
    orchestrator.logger = logging.getLogger("test-orchestrator")
    orchestrator.memory_manager = memory_manager
    orchestrator.agents = agents
    orchestrator.agent_descriptions = {agent_id: agent_id for agent_id in agents}
    orchestrator.plan_manager = MagicMock()
    return orchestrator


class TestSessionSplit:

    async def test_chat_session_persists_under_chat_prefix_only(self, tmp_path):
        manager = MemoryManager(storage=ConversationStorage(
            db_path=str(tmp_path / "sessions.db")))
        await manager.initialize()
        try:
            chat_agent = MagicMock()
            chat_agent.process_task_with_mode = AsyncMock(return_value={
                "status": "success",
                "data": {
                    "content": "Hello back"
                }
            })
            orchestrator = _make_orchestrator(manager, {"chat": chat_agent})

            result = await AgentOrchestrator.execute_direct_session(
                orchestrator,
                session_type=SessionType.CHAT,
                message="Hello",
            )

            assert result["session_type"] == "chat"
            assert result["selected_agent_id"] == "chat"
            assert await _row_count(
                manager.storage.db,
                "agent_states",
                "agent_id LIKE ?",
                ("chat_session:%", ),
            ) == 1
            assert await _row_count(
                manager.storage.db,
                "agent_states",
                "agent_id LIKE ?",
                ("goal_session:%", ),
            ) == 0
        finally:
            await manager.close()

    async def test_agent_session_persists_under_agent_prefix(self, tmp_path):
        manager = MemoryManager(storage=ConversationStorage(
            db_path=str(tmp_path / "sessions.db")))
        await manager.initialize()
        try:
            worker = MagicMock()
            worker.process_task_with_mode = AsyncMock(return_value={
                "status": "success",
                "data": {
                    "content": "done"
                }
            })
            orchestrator = _make_orchestrator(manager, {
                "chat": MagicMock(),
                "worker-agent": worker,
            })

            result = await AgentOrchestrator.execute_direct_session(
                orchestrator,
                session_type=SessionType.AGENT,
                message="Run worker",
                agent_id="worker-agent",
            )

            assert result["session_type"] == "agent"
            assert result["selected_agent_id"] == "worker-agent"
            assert await _row_count(
                manager.storage.db,
                "agent_states",
                "agent_id LIKE ?",
                ("agent_session:%", ),
            ) == 1
        finally:
            await manager.close()

    async def test_list_sessions_returns_mixed_session_types(self, tmp_path):
        manager = MemoryManager(storage=ConversationStorage(
            db_path=str(tmp_path / "sessions.db")))
        await manager.initialize()
        try:
            orchestrator = _make_orchestrator(manager, {"chat": MagicMock()})

            direct_session = DirectSession(
                session_id="chat_1",
                session_type=SessionType.CHAT,
                title="Chat title",
                agent_id="chat",
            )
            await AgentOrchestrator._save_direct_session(orchestrator, direct_session)

            goal_session = GoalSession(session_id="goal_1", goal="Plan title")
            await AgentOrchestrator._save_goal_session(orchestrator, goal_session)

            sessions = await AgentOrchestrator.list_sessions(orchestrator)

            assert {session["session_type"] for session in sessions} == {"chat", "plan"}
        finally:
            await manager.close()
