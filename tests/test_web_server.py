from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from gptase.web import server


@pytest.mark.asyncio
async def test_start_plan_forwards_input_data_and_document_path(monkeypatch):
    execute_task = AsyncMock(return_value={"status": "awaiting_approval"})
    monkeypatch.setattr(server.orchestrator, "execute_task", execute_task)

    request = server.PlanStartRequest(
        plan_id="enzyme_extraction_pipeline",
        input_data={
            "text": "extract this enzyme paper",
            "document_path": "/tmp/paper.md",
            "extra": "value",
        },
        document_path="/tmp/paper.md",
        auto_execute=True,
        auto_replan=False,
    )

    result = await server.start_plan(request)

    assert result["status"] == "awaiting_approval"
    execute_task.assert_awaited_once_with({
        "description": "extract this enzyme paper",
        "goal": "extract this enzyme paper",
        "plan_id": "enzyme_extraction_pipeline",
        "input_data": {
            "text": "extract this enzyme paper",
            "document_path": "/tmp/paper.md",
            "extra": "value",
        },
        "auto_execute": True,
        "auto_replan": False,
        "document_path": "/tmp/paper.md",
    })


@pytest.mark.asyncio
async def test_get_agent_memory_returns_working_memory(monkeypatch):
    get_memory = AsyncMock(return_value={
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
