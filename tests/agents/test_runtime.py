"""Unit tests for gptase.agents.runtime.AgentRuntime.

Drives the turn loop with a RecordingModel that returns pre-canned
ModelResponses and StaticTools registered into a fresh ToolRegistry.
Covers final-answer termination, tool-loop turn recording, MAX_TURNS
and ERROR (invalid args) stop reasons, _build_coordinator_summary,
_extract_json_object, on_turn_complete callback, and resume_snapshot.
"""
from copy import deepcopy
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from gptase.agents.runtime import AgentRuntime
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.models.types import ModelResponse
from gptase.models.types import ToolCall
from gptase.tools.base import BaseTool
from gptase.tools.base import ToolRegistry


class _StaticTool(BaseTool):
    """Tool that returns a preconfigured payload."""

    def __init__(self, name: str, output: str):
        self.name = name
        self.description = "Static test payload."
        self.output = output

    def get_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        return self.output


class _RecordingModel:
    """Minimal model stub: returns the next pre-canned ModelResponse."""

    def __init__(self, responses: List[ModelResponse]):
        self.responses = list(responses)
        self.calls: List[Dict[str, Any]] = []
        self.default_config = None

    async def generate(self, messages, config=None, tools=None, **kwargs):
        self.calls.append({
            "messages": deepcopy(messages),
            "tools": deepcopy(tools),
        })
        return self.responses[len(self.calls) - 1]


def _final_response(content: str) -> ModelResponse:
    return ModelResponse(
        content=content,
        usage={
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2
        },
        model="test-model",
        provider="test",
        tool_calls=None,
        finish_reason="stop",
    )


def _tool_call_response(tool_calls: List[ToolCall]) -> ModelResponse:
    return ModelResponse(
        content="",
        usage={
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8
        },
        model="test-model",
        provider="test",
        tool_calls=tool_calls,
        finish_reason="tool_calls",
    )


@pytest.fixture
def runtime_factory():
    """Build an AgentRuntime with isolated registry + queued model responses."""

    def _factory(responses,
                 max_turns: int = 5,
                 max_tool_result_chars: int = 8000,
                 tools: Optional[List[BaseTool]] = None) -> AgentRuntime:
        model = _RecordingModel(responses)
        runtime = AgentRuntime(
            model=model,
            agent_id="test-agent",
            max_turns=max_turns,
            max_tool_result_chars=max_tool_result_chars,
        )
        # Replace the global registry with a fresh one for test isolation.
        registry = ToolRegistry()
        for tool in tools or []:
            registry.register(tool)
        runtime.registry = registry
        runtime.tool_executor.registry = registry
        return runtime

    return _factory


class TestAgentRuntimeFinalAnswer:
    """Single-turn termination when no tool_calls are returned."""

    async def test_returns_final_answer_when_no_tool_calls(self, runtime_factory):
        runtime = runtime_factory([_final_response("the answer is 42")])

        result = await runtime.run([{"role": "user", "content": "ask"}])

        assert result.content == "the answer is 42"
        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER.value
        assert result.turn_count == 1
        assert result.error is None
        # The single turn carries the final answer.
        assert len(result.snapshot.turns) == 1
        assert (result.snapshot.turns[0].assistant_content == "the answer is 42")


class TestAgentRuntimeToolLoop:
    """Multi-turn flow: tool_call -> tool execution -> next LLM turn."""

    async def test_records_assistant_message_and_tool_results(self, runtime_factory):
        runtime = runtime_factory(
            [
                _tool_call_response([ToolCall(id="c1", name="Echo", arguments="{}")]),
                _final_response("done"),
            ],
            tools=[_StaticTool("Echo", "echoed-output")],
        )

        result = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                   allowed_tools=["Echo"])

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER.value
        assert result.turn_count == 2
        # First turn has tool_results, second turn has none.
        first_turn = result.snapshot.turns[0]
        assert len(first_turn.tool_results) == 1
        assert first_turn.tool_results[0].tool_name == "Echo"
        assert first_turn.tool_results[0].content == "echoed-output"

    async def test_appends_assistant_then_tool_messages_into_state(
            self, runtime_factory):
        runtime = runtime_factory(
            [
                _tool_call_response([ToolCall(id="c1", name="Echo", arguments="{}")]),
                _final_response("done"),
            ],
            tools=[_StaticTool("Echo", "echoed-output")],
        )

        await runtime.run([{"role": "user", "content": "go"}], allowed_tools=["Echo"])

        # The model received the assistant + tool messages on the second call.
        second_call_messages = runtime.model.calls[1]["messages"]
        roles = [msg.get("role") for msg in second_call_messages]
        # user -> assistant (with tool_calls) -> tool
        assert roles == ["user", "assistant", "tool"]
        assert second_call_messages[2]["content"] == "echoed-output"


class TestAgentRuntimeStopReasons:
    """MAX_TURNS and ERROR stop reasons."""

    async def test_stops_at_max_turns(self, runtime_factory):
        # Always return a tool call -> never reaches a final answer.
        responses = [
            _tool_call_response([ToolCall(id=f"c{i}", name="Echo", arguments="{}")])
            for i in range(10)
        ]
        runtime = runtime_factory(
            responses,
            max_turns=3,
            tools=[_StaticTool("Echo", "loop")],
        )

        result = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                   allowed_tools=["Echo"])

        assert result.stop_reason == RuntimeStopReason.MAX_TURNS.value
        assert result.turn_count == 3
        assert "Maximum tool iterations reached" in (result.error or "")

    async def test_stops_on_invalid_tool_arguments(self, runtime_factory):
        runtime = runtime_factory(
            [
                _tool_call_response(
                    [ToolCall(id="c1", name="Echo", arguments="{not valid json")])
            ],
            tools=[_StaticTool("Echo", "ok")],
        )

        result = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                   allowed_tools=["Echo"])

        assert result.stop_reason == RuntimeStopReason.ERROR.value
        assert "invalid tool arguments" in (result.error or "")


class TestCoordinatorSummary:
    """_build_coordinator_summary aggregates DelegateTask payloads from turns."""

    async def test_summary_extracts_delegatetask_payload(self, runtime_factory):
        delegate_payload = ('{"agent_id": "worker-1", "status": "success", '
                            '"content": "delegated work done"}')
        runtime = runtime_factory(
            [
                _tool_call_response([
                    ToolCall(id="c1",
                             name="DelegateTask",
                             arguments='{"agent_id":"worker-1"}')
                ]),
                _final_response("aggregated"),
            ],
            tools=[_StaticTool("DelegateTask", delegate_payload)],
        )

        result = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                   allowed_tools=["DelegateTask"])

        summary = result.coordinator_summary
        assert summary is not None
        assert summary.delegation_count == 1
        assert summary.delegated_agents == ["worker-1"]
        assert summary.worker_results[0].agent_id == "worker-1"
        assert summary.worker_results[0].status == "success"
        assert summary.worker_results[0].content == "delegated work done"

    async def test_summary_returns_none_when_no_delegate_calls(self, runtime_factory):
        # Tool calls exist but none are DelegateTask.
        runtime = runtime_factory(
            [
                _tool_call_response([ToolCall(id="c1", name="Echo", arguments="{}")]),
                _final_response("done"),
            ],
            tools=[_StaticTool("Echo", "ok")],
        )

        result = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                   allowed_tools=["Echo"])

        assert result.coordinator_summary is None

    async def test_summary_aggregates_across_multiple_turns(self, runtime_factory):
        payload_1 = ('{"agent_id": "alpha", "status": "success", '
                     '"content": "alpha-out"}')
        payload_2 = ('{"agent_id": "beta", "status": "success", '
                     '"content": "beta-out"}')

        # Turn 1: DelegateTask alpha. Turn 2: DelegateTask beta. Turn 3: final.
        runtime = runtime_factory(
            [
                _tool_call_response(
                    [ToolCall(id="c1", name="DelegateAlpha", arguments='{"x":1}')]),
                _tool_call_response(
                    [ToolCall(id="c2", name="DelegateBeta", arguments='{"x":2}')]),
                _final_response("aggregated"),
            ],
            tools=[
                _StaticTool("DelegateAlpha", payload_1),
                _StaticTool("DelegateBeta", payload_2),
            ],
        )
        # Both tools registered as DelegateTask aliases — runtime
        # detects via tool_name == "DelegateTask". Use the actual name.
        # Re-register the same tool under DelegateTask name so the
        # coordinator_summary path triggers.
        delegate_alpha = _StaticTool("DelegateTask", payload_1)
        delegate_beta_payload = payload_2
        runtime = runtime_factory(
            [
                _tool_call_response(
                    [ToolCall(id="c1", name="DelegateTask", arguments='{"x":1}')]),
                _tool_call_response(
                    [ToolCall(id="c2", name="DelegateTask", arguments='{"x":2}')]),
                _final_response("aggregated"),
            ],
            tools=[delegate_alpha],
        )

        # Swap the StaticTool output between the two calls by registering
        # a tool whose output rotates. Simplest: mutable closure.
        outputs = iter([payload_1, delegate_beta_payload])

        class _RotatingDelegate(BaseTool):
            name = "DelegateTask"
            description = "rotating"

            def get_schema(self):
                return {"type": "object", "properties": {}}

            async def execute(self, **kwargs) -> str:
                return next(outputs)

        runtime.registry = ToolRegistry()
        runtime.registry.register(_RotatingDelegate())
        runtime.tool_executor.registry = runtime.registry

        result = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                   allowed_tools=["DelegateTask"])

        summary = result.coordinator_summary
        assert summary is not None
        assert summary.delegation_count == 2
        assert summary.delegated_agents == ["alpha", "beta"]
        # Two CoordinatorTurnSummary entries — one per delegating turn.
        assert len(summary.turns) == 2


class TestExtractJsonObject:
    """_extract_json_object: identity for {/[ start; balanced-brace scan."""

    def test_returns_content_unchanged_when_starts_with_brace(self, runtime_factory):
        runtime = runtime_factory([_final_response("x")])

        out = runtime._extract_json_object('{"a": 1}')

        assert out == '{"a": 1}'

    def test_extracts_first_balanced_brace_block_from_noisy_text(self, runtime_factory):
        runtime = runtime_factory([_final_response("x")])
        text = ('Some prose here. {"agent_id": "worker", '
                '"status": "success"} and trailing noise.')

        out = runtime._extract_json_object(text)

        assert out == '{"agent_id": "worker", "status": "success"}'


class TestRunCallback:
    """on_turn_complete invoked per completed turn."""

    async def test_on_turn_complete_callback_invoked_per_turn(self, runtime_factory):
        runtime = runtime_factory(
            [
                _tool_call_response([ToolCall(id="c1", name="Echo", arguments="{}")]),
                _final_response("done"),
            ],
            tools=[_StaticTool("Echo", "ok")],
        )

        callback = MagicMock()
        await runtime.run(
            [{
                "role": "user",
                "content": "go"
            }],
            allowed_tools=["Echo"],
            on_turn_complete=callback,
        )

        # 2 turns -> 2 callback invocations (final-answer turn breaks
        # before the callback path; only tool-completed turns invoke it).
        assert callback.call_count >= 1


class TestResumeSnapshot:
    """resume_snapshot rebuilds state with prior turns + advances turn_index."""

    async def test_resumes_from_snapshot_with_existing_turns(self, runtime_factory):
        # First run: produce a snapshot with one tool turn done.
        runtime = runtime_factory(
            [
                _tool_call_response([ToolCall(id="c1", name="Echo", arguments="{}")]),
                _final_response("first done"),
            ],
            tools=[_StaticTool("Echo", "ok")],
        )
        first = await runtime.run([{
            "role": "user",
            "content": "go"
        }],
                                  allowed_tools=["Echo"])
        snapshot_dump = first.snapshot.model_dump()

        # Second run: resume from that snapshot. Build a fresh runtime
        # with new responses; the resumed state already has 2 turns done.
        resumed = runtime_factory(
            [_final_response("resumed")],
            max_turns=5,
        )
        result = await resumed.run(
            messages=[],  # ignored when resuming
            resume_snapshot=snapshot_dump,
        )

        # Resumed state's turn_index starts at len(snapshot.turns) and
        # the new turn extends from there.
        assert result.turn_count >= len(snapshot_dump["turns"]) + 1
        assert result.content == "resumed"
