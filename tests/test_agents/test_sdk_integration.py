"""Tests for Claude Agent SDK integration."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.agents.hooks import build_hooks
from src.agents.hooks import ConcurrencyControl
from src.agents.hooks import get_default_hooks
from src.agents.hooks import get_minimal_hooks
from src.agents.hooks import get_permissive_hooks
from src.agents.markdown_agent import AgentDefinition
from src.agents.markdown_agent import MarkdownAgent
from src.agents.markdown_agent import MarkdownAgentFactory
from src.agents.sdk_adapter import SDKAgentAdapter
from src.agents.tool_bridge import ToolBridge
from src.tools.base import BaseTool
from src.tools.base import ToolResult


class MockTool(BaseTool):
    """Mock tool for testing."""

    def __init__(self, name="test_tool"):
        super().__init__(name=name, description="A test tool", timeout=30)

    async def execute(self, **kwargs):
        return ToolResult.success(data={"result": "success"})

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string"
                }
            },
            "required": ["input"],
        }


class MockMemoryManager:
    """Mock memory manager for testing."""

    async def store_message(self, message):
        pass

    async def get_next_message(self, agent_id, timeout):
        return None

    async def store_agent_state(self, state):
        pass

    async def get_usage(self):
        return {}


class MockToolRegistry:
    """Mock tool registry for testing."""

    def __init__(self):
        self._tools = {}

    def register_tool(self, tool, category="general"):
        self._tools[tool.name] = tool

    def get_tool(self, name):
        return self._tools.get(name)

    async def execute_tool(self, name, params, timeout=None):
        tool = self.get_tool(name)
        if tool:
            return await tool.safe_execute(**params)
        return ToolResult.from_error(f"Tool {name} not found")


# ============================================================================
# SDKAgentAdapter Tests
# ============================================================================


class TestSDKAgentAdapter:
    """Tests for SDKAgentAdapter class."""

    @pytest.fixture
    def tool_registry(self):
        registry = MockToolRegistry()
        registry.register_tool(MockTool("test_tool"))
        return registry

    @pytest.fixture
    def agent_definition(self):
        return AgentDefinition(
            agent_id="test_agent",
            capabilities=["testing"],
            requires_model=True,
            model_role="general",
            tools=["test_tool"],
            description="Test agent for SDK",
            system_prompt="You are a test agent.",
            task_processing="Process test tasks.",
            output_format="JSON",
            examples=None,
            temperature=0.7,
            max_tokens=1000,
            timeout=60,
        )

    def test_adapter_initialization(self, tool_registry):
        """Test adapter initializes correctly."""
        adapter = SDKAgentAdapter(tool_registry)
        assert adapter.tool_registry == tool_registry
        assert adapter._mcp_servers == {}

    def test_map_model_role(self, tool_registry):
        """Test model role mapping."""
        adapter = SDKAgentAdapter(tool_registry)

        assert adapter._map_model_role("general") == "sonnet"
        assert adapter._map_model_role("reasoning") == "opus"
        assert adapter._map_model_role("fast") == "haiku"
        assert adapter._map_model_role("unknown") == "sonnet"

    def test_build_default_prompt(self, tool_registry, agent_definition):
        """Test default prompt building."""
        adapter = SDKAgentAdapter(tool_registry)
        prompt = adapter._build_default_prompt(agent_definition)

        assert "Test agent for SDK" in prompt
        assert "Process test tasks" in prompt
        assert "JSON" in prompt

    def test_map_tool_names(self, tool_registry):
        """Test tool name mapping."""
        adapter = SDKAgentAdapter(tool_registry)

        tools = ["test_tool", "executor", "planner", "custom"]
        mapped = adapter._map_tool_names(tools)

        assert "test_tool" in mapped
        assert "Executor" in mapped
        assert "Planner" in mapped
        assert "custom" in mapped

    @pytest.mark.asyncio
    async def test_execute_without_sdk_installed(self, tool_registry, agent_definition):
        """Test execute fails gracefully when SDK not installed."""
        adapter = SDKAgentAdapter(tool_registry)

        with patch.dict("sys.modules", {"claude_agent_sdk": None}):
            with pytest.raises(ImportError) as exc_info:
                await adapter.execute(agent_definition, "test task")

            assert "claude-agent-sdk is required" in str(exc_info.value)


# ============================================================================
# ToolBridge Tests
# ============================================================================


class TestToolBridge:
    """Tests for ToolBridge class."""

    @pytest.fixture
    def tool_registry(self):
        registry = MockToolRegistry()
        registry.register_tool(MockTool("tool1"))
        registry.register_tool(MockTool("tool2"))
        return registry

    def test_bridge_initialization(self, tool_registry):
        """Test bridge initializes correctly."""
        bridge = ToolBridge(tool_registry)
        assert bridge.tool_registry == tool_registry
        assert bridge._wrapped_tools == {}

    def test_to_sdk_tools_all(self, tool_registry):
        """Test converting all tools to SDK format."""
        bridge = ToolBridge(tool_registry)
        sdk_tools = bridge.to_sdk_tools()

        assert len(sdk_tools) == 2
        # Check that tools are cached
        assert len(bridge._wrapped_tools) == 2

    def test_to_sdk_tools_specific(self, tool_registry):
        """Test converting specific tools."""
        bridge = ToolBridge(tool_registry)
        sdk_tools = bridge.to_sdk_tools(["tool1"])

        assert len(sdk_tools) == 1
        assert "tool1" in bridge._wrapped_tools
        assert "tool2" not in bridge._wrapped_tools

    def test_get_tool_schema_for_sdk(self, tool_registry):
        """Test getting SDK-compatible schema."""
        bridge = ToolBridge(tool_registry)
        schema = bridge.get_tool_schema_for_sdk("tool1")

        assert schema["name"] == "tool1"
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"

    def test_list_bridgeable_tools(self, tool_registry):
        """Test listing bridgeable tools."""
        bridge = ToolBridge(tool_registry)
        tools = bridge.list_bridgeable_tools()

        assert "tool1" in tools
        assert "tool2" in tools

    @pytest.mark.asyncio
    async def test_execute_wrapped_tool_success(self, tool_registry):
        """Test successful tool execution wrapper."""
        bridge = ToolBridge(tool_registry)
        tool = tool_registry.get_tool("tool1")

        result = await bridge._execute_wrapped_tool(tool, {"input": "test"})

        assert result["is_error"] is False
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_execute_wrapped_tool_missing_param(self, tool_registry):
        """Test tool execution with missing required parameter."""
        bridge = ToolBridge(tool_registry)
        tool = tool_registry.get_tool("tool1")

        # Missing required 'input' parameter
        result = await bridge._execute_wrapped_tool(tool, {})

        # Tool should still execute (validation happens elsewhere)
        # but may return error depending on tool implementation


# ============================================================================
# Hooks Tests
# ============================================================================


class TestHooks:
    """Tests for SDK hooks."""

    @pytest.fixture
    def tool_registry(self):
        registry = MockToolRegistry()
        registry.register_tool(MockTool("test_tool"))
        return registry

    def test_build_hooks_default(self, tool_registry):
        """Test building default hooks configuration."""
        hooks = build_hooks(tool_registry=tool_registry)

        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert "UserPromptSubmit" in hooks

    def test_build_hooks_minimal(self):
        """Test building minimal hooks configuration."""
        hooks = get_minimal_hooks()

        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks

    def test_build_hooks_permissive(self):
        """Test building permissive hooks configuration."""
        hooks = get_permissive_hooks()

        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks

    @pytest.mark.asyncio
    async def test_log_tool_usage(self):
        """Test log_tool_usage hook."""
        from src.agents.hooks import HookContext
        from src.agents.hooks import log_tool_usage

        input_data = {"tool_name": "test_tool", "tool_input": {"arg": "value"}}
        context = HookContext(agent_id="test_agent")

        result = await log_tool_usage(input_data, "test-id", context)

        assert result == {}  # Should return empty dict to proceed

    @pytest.mark.asyncio
    async def test_concurrency_control(self):
        """Test ConcurrencyControl limits concurrent tasks."""
        control = ConcurrencyControl(max_concurrent=2)

        # Should allow first two Task calls
        result1 = await control.limit_task_calls({"tool_name": "Task"}, "id1", None)
        result2 = await control.limit_task_calls({"tool_name": "Task"}, "id2", None)

        assert result1 == {}
        assert result2 == {}

        # Should block third call
        result3 = await control.limit_task_calls({"tool_name": "Task"}, "id3", None)

        assert "hookSpecificOutput" in result3
        assert result3["hookSpecificOutput"]["permissionDecision"] == "deny"

        # Release a slot
        await control.release_task_slot("Task", "id1", None, None)

        # Should now allow another call
        result4 = await control.limit_task_calls({"tool_name": "Task"}, "id4", None)

        assert result4 == {}

    @pytest.mark.asyncio
    async def test_concurrency_control_non_task_tools(self):
        """Test ConcurrencyControl doesn't limit non-Task tools."""
        control = ConcurrencyControl(max_concurrent=1)

        # Non-Task tools should always be allowed
        for i in range(5):
            result = await control.limit_task_calls({"tool_name": "Read"}, f"id{i}",
                                                    None)
            assert result == {}


# ============================================================================
# MarkdownAgent SDK Mode Tests
# ============================================================================


class TestMarkdownAgentSDKMode:
    """Tests for MarkdownAgent with SDK mode."""

    @pytest.fixture
    def memory_manager(self):
        return MockMemoryManager()

    @pytest.fixture
    def tool_registry(self):
        registry = MockToolRegistry()
        registry.register_tool(MockTool("test_tool"))
        return registry

    @pytest.fixture
    def agent_definition(self):
        return AgentDefinition(
            agent_id="sdk_test_agent",
            capabilities=["testing"],
            requires_model=True,
            model_role="general",
            tools=["test_tool"],
            description="SDK test agent",
            system_prompt="You are an SDK test agent.",
            task_processing="Process tasks.",
            output_format="JSON",
            examples=None,
            temperature=None,
            max_tokens=None,
            timeout=None,
        )

    def test_agent_sdk_mode_initialization(self, memory_manager, tool_registry,
                                           agent_definition):
        """Test agent initializes with SDK mode."""
        agent = MarkdownAgent(
            definition=agent_definition,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=MagicMock(),
            use_sdk=True,
        )

        assert agent.use_sdk is True
        assert agent._sdk_adapter is not None

    def test_agent_legacy_mode_initialization(self, memory_manager, tool_registry,
                                              agent_definition):
        """Test agent initializes without SDK mode (legacy)."""
        agent = MarkdownAgent(
            definition=agent_definition,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=MagicMock(),
            use_sdk=False,
        )

        assert agent.use_sdk is False
        assert agent._sdk_adapter is None

    @pytest.mark.asyncio
    async def test_process_task_legacy_mode(self, memory_manager, tool_registry,
                                            agent_definition):
        """Test process_task uses legacy mode when use_sdk=False."""
        agent = MarkdownAgent(
            definition=agent_definition,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=MagicMock(),
            use_sdk=False,
        )

        # Mock the legacy method
        agent._process_llm_task = AsyncMock(return_value={"status": "success"})

        result = await agent.process_task({"text": "test"})

        agent._process_llm_task.assert_called_once()
        assert result["status"] == "success"


# ============================================================================
# MarkdownAgentFactory SDK Tests
# ============================================================================


class TestMarkdownAgentFactorySDK:
    """Tests for MarkdownAgentFactory SDK features."""

    @pytest.fixture
    def factory(self, tmp_path):
        # Create a temp config directory with a test agent
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        agent_md = config_dir / "test_agent.md"
        agent_md.write_text("""
<!--
@agent_id: test_agent
@capabilities: testing
@requires_model: true
@model_role: general
@tools: test_tool
-->

## Agent Description
Test agent for SDK testing.

## System Prompt
You are a test agent.

## Task Processing
Process test tasks.

## Output Format
JSON
""")

        from src.agents.markdown_agent import MarkdownAgentFactory
        return MarkdownAgentFactory(config_dir)

    def test_create_agent_with_sdk_mode(self, factory):
        """Test creating agent with SDK mode enabled."""
        memory_manager = MockMemoryManager()
        tool_registry = MockToolRegistry()
        tool_registry.register_tool(MockTool("test_tool"))

        agent = factory.create_agent(
            "test_agent",
            memory_manager,
            tool_registry,
            model_manager=MagicMock(),
            use_sdk=True,
        )

        assert agent.use_sdk is True
        assert agent._sdk_adapter is not None

    def test_create_agent_with_delegation(self, factory):
        """Test creating agent with delegation enabled."""
        memory_manager = MockMemoryManager()
        tool_registry = MockToolRegistry()
        tool_registry.register_tool(MockTool("test_tool"))

        agent = factory.create_agent(
            "test_agent",
            memory_manager,
            tool_registry,
            model_manager=MagicMock(),
            enable_delegation=True,
        )

        assert "Task" in agent.definition.tools

    def test_create_agents_batch_with_sdk(self, factory):
        """Test creating multiple agents with SDK mode."""
        memory_manager = MockMemoryManager()
        tool_registry = MockToolRegistry()
        tool_registry.register_tool(MockTool("test_tool"))

        agents = factory.create_agents(
            ["test_agent"],
            memory_manager,
            tool_registry,
            model_manager=MagicMock(),
            use_sdk=True,
        )

        assert "test_agent" in agents
        assert agents["test_agent"].use_sdk is True

    def test_get_sdk_agent_definitions(self, factory):
        """Test getting SDK agent definitions for delegation."""
        # This test will skip if SDK not installed
        try:
            from claude_agent_sdk import AgentDefinition as SDKAgentDefinition
            sdk_defs = factory.get_sdk_agent_definitions(exclude_agent_ids=["other"])

            # Should have test_agent definition
            assert "test_agent" in sdk_defs

        except ImportError:
            # Expected behavior when SDK not installed
            sdk_defs = factory.get_sdk_agent_definitions(exclude_agent_ids=["other"])
            assert sdk_defs == {}  # Should return empty dict when SDK not installed


# ============================================================================
# Integration Tests (require SDK installed)
# ============================================================================


@pytest.mark.skipif(
    True,  # Skip by default - enable when SDK is installed
    reason="Requires claude-agent-sdk to be installed")
class TestSDKIntegration:
    """Integration tests that require actual SDK installation."""

    @pytest.mark.asyncio
    async def test_full_sdk_execution(self):
        """Test full execution flow with SDK."""
        # This test would verify:
        # 1. Tool bridge creates MCP server
        # 2. SDK client executes with tools
        # 3. Results are properly aggregated
        pass
