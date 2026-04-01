"""Tests for tool-loop output handling."""

from copy import deepcopy

import pytest

from gptase.models.providers import _request_size_summary
from gptase.models.types import ModelResponse
from gptase.models.types import ToolCall
from gptase.tools.base import BaseTool
from gptase.tools.base import get_tool_registry
from gptase.tools.executor import ToolExecutor


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


@pytest.mark.asyncio
async def test_executor_truncates_large_tool_results(monkeypatch):
    registry = get_tool_registry()
    original_tools = dict(registry._tools)
    original_permissions = dict(registry._permissions)

    huge_tool = StaticTool("HugeToolForExecutorTest", ("A" * 12000) + "TAIL")
    monkeypatch.setattr(
        registry,
        "_tools",
        {
            **original_tools, huge_tool.name: huge_tool
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
            content="",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 3
            },
            model="test-model",
            provider="test-provider",
            tool_calls=[ToolCall(
                id="call-1",
                name=huge_tool.name,
                arguments="{}",
            )],
            finish_reason="tool_calls",
        ),
        ModelResponse(
            content="done",
            usage={
                "prompt_tokens": 12,
                "completion_tokens": 4
            },
            model="test-model",
            provider="test-provider",
            tool_calls=None,
            finish_reason="stop",
        ),
    ])

    executor = ToolExecutor(model=model, max_iterations=2, max_tool_result_chars=800)
    result = await executor.execute(
        [
            {
                "role": "system",
                "content": "system"
            },
            {
                "role": "user",
                "content": "user"
            },
        ],
        tools=[huge_tool.name],
    )

    assert result["status"] == "success"
    assert len(model.calls) == 2

    tool_message = model.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert len(tool_message["content"]) <= 800
    assert "[TOOL OUTPUT TRUNCATED]" in tool_message["content"]
    assert "TAIL" in tool_message["content"]

    tool_step = next(step for step in result["trace"]["steps"]
                     if step["type"] == "tool_call")
    assert tool_step["result_truncated"] is True
    assert tool_step["result_chars"] == 12004
    assert tool_step["stored_result_chars"] <= 800


@pytest.mark.asyncio
async def test_execute_calls_returns_batch_tool_metadata(monkeypatch):
    registry = get_tool_registry()
    original_tools = dict(registry._tools)
    original_permissions = dict(registry._permissions)

    tool = StaticTool("BatchToolForExecutorTest", "batch output")
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

    executor = ToolExecutor(model=RecordingModel([]))
    messages = [
        {
            "role": "system",
            "content": "system"
        },
        {
            "role": "user",
            "content": "user"
        },
    ]

    result = await executor.execute_calls(
        [ToolCall(id="call-1", name=tool.name, arguments="{}")],
        messages,
        iteration=1,
    )

    assert result["has_invalid_tool_arguments"] is False
    assert result["tool_results"][0]["tool_name"] == tool.name
    assert result["tool_results"][0]["content"] == "batch output"
    assert result["steps"][0]["type"] == "tool_call"
    assert result["messages"][-1]["role"] == "tool"


def test_request_size_summary_includes_tool_message_mapping():
    summary = _request_size_summary({
        "messages": [
            {
                "role": "system",
                "content": "system"
            },
            {
                "role":
                "assistant",
                "content":
                "",
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "Read",
                        "arguments": "{\"file_path\":\"/tmp/x\"}",
                    },
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call-1",
                "content": "tool output",
            },
        ],
        "tools": [],
    })

    assert summary["message_breakdown"][1]["tool_calls"] == [{
        "id": "call-1",
        "name": "Read"
    }]
    assert summary["message_breakdown"][2]["tool_call_id"] == "call-1"
