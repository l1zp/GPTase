"""Unit tests for gptase.core.orchestrator.AgentOrchestrator.

Two test layers:

* ``TestPureHelpers`` — pure data helpers exercised against an instance
  built via ``__new__`` so we skip the heavy ``__init__`` (which would
  scan ``.claude/agents/``, build a real ``Model``, and open a sqlite
  ``MemoryManager``). Cheap, deterministic, isolates the math.

* ``TestDispatchRouting`` / ``TestCoordinatorLoop`` — real
  ``__init__`` under a ``tmp_path``-isolated sqlite memory dir, with
  individual code paths driven by ``AsyncMock`` patches on
  ``orchestrator.run`` and ``orchestrator.agents[*].process_task``.
  These pay the agent-discovery cost once per test but are the only
  way to cover the dispatch/coordinator state machine end-to-end.
"""
from unittest.mock import AsyncMock

import pytest

from gptase.core.orchestrator import AgentOrchestrator
from gptase.core.types import DispatchRequest


@pytest.fixture
async def orchestrator(framework_config, tmp_path):
    """Real orchestrator with tmp sqlite; closes cleanly after the test."""
    framework_config.memory.db_path = str(tmp_path / "orchestrator.db")
    instance = AgentOrchestrator(framework_config)
    try:
        yield instance
    finally:
        await instance.close()


def _bare_orchestrator() -> AgentOrchestrator:
    """Build an orchestrator without firing ``__init__``.

    Pure-helper tests don't need agents, model_manager, or sqlite —
    only the methods themselves and a few scalar attributes.
    """
    instance = AgentOrchestrator.__new__(AgentOrchestrator)
    instance.agents = {}
    instance.agent_id = "orchestrator"
    return instance


class TestPureHelpers:
    """Pure data helpers — no async, no I/O, no ``__init__``."""

    def test_summarize_text_short_long_empty(self):
        bare = _bare_orchestrator()

        # Empty / whitespace falls back to the unnamed-session sentinel.
        assert bare._summarize_text("") == "Untitled Session"
        assert bare._summarize_text("   \t\n  ") == "Untitled Session"

        # Short text passes through unchanged.
        assert bare._summarize_text("hi") == "hi"

        # Long text is truncated to 30 chars + "...".
        long = "x" * 100
        out = bare._summarize_text(long)
        assert out.endswith("...")
        assert len(out) == 33  # 30 chars + "..."

    def test_resolve_agent_id_dash_underscore_unknown(self):
        bare = _bare_orchestrator()
        bare.agents = {"enzyme-kinetics-extractor": object()}

        # Exact match wins.
        assert bare._resolve_agent_id(
            "enzyme-kinetics-extractor") == "enzyme-kinetics-extractor"
        # Underscore form is rewritten to dash form.
        assert bare._resolve_agent_id(
            "enzyme_kinetics_extractor") == "enzyme-kinetics-extractor"
        # The orchestrator's own id passes through.
        assert bare._resolve_agent_id("orchestrator") == "orchestrator"
        # Unknown returns None.
        assert bare._resolve_agent_id("does-not-exist") is None
        # Falsy input short-circuits.
        assert bare._resolve_agent_id(None) is None
        assert bare._resolve_agent_id("") is None

    def test_error_result_shape(self):
        bare = _bare_orchestrator()

        result = bare._error_result("task-42", "boom")

        assert result["task_id"] == "task-42"
        assert result["status"] == "failed"
        assert result["error"] == "boom"
        assert "timestamp" in result

    def test_normalize_coordinator_summary_none_and_paths(self):
        bare = _bare_orchestrator()

        # Non-dict input is rejected.
        assert bare._normalize_coordinator_summary(None) is None
        assert bare._normalize_coordinator_summary("not a dict") is None
        assert bare._normalize_coordinator_summary({}) is None

        # Path A: explicit turns list.
        summary = {
            "turns": [{
                "turn_index": 1,
                "delegation_count": 2,
                "delegated_agents": ["a", "b"],
                "worker_results": [{
                    "agent_id": "a",
                    "status": "success"
                }],
                "assistant_content": "...",
                "stop_reason": "tool_calls",
            }],
        }
        normalized = bare._normalize_coordinator_summary(summary)
        assert normalized["turn_count"] == 1
        assert normalized["delegation_count"] == 2
        assert normalized["delegated_agents"] == ["a", "b"]
        assert len(normalized["worker_results"]) == 1

        # Path B: flat worker_results without turns -> synthesize one turn.
        flat = {
            "delegated_agents": ["x"],
            "worker_results": [{
                "agent_id": "x",
                "status": "success"
            }],
            "stop_reason": "max_turns",
        }
        synth = bare._normalize_coordinator_summary(flat)
        assert synth["turn_count"] == 1
        assert synth["turns"][0]["delegated_agents"] == ["x"]

        # Path C: neither turns nor worker_results -> None.
        empty = {"delegated_agents": []}
        assert bare._normalize_coordinator_summary(empty) is None

    def test_merge_coordinator_summaries_concat_and_dedup(self):
        bare = _bare_orchestrator()

        s1 = {
            "turn_count":
            1,
            "delegation_count":
            1,
            "delegated_agents": ["a"],
            "worker_results": [{
                "agent_id": "a"
            }],
            "turns": [{
                "turn_index": 1,
                "delegation_count": 1,
                "delegated_agents": ["a"],
                "worker_results": [{
                    "agent_id": "a"
                }],
            }],
        }
        s2 = {
            "turn_count":
            1,
            "delegation_count":
            2,
            "delegated_agents": ["b", "a"],  # 'a' already present in s1
            "worker_results": [{
                "agent_id": "b"
            }, {
                "agent_id": "a"
            }],
            "turns": [{
                "turn_index": 1,
                "delegation_count": 2,
                "delegated_agents": ["b", "a"],
                "worker_results": [{
                    "agent_id": "b"
                }, {
                    "agent_id": "a"
                }],
            }],
        }

        # None passthroughs.
        assert bare._merge_coordinator_summaries(None, s1) == s1
        assert bare._merge_coordinator_summaries(s1, None) == s1

        merged = bare._merge_coordinator_summaries(s1, s2)
        assert merged["turn_count"] == 2  # turns concatenated
        # Agents deduped while preserving order.
        assert merged["delegated_agents"] == ["a", "b"]
        # Worker results concatenated, not deduped.
        assert len(merged["worker_results"]) == 3

    def test_with_coordinator_trace_passthrough_and_injection(self):
        bare = _bare_orchestrator()

        # No trace -> None.
        assert bare._with_coordinator_trace(None, {"x": 1}) is None
        # No summary -> trace returned unchanged.
        trace = {"runtime": {"stop_reason": "final_answer"}}
        assert bare._with_coordinator_trace(trace, None) == trace
        # Both -> coordinator summary merged into trace.runtime.
        summary = {"turn_count": 2}
        out = bare._with_coordinator_trace(trace, summary)
        assert out["runtime"]["coordinator"] == summary
        assert out["runtime"]["stop_reason"] == "final_answer"

    def test_build_coordinator_followup_prompt_embeds_payload(self):
        bare = _bare_orchestrator()

        coord_summary = {
            "turns": [{
                "turn_index": 1,
                "delegation_count": 1,
                "delegated_agents": ["w1"],
                "worker_results": [{
                    "agent_id": "w1",
                    "status": "success"
                }],
                "assistant_content": "Picked w1",
                "stop_reason": "tool_calls",
            }],
        }
        runtime = {"stop_reason": "tool_calls"}

        prompt = bare._build_coordinator_followup_prompt("Reach the goal",
                                                         coord_summary, runtime)

        assert "Continue coordinating this task" in prompt
        # The full payload is JSON-embedded so the LLM can self-inspect.
        assert "Reach the goal" in prompt
        assert "w1" in prompt
        assert "Picked w1" in prompt


class TestDispatchRouting:
    """Top-level ``dispatch`` routing — agent vs coordinator vs error."""

    async def test_empty_query_returns_failed(self, orchestrator):
        # Coordinator path requires a query — empty -> controlled failure.
        result = await orchestrator.dispatch(DispatchRequest(query=""))

        assert result["status"] == "failed"
        assert "Task description is required" in result["error"]

    async def test_direct_route_with_explicit_agent_id(self, orchestrator):
        # Pick any discovered agent and stub its process_task.
        if not orchestrator.agents:
            pytest.skip("No agents discovered in this environment")
        worker_id = next(iter(orchestrator.agents))
        orchestrator.agents[worker_id].process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": "ok"
            }
        })

        result = await orchestrator.dispatch(
            DispatchRequest(query="Run me", agent_id=worker_id))

        assert result["execution_mode"] == "direct"
        assert result["agent_id"] == worker_id
        assert result["status"] == "success"

    async def test_unknown_agent_id_falls_through_to_coordinator(self, orchestrator):
        # _resolve_agent_id returns None for unknown ids, so dispatch
        # falls through to the coordinator path. With self.run mocked
        # to a final_answer, the result lands as a coordinator success.
        orchestrator.run = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "content": "answered"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "final_answer"
                    }
                },
            })

        result = await orchestrator.dispatch(
            DispatchRequest(query="hi", agent_id="does-not-exist"))

        assert result["execution_mode"] == "coordinator"
        assert result["status"] == "success"

    async def test_exception_caught_as_failed(self, orchestrator):
        # Make the inner loop blow up — dispatch's try/except should
        # convert it into a structured failed result.
        orchestrator.run = AsyncMock(side_effect=RuntimeError("kaboom"))

        result = await orchestrator.dispatch(DispatchRequest(query="trigger"))

        assert result["status"] == "failed"
        assert "kaboom" in result["error"]


class TestCoordinatorLoop:
    """``_execute_coordinator`` multi-turn state machine."""

    async def test_final_answer_terminates_in_one_turn(self, orchestrator):
        # Slice 1.19 contract: when stop_reason=='final_answer' the
        # outer loop must NOT make a follow-up call, even if delegations
        # happened earlier in the same run.
        coordinator_trace = {
            "turns": [{
                "turn_index": 1,
                "delegation_count": 1,
                "delegated_agents": ["worker"],
                "worker_results": [{
                    "agent_id": "worker",
                    "status": "success"
                }],
                "assistant_content": "Synthesizing",
                "stop_reason": "final_answer",
            }],
        }
        orchestrator.run = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "content": "Final answer"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "final_answer",
                        "coordinator": coordinator_trace,
                    },
                },
            })

        result = await orchestrator.dispatch(DispatchRequest(query="Synthesize"))

        assert result["status"] == "success"
        assert result["execution_mode"] == "coordinator"
        assert result["data"]["content"] == "Final answer"
        # CRITICAL: only one inner run() call.
        assert orchestrator.run.call_count == 1

    async def test_saturation_returns_max_turns_failure(self, orchestrator,
                                                        monkeypatch):
        # Lower the cap so the test can synthesize saturation cheaply.
        import gptase.core.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_MAX_COORDINATOR_TURNS", 2)

        coordinator_trace = {
            "turns": [{
                "turn_index": 1,
                "delegation_count": 1,
                "delegated_agents": ["worker"],
                "worker_results": [{
                    "agent_id": "worker",
                    "status": "success"
                }],
                "assistant_content": "Delegating",
                "stop_reason": None,
            }],
        }
        # Every turn keeps delegating without ever hitting final_answer.
        orchestrator.run = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "content": "still working"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "max_turns",
                        "coordinator": coordinator_trace,
                    },
                },
            })

        result = await orchestrator.dispatch(DispatchRequest(query="Loop forever"))

        assert result["status"] == "failed"
        assert "maximum number of orchestration turns" in result["error"]

    async def test_dispatch_wires_delegate_workspace_and_resets_counter(
            self, orchestrator, tmp_path):
        # dispatch() rebinds workspace_dir + zeroes _artifact_counter on
        # the global DelegateTask tool so each dispatch gets a fresh
        # per-run artifact namespace.
        from gptase.tools.base import get_tool_registry

        delegate = get_tool_registry().get("DelegateTask")
        if delegate is None:
            pytest.skip("DelegateTask tool not registered")
        delegate._artifact_counter = 99  # poison value to detect reset

        orchestrator.run = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "content": "done"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "final_answer"
                    }
                },
            })

        workspace = str(tmp_path / "ws")
        await orchestrator.dispatch(
            DispatchRequest(query="anything", workspace_dir=workspace))

        assert delegate.workspace_dir == workspace
        assert delegate._artifact_counter == 0
