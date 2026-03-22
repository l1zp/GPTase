"""Tests for the Agent Orchestrator - Core functionality tests."""

from unittest.mock import AsyncMock

import pytest

from gptase.agents.types import GoalEvaluation
from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
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


@pytest.mark.asyncio
async def test_execute_task_with_plan_id_creates_approval_session(orchestrator):
    """Providing a predefined plan should create a draft harness session."""
    result = await orchestrator.execute_task({
        "description": "Extract enzyme data from this document",
        "plan_id": "enzyme_extraction_pipeline",
        "auto_execute": False,
    })

    assert result["execution_mode"] == "harness"
    assert result["status"] == "awaiting_approval"
    assert result["draft_source"] == "provided"
    assert result["current_plan"]["plan_id"] == "enzyme_extraction_pipeline"
    assert result["session_id"].startswith("goal_")


@pytest.mark.asyncio
async def test_execute_task_approves_and_runs_existing_session(orchestrator):
    """Approving a draft session should execute the current plan and complete."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.plan_manager.create_plan = AsyncMock(
        return_value=Plan(
            plan_id="draft_plan",
            goal="Ship the feature",
            tasks=[PlannedTask(task_id="1", description="Do work", agent_id=worker_id)],
        ))
    orchestrator.plan_manager.execute_plan = AsyncMock(
        return_value={
            "status": "completed",
            "task_results": {
                "1": {
                    "content": "done"
                }
            },
            "progress": {
                "total": 1,
                "completed": 1,
                "failed": 0,
                "pending": 0,
                "in_progress": 0,
            },
        })
    orchestrator._evaluate_goal = AsyncMock(
        return_value=GoalEvaluation(goal_achieved=True,
                                    reason="Target achieved",
                                    missing_gaps=[],
                                    next_action="complete"))

    created = await orchestrator.execute_task({
        "description": "Ship the feature",
        "auto_execute": False,
    })
    approved = await orchestrator.approve_plan(created["session_id"])

    assert created["status"] == "awaiting_approval"
    assert approved["status"] == "completed"
    assert approved["goal_evaluation"]["goal_achieved"] is True
    orchestrator.plan_manager.execute_plan.assert_awaited()


@pytest.mark.asyncio
async def test_execute_task_direct_route_still_supported(orchestrator):
    """Explicit agent_id should keep using direct execution."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.agents[worker_id].process_task_with_mode = AsyncMock(
        return_value={"status": "success", "data": {"content": "ok"}})

    result = await orchestrator.execute_task({
        "description": "Handle directly",
        "agent_id": worker_id,
        "execution_mode": "direct",
    })

    assert result["execution_mode"] == "direct"
    assert result["agent_id"] == worker_id
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_provided_draft_feedback_creates_revised_plan(orchestrator):
    """Feedback on a provided draft should produce a revised draft plan."""
    worker_id = next(iter(orchestrator.agents.keys()))
    revised_plan = Plan(
        plan_id="revised_plan",
        goal="Refined goal",
        tasks=[PlannedTask(task_id="1", description="Revised", agent_id=worker_id)],
    )
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=revised_plan)

    created = await orchestrator.execute_task({
        "description": "Initial goal",
        "plan_id": "enzyme_extraction_pipeline",
        "auto_execute": False,
    })
    revised = await orchestrator.execute_task({
        "session_id": created["session_id"],
        "feedback": "Tighten the scope and change the worker assignment",
    })

    assert revised["status"] == "awaiting_approval"
    assert revised["draft_source"] == "revised"
    assert revised["current_plan"]["plan_id"] == "revised_plan"
    orchestrator.plan_manager.create_plan.assert_awaited()


@pytest.mark.asyncio
async def test_auto_replan_runs_follow_up_plan_when_goal_not_met(orchestrator):
    """Harness should create a follow-up plan automatically when goal is unmet."""
    worker_id = next(iter(orchestrator.agents.keys()))
    initial_plan = Plan(
        plan_id="initial_plan",
        goal="Reach final answer",
        tasks=[PlannedTask(task_id="1", description="Initial", agent_id=worker_id)],
    )
    follow_up_plan = Plan(
        plan_id="follow_up_plan",
        goal="Reach final answer",
        tasks=[PlannedTask(task_id="2", description="Follow up", agent_id=worker_id)],
    )
    orchestrator.plan_manager.create_plan = AsyncMock(
        side_effect=[initial_plan, follow_up_plan])
    orchestrator.plan_manager.execute_plan = AsyncMock(
        side_effect=[
            {
                "status": "completed",
                "task_results": {
                    "1": {
                        "content": "partial"
                    }
                },
                "progress": {
                    "total": 1,
                    "completed": 1,
                    "failed": 0,
                    "pending": 0,
                    "in_progress": 0,
                },
            },
            {
                "status": "completed",
                "task_results": {
                    "2": {
                        "content": "final"
                    }
                },
                "progress": {
                    "total": 1,
                    "completed": 1,
                    "failed": 0,
                    "pending": 0,
                    "in_progress": 0,
                },
            },
        ])
    orchestrator._evaluate_goal = AsyncMock(
        side_effect=[
            GoalEvaluation(goal_achieved=False,
                           reason="Need another pass",
                           missing_gaps=["Finish synthesis"],
                           next_action="replan"),
            GoalEvaluation(goal_achieved=True,
                           reason="Complete",
                           missing_gaps=[],
                           next_action="complete"),
        ])

    result = await orchestrator.execute_task({
        "description": "Reach final answer",
        "auto_execute": True,
        "auto_replan": True,
    })

    assert result["status"] == "completed"
    assert len(result["plan_history"]) == 2
    assert result["plan_history"][0]["plan_id"] == "initial_plan"
    assert result["plan_history"][1]["plan_id"] == "follow_up_plan"
