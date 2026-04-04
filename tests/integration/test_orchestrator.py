"""Tests for the Agent Orchestrator - Core functionality tests."""

from unittest.mock import AsyncMock

import pytest

from gptase.agents.types import GoalEvaluation
from gptase.agents.types import Plan
from gptase.agents.types import Task
from gptase.core.orchestrator import AgentOrchestrator
from gptase.core.types import DispatchRequest


@pytest.fixture
async def orchestrator(framework_config, tmp_path):
    """Provide an AgentOrchestrator instance."""
    framework_config.memory.db_path = str(tmp_path / "orchestrator_test.db")
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
    assert orchestrator.agent_id == "orchestrator"
    assert "orchestrator" not in orchestrator.agents


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
    invalid_tasks = [
        DispatchRequest(),
        DispatchRequest(id="test_invalid"),
        DispatchRequest(description=""),
    ]

    for request in invalid_tasks:
        result = await orchestrator.dispatch(request)
        assert result["status"] in ["failed", "success"]


@pytest.mark.asyncio
async def test_system_health(orchestrator):
    """Test system health checks."""
    status = await orchestrator.get_system_status()
    assert isinstance(status, dict)


@pytest.mark.asyncio
async def test_dispatch_with_plan_id_creates_approval_session(orchestrator):
    """Providing a predefined plan should return a draft plan response."""
    result = await orchestrator.dispatch(
        DispatchRequest(
            description="Extract enzyme data from this document",
            plan_id="enzyme_extraction_pipeline",
            auto_execute=False,
        ))

    assert result["status"] == "draft"
    assert result["current_plan"]["plan_id"] == "enzyme_extraction_pipeline"


@pytest.mark.asyncio
async def test_execute_plan_with_auto_execute_false_returns_draft(orchestrator):
    """With auto_execute=False, _execute_plan returns draft without executing."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=Plan(
        plan_id="draft_plan",
        goal="Ship the feature",
        tasks=[Task(task_id="1", description="Do work", agent_id=worker_id)],
    ))
    orchestrator.plan_manager.execute_plan = AsyncMock()

    result = await orchestrator._execute_plan(
        task_id="test_123",
        request=DispatchRequest(description="Ship the feature", auto_execute=False),
    )

    assert result["status"] == "draft"
    assert result["current_plan"]["plan_id"] == "draft_plan"
    orchestrator.plan_manager.execute_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_plan_passes_input_data_to_execution(orchestrator):
    """_execute_plan should pass input_data/document_path/workspace_dir to plan execution."""
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

    result = await orchestrator._execute_plan(
        task_id="test_456",
        request=DispatchRequest(
            description="Extract reactions",
            plan_id="enzyme_extraction_pipeline",
            input_data={
                "text": "enzyme input",
                "document_path": "/tmp/input.md",
                "custom_value": 7,
            },
            document_path="/tmp/input.md",
            workspace_dir="/tmp/workspace",
            auto_execute=True,
        ),
    )

    assert result["status"] == "completed"
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
    harness_plan = Plan(plan_id="goal_1", goal="Reach final answer")

    evaluation = await orchestrator._evaluate_goal(
        harness_plan.goal,
        harness_plan,
        {"progress": {
            "completed": 1,
            "failed": 0
        }},
    )

    assert evaluation.goal_achieved is False
    assert evaluation.next_action == "ask_user"
    assert "could not be confirmed" in evaluation.missing_gaps[0]


@pytest.mark.asyncio
async def test_dispatch_direct_route_still_supported(orchestrator):
    """Explicit agent_id should keep using direct execution."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.agents[worker_id].process_task = AsyncMock(return_value={
        "status": "success",
        "data": {
            "content": "ok"
        }
    })

    result = await orchestrator.dispatch(
        DispatchRequest(
            description="Handle directly",
            agent_id=worker_id,
            execution_mode="direct",
        ))

    assert result["execution_mode"] == "direct"
    assert result["agent_id"] == worker_id
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_coordinator_returns_direct_answer_without_creating_session(orchestrator):
    """Coordinator should return a direct answer when runtime finishes normally."""
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

    result = await orchestrator.dispatch(DispatchRequest(description="Answer directly"))

    assert result["execution_mode"] == "coordinator"
    assert result["status"] == "success"
    assert result["data"]["content"] == "Direct answer"
    assert "session_id" not in result


@pytest.mark.asyncio
async def test_coordinator_keeps_looping_when_workers_were_used(orchestrator):
    """Coordinator should keep coordinating until it can answer directly."""
    orchestrator.run = AsyncMock(side_effect=[
        {
            "status": "success",
            "data": {
                "content": "Delegating first"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": {
                        "turn_count":
                        1,
                        "delegation_count":
                        1,
                        "delegated_agents": ["code-analyzer"],
                        "worker_results": [{
                            "agent_id": "code-analyzer",
                            "status": "success",
                            "content": "worker result",
                            "error": None,
                        }],
                        "turns": [{
                            "turn_index":
                            1,
                            "delegation_count":
                            1,
                            "delegated_agents": ["code-analyzer"],
                            "worker_results": [{
                                "agent_id": "code-analyzer",
                                "status": "success",
                                "content": "worker result",
                                "error": None,
                            }],
                            "assistant_content":
                            "Delegating first",
                            "stop_reason":
                            None,
                        }],
                    },
                }
            },
        },
        {
            "status": "success",
            "data": {
                "content": "Coordinated answer"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": None,
                }
            },
        },
    ])

    result = await orchestrator.dispatch(
        DispatchRequest(description="Answer with delegation"))

    assert result["execution_mode"] == "coordinator"
    assert result["data"]["content"] == "Coordinated answer"
    assert result["trace"]["runtime"]["coordinator"]["turn_count"] == 1


@pytest.mark.asyncio
async def test_auto_intake_continues_coordinator_loop_across_multiple_delegations(
        orchestrator):
    """Auto intake should continue if a coordinator follow-up delegates again."""
    orchestrator.run = AsyncMock(side_effect=[
        {
            "status": "success",
            "data": {
                "content": "Delegating first"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": {
                        "turn_count":
                        1,
                        "delegation_count":
                        1,
                        "delegated_agents": ["code-analyzer"],
                        "worker_results": [{
                            "agent_id": "code-analyzer",
                            "status": "success",
                            "content": "first result",
                            "error": None,
                        }],
                        "turns": [{
                            "turn_index":
                            1,
                            "delegation_count":
                            1,
                            "delegated_agents": ["code-analyzer"],
                            "worker_results": [{
                                "agent_id": "code-analyzer",
                                "status": "success",
                                "content": "first result",
                                "error": None,
                            }],
                            "assistant_content":
                            "Delegating first",
                            "stop_reason":
                            None,
                        }],
                    },
                }
            },
        },
        {
            "status": "success",
            "data": {
                "content": "Delegating second"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": {
                        "turn_count":
                        1,
                        "delegation_count":
                        1,
                        "delegated_agents": ["document-structure-analyzer"],
                        "worker_results": [{
                            "agent_id": "document-structure-analyzer",
                            "status": "success",
                            "content": "second result",
                            "error": None,
                        }],
                        "turns": [{
                            "turn_index":
                            1,
                            "delegation_count":
                            1,
                            "delegated_agents": ["document-structure-analyzer"],
                            "worker_results": [{
                                "agent_id": "document-structure-analyzer",
                                "status": "success",
                                "content": "second result",
                                "error": None,
                            }],
                            "assistant_content":
                            "Delegating second",
                            "stop_reason":
                            None,
                        }],
                    },
                }
            },
        },
        {
            "status": "success",
            "data": {
                "content": "Final coordinated answer"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": None,
                }
            },
        },
    ])

    result = await orchestrator.dispatch(DispatchRequest(description="Coordinate twice")
                                         )

    assert result["execution_mode"] == "coordinator"
    assert result["data"]["content"] == "Final coordinated answer"
    assert result["trace"]["runtime"]["coordinator"]["turn_count"] == 2
    assert result["trace"]["runtime"]["coordinator"]["delegated_agents"] == [
        "code-analyzer",
        "document-structure-analyzer",
    ]


@pytest.mark.asyncio
async def test_auto_intake_returns_controlled_error_when_coordinator_loop_exceeds_limit(
        orchestrator):
    """Auto intake should fail safely when every coordinator turn keeps delegating."""
    coordinator_trace = {
        "turn_count":
        1,
        "delegation_count":
        1,
        "delegated_agents": ["code-analyzer"],
        "worker_results": [{
            "agent_id": "code-analyzer",
            "status": "success",
            "content": "worker result",
            "error": None,
        }],
        "turns": [{
            "turn_index":
            1,
            "delegation_count":
            1,
            "delegated_agents": ["code-analyzer"],
            "worker_results": [{
                "agent_id": "code-analyzer",
                "status": "success",
                "content": "worker result",
                "error": None,
            }],
            "assistant_content":
            "Delegating",
            "stop_reason":
            None,
        }],
    }
    orchestrator.run = AsyncMock(side_effect=[{
        "status": "success",
        "data": {
            "content": f"delegation {index}"
        },
        "trace": {
            "runtime": {
                "stop_reason": "final_answer",
                "turn_count": 1,
                "turns": [],
                "resume_supported": True,
                "plan_handoff": None,
                "coordinator": coordinator_trace,
            }
        },
    } for index in range(3)])

    result = await orchestrator.dispatch(
        DispatchRequest(description="Keep coordinating"))

    assert result["status"] == "failed"
    assert result["execution_mode"] == "coordinator"
    assert "maximum number of orchestration turns" in result["error"]
    assert "session_id" not in result


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
        tasks=[Task(task_id="1", description="Do work", agent_id=worker_id)],
    ))

    result = await orchestrator.dispatch(
        DispatchRequest(description="Ship the feature", auto_execute=False))

    assert result["status"] == "draft"
    assert result["current_plan"]["plan_id"] == "draft_from_handoff"
    orchestrator.plan_manager.create_plan.assert_awaited()


@pytest.mark.asyncio
async def test_auto_intake_can_handoff_from_inside_coordinator_loop(orchestrator):
    """Coordinator loop should hand off into a draft plan when a later turn requests it."""
    worker_id = next(iter(orchestrator.agents.keys()))
    orchestrator.run = AsyncMock(side_effect=[
        {
            "status": "success",
            "data": {
                "content": "Delegating first"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "plan_handoff": None,
                    "coordinator": {
                        "turn_count":
                        1,
                        "delegation_count":
                        1,
                        "delegated_agents": ["code-analyzer"],
                        "worker_results": [{
                            "agent_id": "code-analyzer",
                            "status": "success",
                            "content": "worker result",
                            "error": None,
                        }],
                        "turns": [{
                            "turn_index":
                            1,
                            "delegation_count":
                            1,
                            "delegated_agents": ["code-analyzer"],
                            "worker_results": [{
                                "agent_id": "code-analyzer",
                                "status": "success",
                                "content": "worker result",
                                "error": None,
                            }],
                            "assistant_content":
                            "Delegating first",
                            "stop_reason":
                            None,
                        }],
                    },
                }
            },
        },
        {
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
                        "turn_count":
                        1,
                        "delegation_count":
                        1,
                        "delegated_agents": ["document-structure-analyzer"],
                        "worker_results": [{
                            "agent_id": "document-structure-analyzer",
                            "status": "success",
                            "content": "second result",
                            "error": None,
                        }],
                        "turns": [{
                            "turn_index":
                            1,
                            "delegation_count":
                            1,
                            "delegated_agents": ["document-structure-analyzer"],
                            "worker_results": [{
                                "agent_id": "document-structure-analyzer",
                                "status": "success",
                                "content": "second result",
                                "error": None,
                            }],
                            "assistant_content":
                            "Need a plan",
                            "stop_reason":
                            "needs_plan",
                        }],
                    },
                }
            },
        },
    ])
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=Plan(
        plan_id="draft_from_handoff",
        goal="Ship the feature",
        tasks=[Task(task_id="1", description="Do work", agent_id=worker_id)],
    ))

    result = await orchestrator.dispatch(
        DispatchRequest(description="Ship the feature", auto_execute=False))

    assert result["status"] == "draft"
    assert result["current_plan"]["plan_id"] == "draft_from_handoff"
    # Two coordinator turns happened before handoff (run called twice)
    assert orchestrator.run.await_count == 2


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
        tasks=[Task(task_id="1", description="Do work", agent_id=worker_id)],
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

    result = await orchestrator.dispatch(
        DispatchRequest(description="Ship the feature", auto_execute=True))

    assert result["status"] == "completed"
    assert result["goal_evaluation"]["goal_achieved"] is True
    orchestrator.plan_manager.create_plan.assert_awaited()
    orchestrator.plan_manager.execute_plan.assert_awaited()


@pytest.mark.asyncio
async def test_execute_plan_with_planning_context_creates_plan(orchestrator):
    """Providing planning_context should produce a plan incorporating feedback."""
    worker_id = next(iter(orchestrator.agents.keys()))
    revised_plan = Plan(
        plan_id="revised_plan",
        goal="Refined goal",
        tasks=[Task(task_id="1", description="Revised", agent_id=worker_id)],
    )
    orchestrator.plan_manager.create_plan = AsyncMock(return_value=revised_plan)

    result = await orchestrator._execute_plan(
        task_id="test_replan",
        request=DispatchRequest(
            description="Initial goal",
            planning_context="Tighten the scope and change the worker assignment",
            auto_execute=False,
        ),
    )

    assert result["status"] == "draft"
    assert result["current_plan"]["plan_id"] == "revised_plan"
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
        tasks=[Task(task_id="1", description="Initial", agent_id=worker_id)],
    )
    follow_up_plan = Plan(
        plan_id="follow_up_plan",
        goal="Reach final answer",
        tasks=[Task(task_id="2", description="Follow up", agent_id=worker_id)],
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

    result = await orchestrator.dispatch(
        DispatchRequest(
            description="Reach final answer",
            auto_execute=True,
            auto_replan=True,
        ))

    assert result["status"] == "completed"
    assert len(result["plan_history"]) == 2
    assert result["plan_history"][0]["plan_id"] == "initial_plan"
    assert result["plan_history"][1]["plan_id"] == "follow_up_plan"


async def test_get_session_status_returns_none_for_plan_session_ids(orchestrator):
    """Plan sessions are no longer persisted; get_session_status returns None."""
    status = await orchestrator.get_session_status("plan_20260331_120000_abc12345")
    assert status is None


async def test_created_session_includes_preflight_warnings(orchestrator):
    """Draft sessions should include a lightweight preflight summary."""
    result = await orchestrator.dispatch(
        DispatchRequest(
            description="Review draft",
            plan={
                "plan_id":
                "draft_plan",
                "goal":
                "Review draft",
                "tasks": [{
                    "task_id": "1",
                    "description": "Run a shell command",
                    "tools": ["Bash"],
                }],
            },
            auto_execute=False,
        ))

    assert result["preflight"]["status"] == "warning"
    assert any("Bash-capable execution" in warning
               for warning in result["preflight"]["warnings"])
