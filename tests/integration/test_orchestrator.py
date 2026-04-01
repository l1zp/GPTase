"""Tests for the Agent Orchestrator - Core functionality tests."""

from unittest.mock import AsyncMock

import pytest

from gptase.agents.types import GoalEvaluation
from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
from gptase.core.orchestrator import AgentOrchestrator


@pytest.fixture
async def orchestrator(framework_config):
    """Provide an AgentOrchestrator instance."""
    instance = AgentOrchestrator(framework_config)
    try:
        yield instance
    finally:
        await instance.close()


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
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Need a plan"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "needs_plan",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": {
                        "reason": "Need a DAG",
                        "goal": "Ship the feature",
                        "planning_context": "Found multiple dependent steps",
                        "evidence_summary": "Need staged execution",
                        "suggested_next_step": "Create a plan",
                    },
                }
            },
        })
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=Plan(
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
async def test_execute_task_passes_stored_input_data_to_plan_execution(orchestrator):
    """Harness sessions should retain input_data/document_path through approval."""
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
        "description": "Extract reactions",
        "plan_id": "enzyme_extraction_pipeline",
        "input_data": {
            "text": "enzyme input",
            "document_path": "/tmp/input.md",
            "custom_value": 7,
        },
        "document_path": "/tmp/input.md",
        "workspace_dir": "/tmp/workspace",
        "auto_execute": False,
    })
    approved = await orchestrator.approve_plan(created["session_id"])

    assert approved["status"] == "completed"
    orchestrator.plan_manager.execute_plan.assert_awaited_once()
    call_kwargs = orchestrator.plan_manager.execute_plan.await_args.kwargs
    assert call_kwargs["input_data"] == {
        "text": "enzyme input",
        "document_path": "/tmp/input.md",
        "custom_value": 7,
    }
    assert call_kwargs["document_path"] == "/tmp/input.md"
    assert call_kwargs["workspace_dir"] == "/tmp/workspace"


@pytest.mark.asyncio
async def test_goal_evaluation_invalid_json_uses_conservative_fallback(orchestrator):
    """Malformed evaluator output should not mark the goal as complete."""
    orchestrator.run = AsyncMock(return_value={
        "status": "success",
        "data": {
            "content": "oops"
        }
    })
    session = Plan(
        plan_id="plan",
        goal="Goal",
        tasks=[],
    )
    from gptase.agents.types import GoalSession
    harness_session = GoalSession(session_id="goal_1",
                                  goal="Reach final answer",
                                  current_plan=session)

    evaluation = await orchestrator._evaluate_goal(
        harness_session,
        {"progress": {
            "completed": 1,
            "failed": 0
        }},
    )

    assert evaluation.goal_achieved is False
    assert evaluation.next_action == "ask_user"
    assert "could not be confirmed" in evaluation.missing_gaps[0]


@pytest.mark.asyncio
async def test_execute_task_direct_route_still_supported(orchestrator):
    """Explicit agent_id should keep using direct execution."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.agents[worker_id].process_task_with_mode = AsyncMock(return_value={
        "status": "success",
        "data": {
            "content": "ok"
        }
    })

    result = await orchestrator.execute_task({
        "description": "Handle directly",
        "agent_id": worker_id,
        "execution_mode": "direct",
    })

    assert result["execution_mode"] == "direct"
    assert result["agent_id"] == worker_id
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_auto_intake_returns_direct_answer_without_creating_session(orchestrator):
    """Auto intake should return a direct answer when runtime finishes normally."""
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Direct answer"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                }
            },
        })

    result = await orchestrator.execute_task({"description": "Answer directly"})

    assert result["execution_mode"] == "auto"
    assert result["status"] == "success"
    assert result["data"]["content"] == "Direct answer"
    assert "session_id" not in result


@pytest.mark.asyncio
async def test_auto_intake_returns_coordinator_mode_when_workers_were_used(
        orchestrator):
    """Auto intake should mark coordinated answers explicitly."""
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Coordinated answer"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 2,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": {
                        "delegation_count":
                        1,
                        "delegated_agents": ["code-analyzer"],
                        "worker_results": [{
                            "agent_id": "code-analyzer",
                            "status": "success",
                            "content": "worker result",
                            "error": None,
                        }],
                    },
                }
            },
        })

    result = await orchestrator.execute_task({"description": "Answer with delegation"})

    assert result["execution_mode"] == "coordinator"
    assert result["data"]["content"] == "Coordinated answer"


@pytest.mark.asyncio
async def test_auto_intake_creates_draft_session_on_needs_plan(orchestrator):
    """Auto intake should create a draft session when runtime requests handoff."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Need a plan"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "needs_plan",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": {
                        "reason": "Need a DAG",
                        "goal": "Ship the feature",
                        "planning_context": "Found multiple dependent steps",
                        "evidence_summary": "Need staged execution",
                        "suggested_next_step": "Create a plan",
                    },
                    "coordinator": {
                        "delegation_count":
                        1,
                        "delegated_agents": ["code-analyzer"],
                        "worker_results": [{
                            "agent_id": "code-analyzer",
                            "status": "success",
                            "content": "worker result",
                            "error": None,
                        }],
                    },
                }
            },
        })
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=Plan(
        plan_id="draft_from_handoff",
        goal="Ship the feature",
        tasks=[PlannedTask(task_id="1", description="Do work", agent_id=worker_id)],
    ))

    result = await orchestrator.execute_task({
        "description": "Ship the feature",
        "auto_execute": False,
    })

    assert result["status"] == "awaiting_approval"
    assert result["draft_source"] == "runtime_handoff"
    assert result["handoff"]["reason"] == "Need a DAG"
    assert result["coordinator"]["delegated_agents"] == ["code-analyzer"]
    assert result["current_plan"]["plan_id"] == "draft_from_handoff"


@pytest.mark.asyncio
async def test_auto_intake_can_auto_execute_handoff_plan(orchestrator):
    """Auto intake should execute immediately when auto_execute is enabled."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Need a plan"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "needs_plan",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": {
                        "reason": "Need a DAG",
                        "goal": "Ship the feature",
                        "planning_context": "Found multiple dependent steps",
                        "evidence_summary": "Need staged execution",
                        "suggested_next_step": "Create a plan",
                    },
                }
            },
        })
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=Plan(
        plan_id="draft_from_handoff",
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

    result = await orchestrator.execute_task({
        "description": "Ship the feature",
        "auto_execute": True,
    })

    assert result["status"] == "completed"
    assert result["draft_source"] == "runtime_handoff"
    assert result["goal_evaluation"]["goal_achieved"] is True


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
        "session_id":
        created["session_id"],
        "feedback":
        "Tighten the scope and change the worker assignment",
    })

    assert revised["status"] == "awaiting_approval"
    assert revised["draft_source"] == "revised"
    assert revised["current_plan"]["plan_id"] == "revised_plan"
    orchestrator.plan_manager.create_plan.assert_awaited()


@pytest.mark.asyncio
async def test_auto_replan_runs_follow_up_plan_when_goal_not_met(orchestrator):
    """Harness should create a follow-up plan automatically when goal is unmet."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Need a plan"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "needs_plan",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": {
                        "reason": "Need a DAG",
                        "goal": "Reach final answer",
                        "planning_context": "Found multiple dependent steps",
                        "evidence_summary": "Need staged execution",
                        "suggested_next_step": "Create a plan",
                    },
                }
            },
        })
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
    orchestrator.plan_manager.execute_plan = AsyncMock(side_effect=[
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
    orchestrator._evaluate_goal = AsyncMock(side_effect=[
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


async def test_session_status_exposes_active_tasks_and_runtime_detail(orchestrator):
    """Runtime status should expose concurrent active tasks and detailed progress."""
    session = await orchestrator.execute_task({
        "description": "Inspect runtime status",
        "plan_id": "enzyme_extraction_pipeline",
        "auto_execute": False,
    })
    orchestrator.plan_manager.get_session_status = AsyncMock(
        return_value={
            "active_tasks": {
                "1": {
                    "task_id": "1",
                    "agent_id": "worker-a",
                    "started_at": "2026-03-31T12:00:00",
                },
                "2": {
                    "task_id": "2",
                    "agent_id": "worker-b",
                    "started_at": "2026-03-31T12:00:01",
                },
            },
            "active_agent_ids": ["worker-a", "worker-b"],
            "completed_steps": 1,
            "failed_steps": 0,
            "pending_steps": 2,
            "in_progress_steps": 2,
            "total_steps": 5,
            "progress": 20.0,
            "step_results": {
                "3": {
                    "result": {
                        "error": "downstream failure"
                    }
                }
            },
        })

    status = await orchestrator.get_session_status(session["session_id"])

    assert status["active_tasks"]["2"]["agent_id"] == "worker-b"
    assert status["latest_error"] == {"task_id": "3", "error": "downstream failure"}
    assert status["runtime_progress_detail"] == {
        "completed_steps": 1,
        "progress_percent": 20.0,
        "total_steps": 5,
        "failed_steps": 0,
        "pending_steps": 2,
        "in_progress_steps": 2,
        "active_tasks": {
            "1": {
                "task_id": "1",
                "agent_id": "worker-a",
                "started_at": "2026-03-31T12:00:00",
            },
            "2": {
                "task_id": "2",
                "agent_id": "worker-b",
                "started_at": "2026-03-31T12:00:01",
            },
        },
        "active_agent_ids": ["worker-a", "worker-b"],
    }


async def test_created_session_includes_preflight_warnings(orchestrator):
    """Draft sessions should include a lightweight preflight summary."""
    result = await orchestrator.execute_task({
        "description": "Review draft",
        "plan": {
            "plan_id":
            "draft_plan",
            "goal":
            "Review draft",
            "tasks": [{
                "task_id": "1",
                "description": "Run a shell command",
                "tools": ["Bash"],
            }]
        },
        "auto_execute": False,
    })

    assert result["preflight"]["status"] == "warning"
    assert any("Bash-capable execution" in warning
               for warning in result["preflight"]["warnings"])
