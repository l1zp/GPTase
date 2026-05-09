"""Tests for the interactive agent runtime."""

from copy import deepcopy
import json

from gptase.agents.runtime import AgentRuntime
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.models.types import ModelResponse
from gptase.models.types import ToolCall
from gptase.tools.base import BaseTool
from gptase.tools.base import get_tool_registry


class StaticTool(BaseTool):
    """Tool that returns a preconfigured string."""

    def __init__(self, name: str, output: str):
        self.name = name
        self.description = "Return a static test payload."
        self.output = output

    def get_schema(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs) -> str:
        return self.output


class RecordingModel:
    """Minimal model stub that records every generate() call."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.default_config = None

    async def generate(self, messages, config=None, tools=None, **kwargs):
        self.calls.append({
            "messages": deepcopy(messages),
            "tools": deepcopy(tools),
        })
        return self.responses[len(self.calls) - 1]


class TestAgentRuntime:
    """Tests for AgentRuntime."""

    @staticmethod
    def _messages():
        return [
            {
                "role": "system",
                "content": "system"
            },
            {
                "role": "user",
                "content": "user"
            },
        ]

    async def test_runtime_returns_final_answer_without_tools(self):
        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="done",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=None,
                    finish_reason="stop",
                ),
            ]),
            max_turns=3,
        )

        result = await runtime.run(self._messages(), allowed_tools=[])

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER
        assert result.turn_count == 1
        assert result.content == "done"
        assert result.snapshot.turns[0].stop_reason == RuntimeStopReason.FINAL_ANSWER
        assert result.snapshot.turns[0].assistant_content == "done"

    async def test_runtime_records_turns_and_tool_results(self, monkeypatch):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool("RuntimeTool", "tool output")
        monkeypatch.setattr(
            registry,
            "_tools",
            {
                **original_tools, tool.name: tool
            },
            raising=False,
        )
        monkeypatch.setattr(
            registry,
            "_permissions",
            {
                **dict(original_permissions),
                tool.name: [""],
            },
            raising=False,
        )

        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="I'll inspect that",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name=tool.name,
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    content="done",
                    usage={
                        "prompt_tokens": 12,
                        "completion_tokens": 4,
                        "total_tokens": 16,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=None,
                    finish_reason="stop",
                ),
            ]),
            max_turns=3,
        )

        result = await runtime.run(self._messages(), allowed_tools=[tool.name])

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER
        assert result.turn_count == 2
        assert any(step["type"] == "tool_call" for step in result.snapshot.steps)
        assert result.snapshot.turns[0].tool_results[0].tool_name == tool.name
        assert result.snapshot.turns[0].tool_results[0].content == "tool output"
        assert result.snapshot.turns[1].assistant_content == "done"

    async def test_runtime_stops_at_max_turns(self, monkeypatch):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool("MaxTurnTool", "tool output")
        monkeypatch.setattr(
            registry,
            "_tools",
            {
                **original_tools, tool.name: tool
            },
            raising=False,
        )
        monkeypatch.setattr(
            registry,
            "_permissions",
            {
                **dict(original_permissions),
                tool.name: [""],
            },
            raising=False,
        )

        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="keep going",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name=tool.name,
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
            ]),
            max_turns=1,
        )

        result = await runtime.run(
            self._messages(),
            allowed_tools=[tool.name],
            max_turns=1,
        )

        assert result.stop_reason == RuntimeStopReason.MAX_TURNS
        assert result.error == "Maximum tool iterations reached"
        assert result.turn_count == 1

    async def test_runtime_stops_on_invalid_tool_arguments(self, monkeypatch):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool("BadArgTool", "tool output")
        monkeypatch.setattr(
            registry,
            "_tools",
            {
                **original_tools, tool.name: tool
            },
            raising=False,
        )
        monkeypatch.setattr(
            registry,
            "_permissions",
            {
                **dict(original_permissions),
                tool.name: [""],
            },
            raising=False,
        )

        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="I'll call the tool",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=[ToolCall(
                        id="call-1",
                        name=tool.name,
                        arguments="{",
                    )],
                    finish_reason="tool_calls",
                ),
            ]),
            max_turns=3,
        )

        result = await runtime.run(
            self._messages(),
            allowed_tools=[tool.name],
            max_turns=3,
        )

        assert result.stop_reason == RuntimeStopReason.ERROR
        assert result.turn_count == 1
        assert result.snapshot.turns[0].stop_reason == RuntimeStopReason.ERROR
        assert result.snapshot.turns[0].tool_results[
            0].error_type == "invalid_arguments"

    async def test_runtime_extracts_coordinator_summary_from_delegate_task(
        self,
        monkeypatch,
    ):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool(
            "DelegateTask",
            json.dumps(
                {
                    "agent_id": "code-analyzer",
                    "status": "success",
                    "content": "worker result",
                    "error": None,
                },
                ensure_ascii=False,
            ),
        )
        monkeypatch.setattr(
            registry,
            "_tools",
            {
                **original_tools, tool.name: tool
            },
            raising=False,
        )
        monkeypatch.setattr(
            registry,
            "_permissions",
            {
                **dict(original_permissions),
                tool.name: [""],
            },
            raising=False,
        )

        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="Delegating this",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name=tool.name,
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    content="done",
                    usage={
                        "prompt_tokens": 12,
                        "completion_tokens": 4,
                        "total_tokens": 16,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=None,
                    finish_reason="stop",
                ),
            ]),
            max_turns=3,
        )

        result = await runtime.run(self._messages(), allowed_tools=[tool.name])

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER
        assert result.coordinator_summary is not None
        assert result.coordinator_summary.turn_count == 1
        assert result.coordinator_summary.delegation_count == 1
        assert result.coordinator_summary.delegated_agents == ["code-analyzer"]
        assert result.coordinator_summary.turns[0].turn_index == 1
        assert result.coordinator_summary.worker_results[0].content == "worker result"

    async def test_runtime_aggregates_multiple_delegate_turns(self, monkeypatch):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool(
            "DelegateTask",
            json.dumps(
                {
                    "agent_id": "code-analyzer",
                    "status": "success",
                    "content": "worker result",
                    "error": None,
                },
                ensure_ascii=False,
            ),
        )
        monkeypatch.setattr(
            registry,
            "_tools",
            {
                **original_tools, tool.name: tool
            },
            raising=False,
        )
        monkeypatch.setattr(
            registry,
            "_permissions",
            {
                **dict(original_permissions),
                tool.name: [""],
            },
            raising=False,
        )

        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="Delegating once",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name=tool.name,
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    content="Delegating twice",
                    usage={
                        "prompt_tokens": 12,
                        "completion_tokens": 3,
                        "total_tokens": 15,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=[
                        ToolCall(
                            id="call-2",
                            name=tool.name,
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    content="done",
                    usage={
                        "prompt_tokens": 14,
                        "completion_tokens": 2,
                        "total_tokens": 16,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=None,
                    finish_reason="stop",
                ),
            ]),
            max_turns=4,
        )

        result = await runtime.run(self._messages(), allowed_tools=[tool.name])

        assert result.coordinator_summary is not None
        assert result.coordinator_summary.turn_count == 2
        assert result.coordinator_summary.delegation_count == 2
        assert [turn.turn_index for turn in result.coordinator_summary.turns] == [1, 2]
