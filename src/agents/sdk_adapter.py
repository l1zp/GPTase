"""Adapter between GPTase agent definitions and Claude Agent SDK.

This module provides a minimal integration layer that converts GPTase's
Markdown-based agent definitions to Claude Agent SDK compatible configuration.

The adapter is intentionally kept minimal — the actual SDK API integration
should be implemented when the SDK is installed and ready to use.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SDKAgentAdapter:
    """Converts GPTase AgentDefinition to SDK-compatible configuration.

    This adapter bridges the gap between GPTase's Markdown-based agent
    definitions and Claude Agent SDK's execution model.

    Usage:
        adapter = SDKAgentAdapter(tool_registry)
        result = await adapter.execute(agent_def, "task prompt")
    """

    def __init__(self, tool_registry, model_manager=None):
        """Initialize the SDK adapter.

        Args:
            tool_registry: GPTase ToolRegistry instance.
            model_manager: Optional ModelManager for LLM operations.
        """
        self.tool_registry = tool_registry
        self.model_manager = model_manager
        self._tool_bridge = None

    async def execute(
        self,
        agent_def: "AgentDefinition",
        task: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute agent using Claude Agent SDK.

        Args:
            agent_def: GPTase agent definition.
            task: Task prompt for the agent.
            context: Optional execution context.

        Returns:
            Dictionary with status and result/error.
        """
        try:
            # Lazy import SDK
            from claude_code_sdk import Agent

            # Create tool bridge and MCP server
            mcp_servers = []
            if agent_def.tools and self.tool_registry:
                from src.agents.tool_bridge import ToolBridge
                if self._tool_bridge is None:
                    self._tool_bridge = ToolBridge(self.tool_registry)
                mcp_servers = self._tool_bridge.create_mcp_servers(agent_def.tools)

            # Build system prompt
            prompt_parts = []
            if agent_def.system_prompt:
                prompt_parts.append(agent_def.system_prompt)
            if agent_def.task_processing:
                prompt_parts.append(agent_def.task_processing)
            if agent_def.output_format:
                prompt_parts.append(agent_def.output_format)
            system_prompt = "\n\n".join(prompt_parts)

            # Create and run SDK agent
            agent = Agent(
                system_prompt=system_prompt,
                tools=self._tool_bridge.to_sdk_tools(agent_def.tools)
                if agent_def.tools else [],
                mcp_servers=mcp_servers,
            )
            result = await agent.run(task)

            return {
                "status": "success",
                "data": {
                    "content": result
                },
                "agent_id": agent_def.agent_id,
            }

        except ImportError:
            raise ImportError("Claude Agent SDK not installed. "
                              "Install with: pip install claude-code-sdk") from None
        except Exception as e:
            logger.error(f"SDK execution failed for {agent_def.agent_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "agent_id": agent_def.agent_id,
            }
