"""Tests for SDK integration layer (sdk_adapter.py and tool_bridge.py).

These tests validate the bridge between GPTase tools and Claude Agent SDK
without requiring the actual SDK to be installed.
"""

import asyncio
import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.agents.sdk_adapter import SDKAgentAdapter
from src.agents.tool_bridge import ToolBridge

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_tool():
    """Create a mock GPTase tool."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            }
        },
        "required": ["query"],
    }

    result = MagicMock()
    result.data = {"answer": "test result"}
    result.status = "success"
    tool.execute = AsyncMock(return_value=result)
    return tool


@pytest.fixture
def tool_registry(mock_tool):
    """Create a mock tool registry with a test tool."""
    registry = MagicMock()
    registry._tools = {"test_tool": mock_tool}
    registry.get_tool.side_effect = lambda name: (mock_tool
                                                  if name == "test_tool" else None)
    return registry


@pytest.fixture
def agent_definition():
    """Create a mock agent definition."""
    definition = MagicMock()
    definition.agent_id = "test_agent"
    definition.system_prompt = "You are a test agent."
    definition.task_processing = "Process the task carefully."
    definition.output_format = "Return JSON output."
    definition.tools = ["test_tool"]
    definition.capabilities = ["test"]
    definition.requires_model = True
    definition.temperature = 0.7
    definition.max_tokens = 1000
    return definition


# ============================================================================
# ToolBridge Tests
# ============================================================================


class TestToolBridge:
    """Tests for ToolBridge class."""

    def test_init(self, tool_registry):
        """Test ToolBridge initialization."""
        bridge = ToolBridge(tool_registry)
        assert bridge.tool_registry == tool_registry
        assert bridge._wrapped_tools == {}

    def test_to_sdk_tools(self, tool_registry):
        """Test converting tools to SDK format."""
        bridge = ToolBridge(tool_registry)
        sdk_tools = bridge.to_sdk_tools(["test_tool"])
        assert len(sdk_tools) == 1
        assert sdk_tools[0]["name"] == "test_tool"
        assert sdk_tools[0]["description"] == "A test tool"
        assert "input_schema" in sdk_tools[0]

    def test_to_sdk_tools_skips_missing(self, tool_registry):
        """Test that missing tools are skipped."""
        bridge = ToolBridge(tool_registry)
        sdk_tools = bridge.to_sdk_tools(["test_tool", "nonexistent"])
        assert len(sdk_tools) == 1

    def test_to_sdk_tools_all(self, tool_registry):
        """Test converting all tools when no names specified."""
        bridge = ToolBridge(tool_registry)
        sdk_tools = bridge.to_sdk_tools()
        assert len(sdk_tools) == 1

    def test_list_bridgeable_tools(self, tool_registry):
        """Test listing bridgeable tools."""
        bridge = ToolBridge(tool_registry)
        tools = bridge.list_bridgeable_tools()
        assert "test_tool" in tools

    @pytest.mark.asyncio
    async def test_execute_tool(self, tool_registry, mock_tool):
        """Test tool execution through bridge."""
        bridge = ToolBridge(tool_registry)
        result = await bridge._execute_tool(mock_tool, {"query": "test"})
        parsed = json.loads(result)
        assert parsed == {"answer": "test result"}
        mock_tool.execute.assert_called_once_with(query="test")

    @pytest.mark.asyncio
    async def test_execute_tool_error(self, tool_registry):
        """Test tool execution error handling."""
        bridge = ToolBridge(tool_registry)
        failing_tool = MagicMock()
        failing_tool.execute = AsyncMock(side_effect=RuntimeError("tool failed"))
        result = await bridge._execute_tool(failing_tool, {})
        parsed = json.loads(result)
        assert "error" in parsed

    def test_build_tool_schema(self, tool_registry, mock_tool):
        """Test building SDK-compatible schema."""
        bridge = ToolBridge(tool_registry)
        schema = bridge._build_tool_schema("test_tool", mock_tool)
        assert schema["name"] == "test_tool"
        assert schema["description"] == "A test tool"
        assert schema["input_schema"]["type"] == "object"

    def test_build_tool_schema_no_schema(self, tool_registry):
        """Test schema building for tool without schema."""
        bridge = ToolBridge(tool_registry)
        tool = MagicMock(spec=[])  # No attributes
        tool.description = "No schema tool"
        schema = bridge._build_tool_schema("bare_tool", tool)
        assert schema["input_schema"] == {"type": "object", "properties": {}}


# ============================================================================
# SDKAgentAdapter Tests
# ============================================================================


class TestSDKAgentAdapter:
    """Tests for SDKAgentAdapter class."""

    def test_init(self, tool_registry):
        """Test adapter initialization."""
        adapter = SDKAgentAdapter(tool_registry)
        assert adapter.tool_registry == tool_registry
        assert adapter.model_manager is None
        assert adapter._tool_bridge is None

    def test_init_with_model_manager(self, tool_registry):
        """Test adapter initialization with model manager."""
        model_manager = MagicMock()
        adapter = SDKAgentAdapter(tool_registry, model_manager)
        assert adapter.model_manager == model_manager

    @pytest.mark.asyncio
    async def test_execute_without_sdk(self, tool_registry, agent_definition):
        """Test that execute raises ImportError when SDK not installed."""
        adapter = SDKAgentAdapter(tool_registry)
        with pytest.raises(ImportError, match="Claude Agent SDK"):
            await adapter.execute(agent_definition, "test task")


# ============================================================================
# SDK Integration Skipped Test
# ============================================================================


@pytest.mark.skipif(
    True,  # Skip unless SDK is installed
    reason="Claude Agent SDK not installed")
class TestSDKIntegration:
    """Integration tests requiring actual Claude Agent SDK."""

    @pytest.mark.asyncio
    async def test_full_sdk_execution(self, tool_registry, agent_definition):
        """Test full SDK execution flow."""
        adapter = SDKAgentAdapter(tool_registry)
        result = await adapter.execute(agent_definition, "Extract enzymes")
        assert result["status"] == "success"
