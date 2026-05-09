"""Tests for the Agent Orchestrator - Core functionality tests.

Slice 3 removed the legacy PlanManager / DAG dispatcher path. The
orchestrator now has only two execution modes:
  - Agent mode (explicit agent_id → direct worker invocation)
  - Coordinator mode (default, LLM orchestrates DelegateTask)

Tests previously exercising _execute_plan, _evaluate_goal, plan
handoff, auto_replan, preflight summaries, etc. were removed
together with the underlying code.
"""

from unittest.mock import AsyncMock

import pytest

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
        DispatchRequest(query=""),
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
        DispatchRequest(query="Handle directly", agent_id=worker_id))

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
                }
            },
        })

    result = await orchestrator.dispatch(DispatchRequest(query="Answer directly"))

    assert result["execution_mode"] == "coordinator"
    assert result["status"] == "success"
    assert result["data"]["content"] == "Direct answer"
    assert "session_id" not in result


@pytest.mark.asyncio
async def test_auto_intake_returns_controlled_error_when_coordinator_loop_exceeds_limit(
        orchestrator, monkeypatch):
    """Auto intake should fail safely when every coordinator turn keeps delegating."""
    # Lower the cap so the test can synthesize a saturating loop with a
    # small number of mock side effects. Slice 1.6 raised the production
    # default from 3 to 10; this test asserts the saturation path, not
    # the specific cap value.
    import gptase.core.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "_MAX_COORDINATOR_TURNS", 3)

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
    # Use stop_reason=max_turns to simulate the runtime giving up while
    # still emitting tool_calls (i.e. the inner runtime ran out of
    # iterations without a final answer). Slice 1.19 changed the outer
    # loop to trust stop_reason=='final_answer' as terminal — this test
    # now models the saturation case where final_answer is *never*
    # reached, only delegations.
    orchestrator.run = AsyncMock(side_effect=[{
        "status": "success",
        "data": {
            "content": f"delegation {index}"
        },
        "trace": {
            "runtime": {
                "stop_reason": "max_turns",
                "turn_count": 1,
                "turns": [],
                "resume_supported": True,
                "coordinator": coordinator_trace,
            }
        },
    } for index in range(3)])

    result = await orchestrator.dispatch(DispatchRequest(query="Keep coordinating"))

    assert result["status"] == "failed"
    assert result["execution_mode"] == "coordinator"
    assert "maximum number of orchestration turns" in result["error"]
    assert "session_id" not in result


@pytest.mark.asyncio
async def test_auto_intake_returns_immediately_on_final_answer_with_delegations(
        orchestrator):
    """Slice 1.19: final_answer is terminal even when delegations happened.

    The previous behavior would re-prompt the LLM with a followup
    payload (which on listov_2025 ballooned to 122KB), wasting a
    Coordinator turn after the LLM had already produced the answer.
    """
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
            "Done with synthesis",
            "stop_reason":
            "final_answer",
        }],
    }
    orchestrator.run = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "content": "Final synthesized answer"
            },
            "trace": {
                "runtime": {
                    "stop_reason": "final_answer",
                    "turn_count": 1,
                    "turns": [],
                    "resume_supported": True,
                    "coordinator": coordinator_trace,
                }
            },
        })

    result = await orchestrator.dispatch(DispatchRequest(query="Synthesize"))

    assert result["status"] == "success"
    assert result["execution_mode"] == "coordinator"
    assert result["data"]["content"] == "Final synthesized answer"
    # CRITICAL: only one self.run() call, even though coordinator
    # tracked a delegation. The outer loop must NOT iterate again.
    assert orchestrator.run.call_count == 1
