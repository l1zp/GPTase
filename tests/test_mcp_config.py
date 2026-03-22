"""Tests for MCP config normalization and executor cleanup."""

from copy import deepcopy

import pytest

from gptase.models.types import ModelResponse
from gptase.tools.executor import ToolExecutor
from gptase.utils.config import FrameworkConfig


class _MinimalModel:
    def __init__(self):
        self.default_config = None
        self.calls = []

    async def generate(self, messages, config=None, tools=None):
        self.calls.append(
            {
                "messages": deepcopy(messages),
                "tools": deepcopy(tools),
            }
        )
        return ModelResponse(
            content="done",
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            model="test-model",
            provider="test-provider",
            tool_calls=None,
            finish_reason="stop",
        )


def test_framework_config_strips_mcp_comment_entries():
    config = FrameworkConfig(
        model_name="Doubao-Seed-2.0-pro",
        mcp_servers={
            "_comment": {"note": "example only"},
            "brave-search": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            },
        },
    )

    assert "_comment" not in config.mcp_servers
    assert "brave-search" in config.mcp_servers


@pytest.mark.asyncio
async def test_executor_disconnects_mcp_after_execute(monkeypatch):
    model = _MinimalModel()
    executor = ToolExecutor(
        model=model,
        mcp_server_configs={"demo": {"transport": "stdio", "command": "echo"}},
    )

    calls = []

    async def _ensure(server_configs):
        calls.append(("ensure", dict(server_configs)))

    async def _disconnect():
        calls.append(("disconnect", None))

    monkeypatch.setattr(executor.registry, "ensure_mcp_connected", _ensure)
    monkeypatch.setattr(executor.registry, "disconnect_mcp", _disconnect)

    result = await executor.execute(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]
    )

    assert result["status"] == "success"
    assert calls == [
        ("ensure", {"demo": {"transport": "stdio", "command": "echo"}}),
        ("disconnect", None),
    ]
