"""Unit tests for gptase.tools.mcp.

Covers the three classes — McpServerConfig (pydantic config),
McpProxyTool (BaseTool wrapper that forwards execute() to an MCP
session), and McpManager (lifecycle + idempotency). McpManager.connect
real-protocol path is intentionally not tested — it requires the mcp
package + actual stdio/SSE subprocess infrastructure and belongs to
L3 integration tests.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from gptase.tools.mcp import McpManager
from gptase.tools.mcp import McpProxyTool
from gptase.tools.mcp import McpServerConfig


def _content_item(text: str) -> SimpleNamespace:
    """Shape an MCP content item — has .text attribute."""
    return SimpleNamespace(text=text)


class TestMcpServerConfig:
    """McpServerConfig pydantic defaults + transport variants."""

    def test_default_stdio_transport(self):
        cfg = McpServerConfig()

        assert cfg.transport == "stdio"
        assert cfg.command is None
        assert cfg.args == []
        assert cfg.env is None
        assert cfg.cwd is None
        assert cfg.url is None

    def test_stdio_full_round_trip(self):
        cfg = McpServerConfig(
            transport="stdio",
            command="node",
            args=["/path/to/server.js", "--debug"],
            env={"NODE_ENV": "production"},
            cwd="/tmp/work",
        )

        assert cfg.transport == "stdio"
        assert cfg.command == "node"
        assert cfg.args == ["/path/to/server.js", "--debug"]
        assert cfg.env == {"NODE_ENV": "production"}
        assert cfg.cwd == "/tmp/work"

    def test_sse_transport_with_url(self):
        cfg = McpServerConfig(transport="sse", url="http://localhost:3000/sse")

        assert cfg.transport == "sse"
        assert cfg.url == "http://localhost:3000/sse"
        # stdio fields default to None / [] so unused.
        assert cfg.command is None


class TestMcpProxyToolGetSchema:
    """get_schema handles 3 input_schema shapes: None / dict / pydantic."""

    def test_returns_empty_object_when_input_schema_none(self):
        proxy = McpProxyTool(
            server_name="srv",
            mcp_tool_name="tool",
            description="desc",
            input_schema=None,
            session=MagicMock(),
        )

        assert proxy.get_schema() == {"type": "object", "properties": {}}

    def test_returns_dict_when_input_schema_dict(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        proxy = McpProxyTool(
            server_name="srv",
            mcp_tool_name="tool",
            description="desc",
            input_schema=schema,
            session=MagicMock(),
        )

        assert proxy.get_schema() == schema

    def test_returns_dump_when_input_schema_has_model_dump(self):
        # Simulate a pydantic-shaped schema object.
        fake_pydantic = MagicMock()
        fake_pydantic.model_dump = MagicMock(return_value={
            "type": "object",
            "from": "pydantic"
        })

        proxy = McpProxyTool(
            server_name="srv",
            mcp_tool_name="tool",
            description="desc",
            input_schema=fake_pydantic,
            session=MagicMock(),
        )

        result = proxy.get_schema()

        assert result == {"type": "object", "from": "pydantic"}
        fake_pydantic.model_dump.assert_called_once_with(exclude_none=True)


class TestMcpProxyToolExecute:
    """execute forwards to session.call_tool and shapes the response."""

    async def test_executes_with_kwargs_and_returns_concatenated_text(self):
        session = MagicMock()
        session.call_tool = AsyncMock(return_value=SimpleNamespace(
            content=[_content_item("part one"),
                     _content_item("part two")],
            isError=False,
        ))

        proxy = McpProxyTool(
            server_name="srv",
            mcp_tool_name="search",
            description="",
            input_schema=None,
            session=session,
        )

        out = await proxy.execute(query="find me")

        assert out == "part one\npart two"
        session.call_tool.assert_awaited_once_with("search", {"query": "find me"})

    async def test_returns_info_when_no_content_items(self):
        session = MagicMock()
        session.call_tool = AsyncMock(
            return_value=SimpleNamespace(content=[], isError=False))

        proxy = McpProxyTool(
            server_name="srv",
            mcp_tool_name="ping",
            description="",
            input_schema=None,
            session=session,
        )

        out = await proxy.execute()

        assert "[INFO] MCP tool returned no content" in out

    async def test_returns_error_prefix_when_is_error_true(self):
        session = MagicMock()
        session.call_tool = AsyncMock(return_value=SimpleNamespace(
            content=[_content_item("server failed")],
            isError=True,
        ))

        proxy = McpProxyTool(
            server_name="srv",
            mcp_tool_name="failing",
            description="",
            input_schema=None,
            session=session,
        )

        out = await proxy.execute()

        assert out.startswith("[ERROR]")
        assert "failing" in out
        assert "server failed" in out


class TestMcpManager:
    """McpManager idempotency + graceful disconnect."""

    async def test_idempotent_connect_when_already_connected(self):
        manager = McpManager()
        # Pretend we're already connected (e.g. from a prior connect call).
        manager._connected = True

        # connect() short-circuits without touching the mcp imports or
        # iterating server_configs.
        registry = MagicMock()
        await manager.connect(registry, {"srv": McpServerConfig()})

        registry.register.assert_not_called()
        assert manager._connected is True
        # _exit_stack remains None — no AsyncExitStack created on the second call.
        assert manager._exit_stack is None

    async def test_disconnect_handles_no_exit_stack_gracefully(self):
        manager = McpManager()

        # Disconnect when no connect has run — must not raise.
        await manager.disconnect()

        assert manager._connected is False
        assert manager._exit_stack is None
