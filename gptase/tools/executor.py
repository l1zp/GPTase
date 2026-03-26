"""Executor for LLM tool loops.

This module provides the ToolExecutor class which manages the interaction
between an LLM model and a set of tools, handling the multi-turn conversation
required for tool execution.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from gptase.models.model import Model
from gptase.tools.base import get_tool_registry

logger = logging.getLogger(__name__)


def _message_content_chars(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        else:
            total += len(json.dumps(content, ensure_ascii=False, default=str))
    return total


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
        step_id: Optional[str] = None,
        max_iterations: int = 10,
        max_tool_result_chars: int = 8000,
        mcp_server_configs: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the ToolExecutor.

        Args:
            model: The initialized Model instance to use for generation.
            agent_id: Identifier of the agent running this executor (used for permissions).
            max_iterations: Maximum number of tool call iterations to allow.
            max_tool_result_chars: Maximum number of characters from each tool result
                                   to feed back into the next model turn.
            mcp_server_configs: Optional mapping of server name -> McpServerConfig for
                                 MCP tool integration. Tools are registered before the
                                 first iteration and disconnected after execute() returns.
        """
        self.model = model
        self.agent_id = agent_id
        self.step_id = step_id
        self.max_iterations = max_iterations
        self.max_tool_result_chars = max_tool_result_chars
        self.mcp_server_configs = mcp_server_configs or {}
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
        try:
            # Connect to MCP servers and register their tools before the loop
            if self.mcp_server_configs:
                await self.registry.ensure_mcp_connected(self.mcp_server_configs)

            # Get tool schemas for requested tools
            tool_schemas = self.registry.get_schemas(tools) if tools else None

            if tool_schemas:
                self.logger.info(
                    "Executor running with %d tools available: %s",
                    len(tool_schemas),
                    tools,
                )

            # Trajectory tracking (reset each call)
            self._steps: List[Dict[str, Any]] = []
            total_start = time.monotonic()
            total_input_tokens = 0
            total_output_tokens = 0

            for iteration in range(1, self.max_iterations + 1):
                iter_start = time.monotonic()
                response = await self.model.generate(
                    messages,
                    config=self.model.default_config,
                    tools=tool_schemas,
                    agent_id=self.agent_id or None,
                    step_id=self.step_id,
                )
                iter_ms = int((time.monotonic() - iter_start) * 1000)

                # Accumulate token usage
                total_input_tokens += response.usage.get("prompt_tokens", 0)
                total_output_tokens += response.usage.get("completion_tokens", 0)

                # Record LLM call step
                self._steps.append({
                    "type": "llm_call",
                    "iteration": iteration,
                    "message_count": len(messages),
                    "message_content_chars": _message_content_chars(messages),
                    "content_preview": (response.content or "")[:500],
                    "tool_calls_requested": [
                        {"name": tc.name, "arguments": tc.arguments}
                        for tc in (response.tool_calls or [])
                    ],
                    "usage": dict(response.usage),
                    "duration_ms": iter_ms,
                })

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
                        "trace": {
                            "steps": self._steps,
                            "total_input_tokens": total_input_tokens,
                            "total_output_tokens": total_output_tokens,
                            "total_duration_ms": int(
                                (time.monotonic() - total_start) * 1000
                            ),
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
                "trace": {
                    "steps": self._steps,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_duration_ms": int((time.monotonic() - total_start) * 1000),
                },
            }
        finally:
            if self.mcp_server_configs:
                await self.registry.disconnect_mcp()

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

        # Execute all tool calls in parallel with timing
        if len(response.tool_calls) > 1:
            self.logger.info(
                "Executing %d tools in parallel",
                len(response.tool_calls),
            )

        async def _timed_tool_call(tc):
            start = time.monotonic()
            result_str = await self._execute_single_tool(tc)
            ms = int((time.monotonic() - start) * 1000)
            return result_str, ms

        pairs = await asyncio.gather(
            *[_timed_tool_call(tc) for tc in response.tool_calls]
        )

        # Build tool result messages and record trajectory steps
        for tool_call, (result_str, tool_ms) in zip(response.tool_calls, pairs):
            stored_result = self._truncate_tool_result(tool_call.name, result_str)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": stored_result,
            })
            try:
                args = json.loads(tool_call.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {"raw": tool_call.arguments}
            self._steps.append({
                "type": "tool_call",
                "iteration": iteration,
                "tool_name": tool_call.name,
                "arguments": args,
                "result_preview": stored_result[:300],
                "result_chars": len(result_str),
                "stored_result_chars": len(stored_result),
                "result_truncated": stored_result != result_str,
                "duration_ms": tool_ms,
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

    def _truncate_tool_result(self, tool_name: str, result: str) -> str:
        if len(result) <= self.max_tool_result_chars:
            return result

        prefix = (
            "[TOOL OUTPUT TRUNCATED]\n"
            f"Tool `{tool_name}` returned {len(result)} chars, which exceeds the "
            f"{self.max_tool_result_chars}-char limit for follow-up model turns.\n"
            "Only the beginning and end are kept below.\n"
            "If more detail is needed, rerun the tool with a narrower scope.\n\n"
        )

        head_chars = 0
        tail_chars = 0
        marker = ""
        available = max(self.max_tool_result_chars - len(prefix), 0)

        if available > 0:
            head_chars = max((available * 2) // 3, 1)
            tail_chars = max(available - head_chars, 0)
            omitted = max(len(result) - head_chars - tail_chars, 0)
            marker = f"\n\n[... omitted {omitted} chars ...]\n\n"

            available = max(
                self.max_tool_result_chars - len(prefix) - len(marker),
                0,
            )
            head_chars = max((available * 2) // 3, 1)
            tail_chars = max(available - head_chars, 0)
            omitted = max(len(result) - head_chars - tail_chars, 0)
            marker = f"\n\n[... omitted {omitted} chars ...]\n\n"

        truncated = prefix + result[:head_chars] + marker
        if tail_chars:
            truncated += result[-tail_chars:]

        if len(truncated) > self.max_tool_result_chars:
            truncated = truncated[:self.max_tool_result_chars]

        self.logger.warning(
            "Truncated tool '%s' output from %d to %d chars",
            tool_name,
            len(result),
            len(truncated),
        )
        return truncated
