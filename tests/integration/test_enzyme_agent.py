import pytest

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig


@pytest.mark.asyncio
async def test_enzyme_agent_text():
    """Test enzyme kinetics extraction with text input."""
    orch = AgentOrchestrator(FrameworkConfig())
    task = {
        "document": {
            "source_type":
            "text",
            "content":
            "computational design active site; kinetic assay Km kcat; directed evolution",
        }
    }
    # Use the renamed agent: enzyme_kinetics_extractor
    res = await orch.agents["enzyme_kinetics_extractor"].process_task(task)
    assert res["status"] == "success"
    # Markdown-based agents return data directly, not nested in "extraction"
    data = res.get("data", {})
    # Check for reactions in the direct data structure
    assert "reactions" in data or "extraction" in data
    if "extraction" in data:
        # Legacy structure
        extraction = data["extraction"]
        assert "reactions" in extraction
        assert "pipeline" in extraction
    else:
        # New markdown-based structure
        assert "reactions" in data
        assert "pipeline" in data
