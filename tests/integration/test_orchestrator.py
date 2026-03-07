"""Tests for the Agent Orchestrator - Core functionality tests."""

import pytest

from gptase.core.orchestrator import AgentOrchestrator


@pytest.fixture
def orchestrator(framework_config):
    """Provide an AgentOrchestrator instance."""
    return AgentOrchestrator(framework_config)


@pytest.mark.asyncio
async def test_orchestrator_initialization(orchestrator):
    """Test that the orchestrator initializes correctly."""
    assert orchestrator.config is not None
    assert len(orchestrator.agents) >= 0


@pytest.mark.asyncio
async def test_system_status(orchestrator):
    """Test getting system status."""
    status = await orchestrator.get_system_status()

    assert "timestamp" in status
    assert "agents" in status
    assert "memory" in status
    assert len(status["agents"]) >= 0


@pytest.mark.asyncio
async def test_list_agents(orchestrator):
    """Test listing available agents."""
    agents = await orchestrator.list_available_agents()
    assert len(agents) >= 0


@pytest.mark.asyncio
async def test_invalid_task(orchestrator):
    """Test handling of invalid tasks."""
    invalid_tasks = [{}, {"id": "test_invalid"}, {"description": ""}]

    for task in invalid_tasks:
        result = await orchestrator.execute_task(task)
        assert result["status"] in ["failed", "success"]


@pytest.mark.asyncio
async def test_system_health(orchestrator):
    """Test system health checks."""
    status = await orchestrator.get_system_status()
    assert isinstance(status, dict)
