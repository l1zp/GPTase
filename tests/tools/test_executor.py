"""Unit tests for gptase.tools.executor.ToolExecutor.

Covers the live surface after L1 #20 refactor (execute() wrapper
removed): batch execute_calls flow, _execute_single_tool's four error
paths, _truncate_tool_result, and the trace-vs-message split that lets
JSON parsers downstream see full tool output even when the LLM-facing
message is truncated.

ToolExecutor is now AgentRuntime's per-batch tool helper rather than a
standalone entry point, so tests use a fresh ToolRegistry assigned
directly onto the executor (no global-singleton pollution).
"""
import json

import pytest

from gptase.models.types import ToolCall
from gptase.tools.base import BaseTool
from gptase.tools.base import ToolRegistry
from gptase.tools.executor import ToolExecutor


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


class _BoomTool(BaseTool):
    """Tool that raises on execute."""
    name = "Boom"
    description = "Raises when called."

    def get_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        raise RuntimeError("kaboom")


@pytest.fixture
def executor():
    """ToolExecutor with a fresh empty registry; tests register tools as needed."""
    e = ToolExecutor(agent_id="test-agent", max_tool_result_chars=800)
    e.registry = ToolRegistry()
    return e


class TestToolExecutorInit:
    """__init__ stores config + bootstraps from the global registry by default."""

    def test_init_uses_global_registry_and_defaults(self):
        e = ToolExecutor()

        assert e.agent_id == ""
        assert e.max_iterations == 10
        assert e.max_tool_result_chars == 8000
        # Default registry is the global singleton — confirm via type only.
        assert isinstance(e.registry, ToolRegistry)


class TestExecuteCallsParallel:
    """execute_calls fans out tool calls and aggregates per-call metadata."""

    async def test_executes_multiple_tool_calls_in_parallel_aggregating_results(
            self, executor):
        executor.registry.register(_StaticTool("ToolA", "result-a"))
        executor.registry.register(_StaticTool("ToolB", "result-b"))

        messages = [{"role": "user", "content": "go"}]
        result = await executor.execute_calls(
            tool_calls=[
                ToolCall(id="c1", name="ToolA", arguments="{}"),
                ToolCall(id="c2", name="ToolB", arguments="{}"),
            ],
            messages=messages,
            iteration=1,
        )

        # Both tool messages appended in call order.
        assert result["messages"][-2]["content"] == "result-a"
        assert result["messages"][-1]["content"] == "result-b"
        assert result["has_invalid_tool_arguments"] is False
        assert {tr["tool_name"] for tr in result["tool_results"]} == {"ToolA", "ToolB"}

    async def test_per_call_step_includes_iteration_and_duration(self, executor):
        executor.registry.register(_StaticTool("Step", "ok"))

        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="Step", arguments="{}")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=7,
        )

        step = result["steps"][0]
        assert step["type"] == "tool_call"
        assert step["iteration"] == 7
        assert step["tool_name"] == "Step"
        assert "duration_ms" in step
        assert step["result_truncated"] is False


class TestSingleToolErrorPaths:
    """Four error branches: unknown / not_allowed / invalid_arguments / execution_failed."""

    async def test_unknown_tool_returns_error_metadata(self, executor):
        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="Missing", arguments="{}")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=1,
        )

        assert result["tool_results"][0]["error_type"] == "unknown_tool"
        assert "Unknown tool: Missing" in result["messages"][-1]["content"]

    async def test_disallowed_tool_returns_not_allowed_error(self, executor):
        executor.registry.register(_StaticTool("Restricted", "secret"),
                                   allowed_agents=["other-agent"])

        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="Restricted", arguments="{}")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=1,
        )

        assert result["tool_results"][0]["error_type"] == "not_allowed"
        assert "not allowed" in result["messages"][-1]["content"]

    async def test_invalid_json_arguments_marked_as_invalid(self, executor):
        executor.registry.register(_StaticTool("Json", "out"))

        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="Json", arguments="{not valid json")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=1,
        )

        assert result["tool_results"][0]["error_type"] == "invalid_arguments"
        assert result["has_invalid_tool_arguments"] is True

    async def test_execute_exception_marked_as_execution_failed(self, executor):
        executor.registry.register(_BoomTool())

        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="Boom", arguments="{}")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=1,
        )

        assert result["tool_results"][0]["error_type"] == "execution_failed"
        assert "kaboom" in result["messages"][-1]["content"]


class TestTruncateToolResult:
    """_truncate_tool_result respects max_tool_result_chars."""

    def test_short_result_returned_unchanged(self, executor):
        out = executor._truncate_tool_result("ToolX", "small payload")

        assert out == "small payload"

    def test_read_tool_exempt_from_truncation(self, executor):
        # Read is in _TRUNCATE_EXEMPT_TOOLS because the caller already
        # scopes its output via the offset/limit args — clipping again
        # silently mid-document defeats the deliberate slice.
        big = "X" * 50000  # >> max_tool_result_chars (800)

        out = executor._truncate_tool_result("Read", big)

        assert out == big
        assert len(out) == 50000

    async def test_long_result_includes_prefix_marker_and_tail(self, executor):
        # Tool output much larger than max_tool_result_chars (800).
        big = ("HEAD" + ("A" * 12000) + "TAIL")
        executor.registry.register(_StaticTool("Big", big))

        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="Big", arguments="{}")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=1,
        )

        msg = result["messages"][-1]["content"]
        assert len(msg) <= 800
        assert "[TOOL OUTPUT TRUNCATED]" in msg
        assert "TAIL" in msg  # tail bytes preserved
        # Step metadata flags truncation correctly.
        step = result["steps"][0]
        assert step["result_truncated"] is True
        assert step["result_chars"] == len(big)
        assert step["stored_result_chars"] <= 800


class TestTraceFullContentVsTruncatedMessage:
    """tool_results carries FULL output even when message is truncated."""

    async def test_tool_results_keep_full_content_when_message_truncated(
            self, executor):
        # JSON-shaped payload large enough to trigger truncation. The
        # downstream consumer (runtime._build_coordinator_summary) parses
        # tool_results.content; if it were truncated, JSON parsing would
        # fail.
        payload = ('{"agent_id": "worker", "status": "success", "content": "' +
                   ("X" * 12000) + '"}')
        executor.registry.register(_StaticTool("WorkerLike", payload))

        result = await executor.execute_calls(
            tool_calls=[ToolCall(id="c1", name="WorkerLike", arguments="{}")],
            messages=[{
                "role": "user",
                "content": "go"
            }],
            iteration=1,
        )

        # LLM-facing message is truncated as before.
        assert len(result["messages"][-1]["content"]) <= 800
        assert "[TOOL OUTPUT TRUNCATED]" in result["messages"][-1]["content"]

        # Trace tool_results carry full untruncated payload.
        assert result["tool_results"][0]["content"] == payload
        parsed = json.loads(result["tool_results"][0]["content"])
        assert parsed["agent_id"] == "worker"
        assert parsed["status"] == "success"
