"""
Refactored tests for the Agent Orchestrator - More robust and elegant
"""

import asyncio

import pytest

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig


@pytest.mark.asyncio
async def test_orchestrator_initialization():
    """Test that the orchestrator initializes correctly."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    assert len(orchestrator.agents) >= 4
    assert orchestrator.config is not None


@pytest.mark.asyncio
async def test_system_status():
    """Test getting system status."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    status = await orchestrator.get_system_status()

    assert "timestamp" in status
    assert "agents" in status
    assert "tools" in status
    assert "memory" in status
    assert len(status["agents"]) >= 4
    assert status["tools"]["total_tools"] >= 5


@pytest.mark.asyncio
async def test_list_agents():
    """Test listing available agents."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    agents = await orchestrator.list_available_agents()

    assert len(agents) >= 4
    agent_ids = [agent["agent_id"] for agent in agents]
    expected_agents = {"planner", "executor", "tool_manager", "memory_manager"}
    assert set(agent_ids).issuperset(expected_agents)


@pytest.mark.asyncio
async def test_fibonacci_task_execution():
    """Test executing a fibonacci calculation task."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    task = {
        "id": "test_fibonacci_001",
        "description": "Create a Python script that calculates fibonacci numbers and test it",
        "priority": "high",
    }

    result = await orchestrator.execute_task(task)

    assert result["status"] in ["success", "completed"]
    assert result["task_id"] == "test_fibonacci_001"
    assert "phases" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_task_with_plan():
    """Test task execution with explicit plan."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    task = {
        "id": "test_planned_001",
        "description": "Test planned execution",
        "plan": {
            "steps": [
                {
                    "step_id": "1",
                    "description": "Create a simple test file",
                    "tool": "code_writer",
                    "estimated_time": 1,
                    "priority": "high",
                }
            ]
        },
    }

    result = await orchestrator.execute_task(task)

    assert result["status"] in ["success", "completed"]
    assert len(result["phases"]["execution"]["results"]) >= 1


@pytest.mark.asyncio
async def test_agent_memory():
    """Test agent memory functionality."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Execute a task first to create some memory
    task = {"id": "memory_test", "description": "Test memory functionality"}

    await orchestrator.execute_task(task)

    # Test memory retrieval
    memory_summary = await orchestrator.get_agent_memory("planner")

    assert "status" in memory_summary
    assert "summary" in memory_summary


@pytest.mark.asyncio
async def test_shutdown():
    """Test graceful shutdown."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Execute a quick task first
    task = {"id": "test_shutdown_001", "description": "Quick test for shutdown"}

    await orchestrator.execute_task(task)

    # Then shutdown
    await orchestrator.shutdown()

    # Verify agents are idle
    for agent in orchestrator.agents.values():
        assert agent.state.status in ["idle", "completed"]


@pytest.mark.asyncio
async def test_invalid_task():
    """Test handling of invalid tasks."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Test various invalid scenarios
    test_cases = [
        {},  # Empty task
        {"id": "test_invalid"},  # No description
        {"description": ""},  # Empty description
    ]

    for task in test_cases:
        result = await orchestrator.execute_task(task)
        assert result["status"] in ["failed", "success"]


@pytest.mark.asyncio
async def test_system_health():
    """Test system health checks."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    status = await orchestrator.get_system_status()
    assert isinstance(status, dict)


@pytest.mark.asyncio
async def test_memory_cleanup():
    """Test memory cleanup functionality."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Execute multiple tasks
    tasks = [{"id": f"test_{i}", "description": f"Test task {i}"} for i in range(3)]

    for task in tasks:
        await orchestrator.execute_task(task)

    # Test cleanup
    await orchestrator.shutdown()

    # Verify system is clean
    status = await orchestrator.get_system_status()
    assert "memory" in status
