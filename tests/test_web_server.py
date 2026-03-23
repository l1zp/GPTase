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
