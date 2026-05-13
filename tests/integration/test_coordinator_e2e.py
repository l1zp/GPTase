"""Integration test: DelegateTask actually routes through the orchestrator.

Unit tests cover the orchestrator's dispatch state machine and the
DelegateTask tool's logic separately. The wiring between them — that
``AgentOrchestrator.__init__`` sets ``delegate_tool.orchestrator = self``
and the tool then routes ``agent_id`` through ``orchestrator.agents[id]``
to the worker's ``process_task`` — is the integration point that no
unit test directly exercises.

This single test pins that path end-to-end:

    LLM tool_call(DelegateTask, agent_id=W, ...)
        -> DelegateTaskTool.execute(...)
            -> self.orchestrator.agents[W].process_task(Task(...))

with all five components real (orchestrator, agent registry, tool
registry, DelegateTask, Task), and only the worker's actual LLM call
mocked.
"""
import json
from unittest.mock import AsyncMock

import pytest

from gptase.core.orchestrator import AgentOrchestrator
from gptase.tools.base import get_tool_registry


@pytest.fixture
async def real_orchestrator(framework_config, tmp_path):
    """Real orchestrator under tmp_path-isolated sqlite. Agent registry
    populated from the live ``.claude/agents/`` tree.

    Resets the global DelegateTask tool's per-dispatch state because
    other tests may have left a stale ``workspace_dir`` set, which
    would push us onto the artifact-mode response branch.
    """
    framework_config.memory.db_path = str(tmp_path / "integration.db")
    instance = AgentOrchestrator(framework_config)
    tool = get_tool_registry().get("DelegateTask")
    if tool is not None:
        tool.workspace_dir = None
        tool._artifact_counter = 0
    try:
        yield instance
    finally:
        await instance.close()


def _pick_worker(orch: AgentOrchestrator) -> str:
    """Pick any registered agent for delegation tests, or skip."""
    if not orch.agents:
        pytest.skip("No agents discovered in this environment")
    return next(iter(orch.agents))


class TestDelegateTaskWiring:
    """End-to-end: tool registry -> orchestrator.agents[id] -> worker."""

    async def test_delegate_routes_through_orchestrator_to_worker(
            self, real_orchestrator):
        # Wiring assertion 1: __init__ should have bound the global
        # DelegateTask tool to this orchestrator.
        tool = get_tool_registry().get("DelegateTask")
        assert tool is not None, "DelegateTask must be registered globally"
        assert tool.orchestrator is real_orchestrator, (
            "AgentOrchestrator.__init__ must bind delegate_tool.orchestrator")

        worker_id = _pick_worker(real_orchestrator)

        # Mock the worker's actual execution so we don't hit a real LLM.
        real_orchestrator.agents[worker_id].process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": "synthesized worker output"
            },
        })

        # Drive the tool the same way the LLM would.
        result_json = await tool.execute(
            agent_id=worker_id,
            task_description="please synthesize",
        )

        # Wiring assertion 2: the worker actually got called via the tool.
        real_orchestrator.agents[worker_id].process_task.assert_awaited_once()

        # Wiring assertion 3: the worker's content threaded back into the
        # tool's JSON response.
        parsed = json.loads(result_json)
        assert parsed.get("status") == "success"
        # The tool surfaces the worker's content under one of two keys
        # depending on whether workspace_dir was set (artifact mode,
        # ``content_preview``) or not (inline mode, ``content``).
        content = parsed.get("content") or parsed.get("content_preview") or ""
        assert "synthesized worker output" in content

    async def test_workspace_dir_flips_response_into_artifact_mode(
            self, real_orchestrator, tmp_path):
        # Slice 1.18 contract: when dispatch carries a workspace_dir,
        # the global DelegateTask tool persists full worker payloads to
        # disk and returns only a compact reference (output_path +
        # content_preview). This keeps the Coordinator's context O(1)
        # across long fan-in pipelines instead of inlining megabytes
        # of worker output into every followup prompt.
        from gptase.core.types import DispatchRequest

        tool = get_tool_registry().get("DelegateTask")
        worker_id = _pick_worker(real_orchestrator)

        long_content = "long worker output line\n" * 100
        real_orchestrator.agents[worker_id].process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": long_content
            }
        })

        # Drive dispatch (which is what rebinds workspace_dir on the tool)
        # but stub the LLM loop so we don't need to script tool_calls.
        real_orchestrator.run = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "content": "synthesized"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "final_answer"
                    }
                },
            })

        workspace = tmp_path / "ws"
        await real_orchestrator.dispatch(
            DispatchRequest(query="anything", workspace_dir=str(workspace)))

        # dispatch() must have rebound workspace + zeroed the counter.
        assert tool.workspace_dir == str(workspace)
        assert tool._artifact_counter == 0

        # Now invoke the tool directly to verify the artifact-mode shape.
        result_json = await tool.execute(
            agent_id=worker_id,
            task_description="produce a long report",
        )

        parsed = json.loads(result_json)
        # Artifact-mode response shape — NOT the inline content field.
        assert "output_path" in parsed
        assert "content_preview" in parsed
        assert parsed["content_chars"] > 1500  # exceeded preview limit
        # Full payload landed on disk under worker_results/.
        artifact = workspace / "worker_results" / f"001_{worker_id}.json"
        assert artifact.exists()
        on_disk = json.loads(artifact.read_text(encoding="utf-8"))
        assert "long worker output line" in on_disk["content"]

    async def test_delegate_to_unknown_agent_returns_failure_response(
            self, real_orchestrator):
        # The tool should NOT crash — it returns a structured failure
        # JSON with a list of available agents so the LLM can self-correct.
        tool = get_tool_registry().get("DelegateTask")

        result_json = await tool.execute(
            agent_id="agent-that-does-not-exist",
            task_description="anything",
        )

        parsed = json.loads(result_json)
        assert parsed.get("status") in ("failed", "error")
        # The error message names the bad id and lists alternatives.
        error = (parsed.get("error") or "")
        assert "agent-that-does-not-exist" in error
        assert "Available agents" in error
