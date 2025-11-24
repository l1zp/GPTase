import pytest
from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig

@pytest.mark.asyncio
async def test_enzyme_agent_text():
    orch = AgentOrchestrator(FrameworkConfig())
    task = {
        "document": {
            "source_type": "text",
            "content": "computational design active site; kinetic assay Km kcat; directed evolution"
        }
    }
    res = await orch.agents["enzyme"].process_task(task)
    assert res["status"] == "success"
    data = res["data"]
    assert data["confidence_overall"] >= 0.2
    assert isinstance(data["steps"], list)
