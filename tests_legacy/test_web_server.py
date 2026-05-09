from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from gptase.web import server


async def test_list_agents_exposes_orchestrator_identity(monkeypatch):
    list_available_agents = AsyncMock(
        return_value=[{
            "agent_id": "document-structure-analyzer",
            "description": "Analyze document structure",
        }])
    monkeypatch.setattr(server.orchestrator, "list_available_agents",
                        list_available_agents)

    result = await server.list_agents()

    assert result[0]["id"] == "orchestrator"
    assert result[0]["name"] == "Orchestrator"


async def test_chat_with_agent_rejects_unknown_session_type():
    request = server.ChatRequest(
        agent_id="chat",
        query="hello",
        image_paths=None,
        session_type="plan",
    )

    with pytest.raises(Exception, match="Unsupported session_type: plan"):
        await server.chat_with_agent(request)


async def test_chat_with_agent_uses_direct_session_executor(monkeypatch):
    execute_direct_session = AsyncMock(return_value={
        "session_id": "chat_123",
        "session_type": "chat",
        "status": "completed",
    })
    monkeypatch.setattr(server.orchestrator, "execute_direct_session",
                        execute_direct_session)

    request = server.ChatRequest(agent_id="chat",
                                 query="hello",
                                 image_paths=None,
                                 session_id="chat_123",
                                 session_type="chat",
                                 auto_execute=False)
    result = await server.chat_with_agent(request)

    assert result["status"] == "completed"
    execute_direct_session.assert_awaited_once()
    _, kwargs = execute_direct_session.await_args
    assert kwargs["query"] == "hello"
    assert kwargs["agent_id"] == "chat"
    assert kwargs["session_id"] == "chat_123"


async def test_get_agent_memory_returns_working_memory(monkeypatch):
    get_memory = AsyncMock(
        return_value={
            "agent_id": "memory-agent",
            "working_memory": {
                "summary": "Prior context",
                "metadata": {
                    "status": "success"
                },
                "last_updated": "2026-03-23T00:00:00",
            },
        })
    monkeypatch.setattr(server.orchestrator, "get_agent_working_memory", get_memory)

    result = await server.get_agent_memory("memory-agent")

    assert result["agent_id"] == "memory-agent"
    assert result["working_memory"]["summary"] == "Prior context"
    get_memory.assert_awaited_once_with("memory-agent")
