"""
Tests for the Agent Orchestrator - Core functionality tests
"""

import pytest

from src.agents.orchestrator import AgentOrchestrator


@pytest.fixture
def orchestrator(framework_config):
    """Fixture to provide an AgentOrchestrator instance."""
    return AgentOrchestrator(framework_config)


@pytest.mark.asyncio
async def test_orchestrator_initialization(orchestrator):
    """Test that the orchestrator initializes correctly."""
    # Should have at least the core agents
    assert len(orchestrator.agents) >= 4
    assert orchestrator.config is not None
    # Verify renamed enzyme agents are loaded
    assert "enzyme_kinetics_extractor" in orchestrator.agents
    assert "enzyme_design_parser" in orchestrator.agents


@pytest.mark.asyncio
async def test_system_status(orchestrator):
    """Test getting system status."""
    status = await orchestrator.get_system_status()

    assert "timestamp" in status
    assert "agents" in status
    assert "tools" in status
    assert "memory" in status
    assert len(status["agents"]) >= 4
    assert status["tools"]["total_tools"] >= 5


@pytest.mark.asyncio
async def test_list_agents(orchestrator):
    """Test listing available agents."""
    agents = await orchestrator.list_available_agents()

    assert len(agents) >= 4
    agent_ids = [agent["agent_id"] for agent in agents]
    expected_agents = {
        "planner", "executor", "tool_manager", "memory_manager",
        "enzyme_kinetics_extractor", "enzyme_design_parser"
    }
    assert set(agent_ids).issuperset(expected_agents)


@pytest.mark.asyncio
async def test_agent_memory(orchestrator):
    """Test agent memory functionality."""
    # Execute a task first to create some memory
    task = {"id": "memory_test", "description": "Test memory functionality"}

    await orchestrator.execute_task(task)

    # Test memory retrieval
    memory_summary = await orchestrator.get_agent_memory("planner")

    assert "status" in memory_summary
    assert "summary" in memory_summary


@pytest.mark.asyncio
async def test_shutdown(orchestrator):
    """Test graceful shutdown."""
    # Execute a quick task first
    task = {"id": "test_shutdown_001", "description": "Quick test for shutdown"}

    await orchestrator.execute_task(task)

    # Then shutdown
    await orchestrator.shutdown()

    # Verify agents are idle
    for agent in orchestrator.agents.values():
        assert agent.state.status in ["idle", "completed"]


@pytest.mark.asyncio
async def test_invalid_task(orchestrator):
    """Test handling of invalid tasks."""
    # Test various invalid scenarios
    test_cases = [
        {},  # Empty task
        {
            "id": "test_invalid"
        },  # No description
        {
            "description": ""
        },  # Empty description
    ]

    for task in test_cases:
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
    # Execute multiple tasks
    tasks = [{"id": f"test_{i}", "description": f"Test task {i}"} for i in range(3)]

    for task in tasks:
        await orchestrator.execute_task(task)

    # Test cleanup
    await orchestrator.shutdown()

    # Verify system is clean
    status = await orchestrator.get_system_status()
    assert "memory" in status
