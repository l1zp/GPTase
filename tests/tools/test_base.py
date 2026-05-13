"""Unit tests for gptase.tools.base — BaseTool + ToolRegistry.

Covers the live surface after L1 #19 dead-code purge: BaseTool's
abstract API + dict-returning to_tool_definition, ToolRegistry's
register/get/get_schemas/is_allowed/mcp_connected, and the global
get_tool_registry() singleton.
"""
import logging
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from gptase.tools.base import BaseTool
from gptase.tools.base import get_tool_registry
from gptase.tools.base import ToolRegistry


class _StubTool(BaseTool):
    """Concrete BaseTool subclass for tests."""
    name = "Stub"
    description = "Test stub tool"

    def get_schema(self):
        return {"type": "object", "properties": {"x": {"type": "string"}}}

    async def execute(self, **kwargs):
        return f"stub:{kwargs}"


class _OtherTool(BaseTool):
    name = "Other"
    description = "Another test tool"

    def get_schema(self):
        return {"type": "object"}

    async def execute(self, **kwargs):
        return "other"


class TestBaseTool:
    """to_tool_definition returns a dict ready for OpenAI tools=[...]."""

    def test_subclass_returns_valid_definition_dict(self):
        tool = _StubTool()

        defn = tool.to_tool_definition()

        assert defn == {
            "type": "function",
            "function": {
                "name": "Stub",
                "description": "Test stub tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "string"
                        }
                    },
                },
            },
        }


class TestToolRegistryRegister:
    """register(tool) stores it; allowed_agents records permission."""

    def test_register_stores_tool_under_name(self):
        registry = ToolRegistry()
        tool = _StubTool()

        registry.register(tool)

        assert registry.get("Stub") is tool

    def test_register_with_allowed_agents_records_permission(self):
        registry = ToolRegistry()
        tool = _StubTool()

        registry.register(tool, allowed_agents=["agent-x"])

        assert registry._permissions["Stub"] == ["agent-x"]


class TestToolRegistryGet:
    """get(name) returns the tool or None when missing."""

    def test_get_returns_tool_or_none(self):
        registry = ToolRegistry()
        registry.register(_StubTool())

        assert isinstance(registry.get("Stub"), _StubTool)
        assert registry.get("Missing") is None


class TestToolRegistryGetSchemas:
    """get_schemas returns dicts in input order; missing names get warning."""

    def test_get_schemas_returns_list_in_order(self):
        registry = ToolRegistry()
        registry.register(_StubTool())
        registry.register(_OtherTool())

        schemas = registry.get_schemas(["Other", "Stub"])

        assert len(schemas) == 2
        assert schemas[0]["function"]["name"] == "Other"
        assert schemas[1]["function"]["name"] == "Stub"

    def test_get_schemas_skips_unknown_tools_with_warning(self, caplog):
        registry = ToolRegistry()
        registry.register(_StubTool())

        with caplog.at_level(logging.WARNING):
            schemas = registry.get_schemas(["Stub", "DoesNotExist"])

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "Stub"
        assert any("DoesNotExist" in r.message for r in caplog.records)


class TestToolRegistryIsAllowed:
    """is_allowed gates by permission list (None = allow all)."""

    def test_is_allowed_default_no_restriction(self):
        registry = ToolRegistry()
        registry.register(_StubTool())

        assert registry.is_allowed("Stub", "any-agent") is True

    def test_is_allowed_blocks_agent_outside_permission(self):
        registry = ToolRegistry()
        registry.register(_StubTool(), allowed_agents=["allowed-agent"])

        assert registry.is_allowed("Stub", "blocked-agent") is False

    def test_is_allowed_permits_listed_agent(self):
        registry = ToolRegistry()
        registry.register(_StubTool(), allowed_agents=["alice", "bob"])

        assert registry.is_allowed("Stub", "alice") is True
        assert registry.is_allowed("Stub", "bob") is True


class TestToolRegistryMcpConnected:
    """mcp_connected async ctx mgr: lazy McpManager + connect/disconnect lifecycle."""

    async def test_mcp_connected_no_op_when_configs_empty(self):
        registry = ToolRegistry()

        async with registry.mcp_connected({}):
            assert registry._mcp_manager is None  # never created

        assert registry._mcp_manager is None

    async def test_mcp_connected_invokes_manager_connect_then_disconnect(
            self, monkeypatch):
        # Patch McpManager at its definition site so the lazy import
        # inside mcp_connected resolves to a mock.
        fake_manager = MagicMock()
        fake_manager.connect = AsyncMock()
        fake_manager.disconnect = AsyncMock()
        monkeypatch.setattr(
            "gptase.tools.mcp.McpManager",
            MagicMock(return_value=fake_manager),
        )

        registry = ToolRegistry()
        configs = {"server-1": {"transport": "stdio", "command": "x"}}

        async with registry.mcp_connected(configs):
            fake_manager.connect.assert_awaited_once_with(registry, configs)
            assert fake_manager.disconnect.await_count == 0  # not yet

        fake_manager.disconnect.assert_awaited_once()
        # Manager state cleared so a future enter restarts the lifecycle.
        assert registry._mcp_manager is None


class TestGetToolRegistry:
    """get_tool_registry returns a memoized ToolRegistry with defaults."""

    def test_get_tool_registry_returns_singleton_with_default_tools(self, monkeypatch):
        # Reset the module-level global so this test's call triggers
        # default-tool registration via handlers.register_default_tools.
        import gptase.tools.base as base_module
        monkeypatch.setattr(base_module, "_global_registry", None)

        first = get_tool_registry()
        second = get_tool_registry()

        assert first is second
        # Default tools wired up by handlers.register_default_tools include
        # the standard filesystem + shell set.
        assert first.get("Read") is not None
        assert first.get("Bash") is not None
