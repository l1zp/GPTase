"""Adapter between GPTase agent definitions and Claude Agent SDK.

This module provides the integration layer that converts GPTase's Markdown-based
agent definitions to Claude Agent SDK compatible configuration, enabling SDK
execution while preserving the Markdown configuration advantage.
"""

import logging
from typing import Any, Dict, List, Optional

from src.agents.markdown_agent import AgentDefinition

logger = logging.getLogger(__name__)

# Type alias for SDK types (imported lazily to avoid hard dependency)
SDKAgentDefinition = None
ClaudeAgentOptions = None
ClaudeSDKClient = None
HookMatcher = None
create_sdk_mcp_server = None


def _ensure_sdk_imports():
    """Lazily import SDK types to avoid hard dependency errors."""
    global SDKAgentDefinition, ClaudeAgentOptions, ClaudeSDKClient
    global HookMatcher, create_sdk_mcp_server

    if SDKAgentDefinition is None:
        try:
            from claude_agent_sdk import AgentDefinition as SDKAgentDefinition
            from claude_agent_sdk import ClaudeAgentOptions
            from claude_agent_sdk import ClaudeSDKClient
            from claude_agent_sdk import create_sdk_mcp_server
            from claude_agent_sdk import HookMatcher

            # Store in globals for later use
            globals()['SDKAgentDefinition'] = SDKAgentDefinition
            globals()['ClaudeAgentOptions'] = ClaudeAgentOptions
            globals()['ClaudeSDKClient'] = ClaudeSDKClient
            globals()['HookMatcher'] = HookMatcher
            globals()['create_sdk_mcp_server'] = create_sdk_mcp_server
        except ImportError as e:
            raise ImportError("claude-agent-sdk is required for SDK execution mode. "
                              "Install it with: pip install claude-agent-sdk") from e

    return SDKAgentDefinition, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher, create_sdk_mcp_server


class SDKAgentAdapter:
    """Converts GPTase AgentDefinition to SDK-compatible configuration.

    This adapter bridges the gap between GPTase's Markdown-based agent
    definitions and Claude Agent SDK's execution model. It handles:
    - Converting agent definitions to SDK format
    - Creating SDK options with proper configuration
    - Managing tool bridges and MCP servers
    - Executing agents via SDK's built-in agent loop

    Attributes:
        tool_registry: GPTase ToolRegistry instance for tool access.
        model_manager: Optional ModelManager for LLM operations.
        _mcp_servers: Cache of created MCP servers.
    """

    def __init__(self, tool_registry, model_manager=None):
        """Initialize the SDK adapter.

        Args:
            tool_registry: GPTase ToolRegistry instance.
            model_manager: Optional ModelManager for LLM operations.
        """
        self.tool_registry = tool_registry
        self.model_manager = model_manager
        self._mcp_servers: Dict[str, Any] = {}
        self._tool_bridge = None

    def convert_definition(self, gptase_def: AgentDefinition) -> "SDKAgentDefinition":
        """Convert GPTase AgentDefinition to SDK AgentDefinition.

        Args:
            gptase_def: GPTase agent definition from Markdown.

        Returns:
            SDK-compatible AgentDefinition instance.
        """
        SDKAgentDefinition, _, _, _, _ = _ensure_sdk_imports()

        # Map GPTase tools to SDK tool names
        sdk_tools = self._map_tool_names(gptase_def.tools)

        # Map model role to SDK model name
        model = self._map_model_role(gptase_def.model_role)

        # Build SDK definition
        return SDKAgentDefinition(
            description=gptase_def.description or f"Agent {gptase_def.agent_id}",
            prompt=gptase_def.system_prompt or self._build_default_prompt(gptase_def),
            tools=sdk_tools,
            model=model,
        )

    def create_options(
        self,
        agent_def: AgentDefinition,
        hooks: Optional[Dict[str, List]] = None,
        mcp_servers: Optional[Dict[str, Any]] = None,
    ) -> "ClaudeAgentOptions":
        """Create SDK options from agent definition.

        Args:
            agent_def: GPTase agent definition.
            hooks: Optional SDK hooks configuration.
            mcp_servers: Optional pre-configured MCP servers.

        Returns:
            ClaudeAgentOptions instance ready for SDK use.
        """
        _, ClaudeAgentOptions, _, HookMatcher, _ = _ensure_sdk_imports()

        # Build allowed tools list
        allowed_tools = self._build_allowed_tools(agent_def.tools, mcp_servers)

        # Convert hooks to SDK format
        sdk_hooks = self._convert_hooks(hooks) if hooks else None

        # Build options
        options = ClaudeAgentOptions(
            system_prompt=agent_def.system_prompt,
            allowed_tools=allowed_tools,
            max_turns=50,  # Reasonable default
            hooks=sdk_hooks,
            mcp_servers=mcp_servers,
        )

        # Apply temperature and max_tokens if specified
        if agent_def.temperature is not None:
            options.temperature = agent_def.temperature
        if agent_def.max_tokens is not None:
            options.max_tokens = agent_def.max_tokens

        return options

    async def execute(
        self,
        agent_def: AgentDefinition,
        task: str,
        context: Optional[Dict] = None,
        hooks: Optional[Dict[str, List]] = None,
    ) -> Dict[str, Any]:
        """Execute agent using Claude Agent SDK.

        This method handles the full execution cycle:
        1. Create tool bridge and MCP server for GPTase tools
        2. Configure SDK options
        3. Run the SDK agent loop
        4. Collect and return results

        Args:
            agent_def: GPTase agent definition.
            task: Task prompt for the agent.
            context: Optional execution context.
            hooks: Optional SDK hooks.

        Returns:
            Dictionary with status and result data.
        """
        _, _, ClaudeSDKClient, _, create_sdk_mcp_server = _ensure_sdk_imports()

        try:
            # Create tool bridge and MCP server
            mcp_servers = {}
            if agent_def.tools and self.tool_registry:
                mcp_servers = await self._create_mcp_servers(agent_def.tools)

            # Create SDK options
            options = self.create_options(agent_def,
                                          hooks=hooks,
                                          mcp_servers=mcp_servers)

            # Execute via SDK client
            results = []
            async with ClaudeSDKClient(options=options) as client:
                await client.query(task)

                # Collect response messages
                async for msg in client.receive_response():
                    results.append(self._process_sdk_message(msg))

            # Aggregate results
            return {
                "status": "success",
                "data": self._aggregate_results(results),
                "agent_id": agent_def.agent_id,
            }

        except Exception as e:
            logger.error(f"SDK execution failed for {agent_def.agent_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "agent_id": agent_def.agent_id,
            }

    def _build_default_prompt(self, gptase_def: AgentDefinition) -> str:
        """Build default prompt from agent definition components.

        Args:
            gptase_def: GPTase agent definition.

        Returns:
            Combined prompt string.
        """
        parts = []

        if gptase_def.description:
            parts.append(gptase_def.description)

        if gptase_def.task_processing:
            parts.append(f"\nTask Processing:\n{gptase_def.task_processing}")

        if gptase_def.output_format:
            parts.append(f"\nOutput Format:\n{gptase_def.output_format}")

        return "\n".join(parts) if parts else f"You are {gptase_def.agent_id}."

    def _map_tool_names(self, gptase_tools: List[str]) -> List[str]:
        """Map GPTase tool names to SDK tool names.

        Some tools may have different names or need special handling.

        Args:
            gptase_tools: List of GPTase tool names.

        Returns:
            List of SDK-compatible tool names.
        """
        # Most tools map directly, but we handle special cases
        tool_mapping = {
            "executor": "Executor",
            "planner": "Planner",
        }

        return [tool_mapping.get(t, t) for t in gptase_tools]

    def _map_model_role(self, model_role: str) -> str:
        """Map GPTase model role to SDK model name.

        Args:
            model_role: GPTase model role (e.g., 'general', 'reasoning').

        Returns:
            SDK model name (e.g., 'sonnet', 'opus', 'haiku').
        """
        role_mapping = {
            "general": "sonnet",
            "reasoning": "opus",
            "fast": "haiku",
            "default": "sonnet",
        }

        return role_mapping.get(model_role.lower(), "sonnet")

    def _build_allowed_tools(
        self,
        tools: List[str],
        mcp_servers: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Build the full allowed tools list including MCP tools.

        Args:
            tools: List of GPTase tool names.
            mcp_servers: Optional MCP servers dict.

        Returns:
            Complete list of allowed tool names.
        """
        allowed = list(tools)

        # Add MCP tool names (format: mcp__{server}__{tool})
        if mcp_servers:
            for server_name in mcp_servers:
                # SDK will handle MCP tool naming
                pass

        return allowed

    def _convert_hooks(self, hooks: Dict[str, List]) -> Dict[str, List]:
        """Convert GPTase hooks to SDK HookMatcher format.

        Args:
            hooks: Dictionary mapping hook event names to hook functions.

        Returns:
            SDK-compatible hooks dictionary.
        """
        _, _, _, HookMatcher, _ = _ensure_sdk_imports()

        sdk_hooks = {}

        for event_name, hook_list in hooks.items():
            matchers = []
            for hook in hook_list:
                if isinstance(hook, dict):
                    # Already in matcher format
                    matchers.append(HookMatcher(**hook))
                elif callable(hook):
                    # Simple function - wrap in default matcher
                    matchers.append(HookMatcher(hooks=[hook]))
                else:
                    logger.warning(f"Unknown hook format: {type(hook)}")

            sdk_hooks[event_name] = matchers

        return sdk_hooks

    async def _create_mcp_servers(self, tools: List[str]) -> Dict[str, Any]:
        """Create MCP servers for GPTase tools.

        Args:
            tools: List of tool names to bridge.

        Returns:
            Dictionary of MCP server name to server instance.
        """
        _, _, _, _, create_sdk_mcp_server = _ensure_sdk_imports()

        # Import tool bridge here to avoid circular import
        from src.agents.tool_bridge import ToolBridge

        if self._tool_bridge is None:
            self._tool_bridge = ToolBridge(self.tool_registry)

        # Get SDK-compatible tool functions
        sdk_tools = self._tool_bridge.to_sdk_tools(tools)

        if not sdk_tools:
            return {}

        # Create single MCP server for all GPTase tools
        server = create_sdk_mcp_server(
            name="gptase-tools",
            version="1.0.0",
            tools=sdk_tools,
        )

        return {"gptase": server}

    def _process_sdk_message(self, message: Any) -> Dict[str, Any]:
        """Process an SDK message into a standard format.

        Args:
            message: SDK message object.

        Returns:
            Processed message dictionary.
        """
        result = {"type": type(message).__name__}

        # Handle different message types
        if hasattr(message, "content"):
            content = message.content
            if isinstance(content, list):
                result["content"] = [{
                    "type": type(block).__name__,
                    "text": getattr(block, "text", str(block))
                } for block in content]
            else:
                result["content"] = str(content)

        if hasattr(message, "result"):
            result["result"] = message.result

        return result

    def _aggregate_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Aggregate SDK execution results.

        Args:
            results: List of processed SDK messages.

        Returns:
            Aggregated result dictionary.
        """
        # Extract text content
        text_content = []
        tool_results = []
        final_result = None

        for r in results:
            if r.get("type") == "AssistantMessage":
                content = r.get("content", [])
                for block in content:
                    if block.get("type") == "TextBlock":
                        text_content.append(block.get("text", ""))
            elif r.get("result"):
                final_result = r["result"]
            elif "tool_result" in r:
                tool_results.append(r["tool_result"])

        return {
            "text": "\n".join(text_content) if text_content else None,
            "tool_results": tool_results if tool_results else None,
            "final_result": final_result,
        }
