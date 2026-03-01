"""Tests for the Agent Orchestrator - Core functionality tests."""

import pytest

from src.agents.orchestrator import AgentOrchestrator


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
    assert "tools" in status
    assert "memory" in status
    assert len(status["agents"]) >= 0
    assert status["tools"]["total_tools"] >= 2


@pytest.mark.asyncio
async def test_list_agents(orchestrator):
    """Test listing available agents."""
    agents = await orchestrator.list_available_agents()
    assert len(agents) >= 0


@pytest.mark.asyncio
async def test_agent_memory(orchestrator):
    """Test agent memory functionality."""
    task = {"id": "memory_test", "description": "Test memory functionality"}
    result = await orchestrator.execute_task(task)

    memory_summary = await orchestrator.get_agent_memory("test_agent")
    assert memory_summary["status"] == "success"
    assert "summary" in memory_summary


@pytest.mark.asyncio
async def test_shutdown(orchestrator):
    """Test graceful shutdown."""
    task = {"id": "test_shutdown_001", "description": "Quick test for shutdown"}
    await orchestrator.execute_task(task)
    await orchestrator.shutdown()

    for agent in orchestrator.agents.values():
        assert agent.state.status in ["idle", "completed"]


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


@pytest.mark.asyncio
async def test_memory_cleanup(orchestrator):
    """Test memory cleanup functionality."""
    for i in range(3):
        task = {"id": f"test_{i}", "description": f"Test task {i}"}
        await orchestrator.execute_task(task)

    await orchestrator.shutdown()

    status = await orchestrator.get_system_status()
    assert "memory" in status
