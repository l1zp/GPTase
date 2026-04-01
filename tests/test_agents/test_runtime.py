"""Tests for the interactive agent runtime."""

from copy import deepcopy

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
        assert result.turns[0].stop_reason == RuntimeStopReason.FINAL_ANSWER
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
            dict(original_permissions),
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
        assert any(step["type"] == "tool_call" for step in result.steps)
        assert result.turns[0].tool_results[0].tool_name == tool.name
        assert result.turns[0].tool_results[0].content == "tool output"
        assert result.turns[1].assistant_content == "done"

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
            dict(original_permissions),
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
            dict(original_permissions),
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
        assert result.turns[0].stop_reason == RuntimeStopReason.ERROR
        assert result.turns[0].tool_results[0].error_type == "invalid_arguments"

    async def test_runtime_returns_needs_plan_when_evaluator_requests_handoff(
        self,
        monkeypatch,
    ):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool("HandoffTool", "tool output")
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
            dict(original_permissions),
            raising=False,
        )

        runtime = AgentRuntime(
            model=RecordingModel([
                ModelResponse(
                    content="I inspected the repo",
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
                    content=(
                        '{"action":"needs_plan","reason":"Need a DAG",'
                        '"planning_context":"Found multiple dependent steps",'
                        '"evidence_summary":"Tool output suggests staged execution",'
                        '"suggested_next_step":"Create a plan"}'),
                    usage={
                        "prompt_tokens": 8,
                        "completion_tokens": 5,
                        "total_tokens": 13,
                    },
                    model="test-model",
                    provider="test-provider",
                    tool_calls=None,
                    finish_reason="stop",
                ),
            ]),
            max_turns=3,
        )

        result = await runtime.run(
            self._messages(),
            allowed_tools=[tool.name],
            allow_plan_handoff=True,
            handoff_goal="Ship the feature",
        )

        assert result.stop_reason == RuntimeStopReason.NEEDS_PLAN
        assert result.plan_handoff is not None
        assert result.plan_handoff.goal == "Ship the feature"
        assert result.plan_handoff.reason == "Need a DAG"
        assert result.turns[0].stop_reason == RuntimeStopReason.NEEDS_PLAN

    async def test_runtime_continues_when_handoff_evaluator_says_continue(
        self,
        monkeypatch,
    ):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool("ContinueTool", "tool output")
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
            dict(original_permissions),
            raising=False,
        )

        model = RecordingModel([
            ModelResponse(
                content="Investigating",
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
                    arguments="{}",
                )],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                content='{"action":"continue","reason":"Need one more turn"}',
                usage={
                    "prompt_tokens": 8,
                    "completion_tokens": 5,
                    "total_tokens": 13,
                },
                model="test-model",
                provider="test-provider",
                tool_calls=None,
                finish_reason="stop",
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
        ])
        runtime = AgentRuntime(model=model, max_turns=3)

        result = await runtime.run(
            self._messages(),
            allowed_tools=[tool.name],
            allow_plan_handoff=True,
            handoff_goal="Ship the feature",
        )

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER
        assert result.content == "done"
        assert result.plan_handoff is None
        assert len(model.calls) == 3

    async def test_runtime_ignores_invalid_handoff_json_and_continues(
        self,
        monkeypatch,
    ):
        registry = get_tool_registry()
        original_tools = dict(registry._tools)
        original_permissions = dict(registry._permissions)
        tool = StaticTool("InvalidHandoffTool", "tool output")
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
            dict(original_permissions),
            raising=False,
        )

        model = RecordingModel([
            ModelResponse(
                content="Investigating",
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
                    arguments="{}",
                )],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                content="not json",
                usage={
                    "prompt_tokens": 8,
                    "completion_tokens": 5,
                    "total_tokens": 13,
                },
                model="test-model",
                provider="test-provider",
                tool_calls=None,
                finish_reason="stop",
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
        ])
        runtime = AgentRuntime(model=model, max_turns=3)

        result = await runtime.run(
            self._messages(),
            allowed_tools=[tool.name],
            allow_plan_handoff=True,
            handoff_goal="Ship the feature",
        )

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER
        assert result.plan_handoff is None
        assert len(model.calls) == 3
