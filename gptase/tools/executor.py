"""Executor for LLM tool loops.

This module provides the ToolExecutor class which manages the interaction
between an LLM model and a set of tools, handling the multi-turn conversation
required for tool execution.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from gptase.models.model import Model
from gptase.tools.base import get_tool_registry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes a multi-turn LLM loop with tool calling support.

    Manages the conversation state, parsing of tool calls, execution of
    registered tools, and feeding results back to the LLM until a final
    response is generated or max iterations are reached.
    """

    def __init__(
        self,
        model: Model,
        agent_id: str = "",
        max_iterations: int = 10,
    ):
        """Initialize the ToolExecutor.

        Args:
            model: The initialized Model instance to use for generation.
            agent_id: Identifier of the agent running this executor (used for permissions).
            max_iterations: Maximum number of tool call iterations to allow.
        """
        self.model = model
        self.agent_id = agent_id
        self.max_iterations = max_iterations
        self.registry = get_tool_registry()
        self.logger = logging.getLogger(
            f"{__name__}.{self.agent_id}" if self.agent_id else __name__)

    async def execute(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the tool execution loop until completion or max iterations.

        Args:
            messages: The initial conversation messages. This list will be modified
                     in-place during execution to append tool calls and results.
            tools: Optional list of tool names the LLM is allowed to use.

        Returns:
            Result dictionary containing status, content, and metadata.
        """
        # Get tool schemas for requested tools
        tool_schemas = self.registry.get_schemas(tools) if tools else None

        if tool_schemas:
            self.logger.info(
                "Executor running with %d tools available: %s",
                len(tool_schemas),
                tools,
            )

        for iteration in range(1, self.max_iterations + 1):
            response = await self.model.generate(
                messages,
                config=self.model.default_config,
                tools=tool_schemas,
            )

            # Check if we have tool calls
            if not response.tool_calls:
                # No tool calls - we have a final response
                self.logger.info(
                    "Execution completed after %d iterations",
                    iteration,
                )
                return {
                    "status": "success",
                    "data": {
                        "content": response.content,
                        "reasoning": response.reasoning_content,
                        "usage": response.usage,
                        "iterations": iteration,
                    },
                }

            await self._handle_tool_calls(response, messages, iteration)

        # Max iterations reached
        self.logger.warning(
            "Executor reached max iterations (%d)",
            self.max_iterations,
        )
        return {
            "status": "error",
            "error": "Maximum tool iterations reached",
            "data": {
                "content": response.content,
                "iterations": self.max_iterations,
            },
        }

    async def _handle_tool_calls(
        self,
        response: Any,
        messages: List[Dict[str, Any]],
        iteration: int,
    ) -> None:
        """Process all tool calls from the LLM and append results to messages."""
        self.logger.info(
            "Iteration %d: Received %d tool calls",
            iteration,
            len(response.tool_calls),
        )

        # Build assistant message with tool calls
        assistant_message: Dict[str, Any] = {
            "role": "assistant",
            "content": response.content,
        }

        # Add tool_calls field for OpenAI format
        assistant_message["tool_calls"] = [{
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.name,
                "arguments": tc.arguments,
            },
        } for tc in response.tool_calls]
        messages.append(assistant_message)

        # Execute all tool calls in parallel
        if len(response.tool_calls) > 1:
            self.logger.info(
                "Executing %d tools in parallel",
                len(response.tool_calls),
            )

        results = await asyncio.gather(
            *[self._execute_single_tool(tc) for tc in response.tool_calls], )

        # Build tool result messages in original order
        for tool_call, result in zip(response.tool_calls, results):
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    async def _execute_single_tool(self, tool_call: Any) -> str:
        """Safely execute a single tool call, returning the string result or error message."""
        tool = self.registry.get(tool_call.name)

        if tool is None:
            self.logger.warning("Unknown tool requested: %s", tool_call.name)
            return f"[ERROR] Unknown tool: {tool_call.name}"

        if not self.registry.is_allowed(tool_call.name, self.agent_id):
            self.logger.warning(
                "Tool '%s' not allowed for agent '%s'",
                tool_call.name,
                self.agent_id,
            )
            return f"[ERROR] Tool '{tool_call.name}' not allowed for this agent"

        # Parse arguments
        try:
            args = json.loads(tool_call.arguments)
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse tool arguments: %s",
                tool_call.arguments,
            )
            return f"[ERROR] Invalid tool arguments: {e}"

        self.logger.info(
            "Executing tool '%s' with args: %s",
            tool_call.name,
            args,
        )

        try:
            result = await tool.execute(**args)

            self.logger.debug(
                "Tool '%s' result (first 200 chars): %s",
                tool_call.name,
                str(result)[:200] if result else "",
            )
            return str(result)
        except Exception as e:
            self.logger.exception(
                "Tool '%s' execution failed",
                tool_call.name,
            )
            return f"[ERROR] Tool execution failed: {e}"
