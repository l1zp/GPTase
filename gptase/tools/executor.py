"""Executor for per-batch tool calls in the interactive runtime."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from gptase.tools.base import get_tool_registry

logger = logging.getLogger(__name__)

# Tools whose output is explicitly scoped by the caller (Read takes
# offset/limit) should not be truncated again at the executor layer —
# silently clipping a deliberate file read undermines the slice
# semantics the agent already controlled. Unbounded tools like Bash,
# Grep, WebFetch are still subject to max_tool_result_chars.
_TRUNCATE_EXEMPT_TOOLS = frozenset({"Read"})


class ToolExecutor:
    """Executes a batch of tool calls for AgentRuntime."""

    def __init__(
        self,
        agent_id: str = "",
        max_iterations: int = 10,
        max_tool_result_chars: int = 8000,
    ):
        """Initialize the ToolExecutor.

        Args:
            agent_id: Identifier of the agent running this executor
                (used for permission checks).
            max_iterations: Maximum number of tool call iterations
                accepted by the surrounding runtime; informational here.
            max_tool_result_chars: Maximum characters from each tool
                result fed back into the next model turn — longer results
                are truncated by ``_truncate_tool_result``.
        """
        self.agent_id = agent_id
        self.max_iterations = max_iterations
        self.max_tool_result_chars = max_tool_result_chars
        self.registry = get_tool_registry()
        self.logger = logging.getLogger(
            f"{__name__}.{self.agent_id}" if self.agent_id else __name__)

    async def execute_calls(
        self,
        tool_calls: List[Any],
        messages: List[Dict[str, Any]],
        iteration: int,
    ) -> Dict[str, Any]:
        """Execute one batch of tool calls and append tool messages."""
        self.logger.info(
            "Iteration %d: Received %d tool calls",
            iteration,
            len(tool_calls),
        )

        if len(tool_calls) > 1:
            self.logger.info(
                "Executing %d tools in parallel",
                len(tool_calls),
            )

        async def _timed_tool_call(tc):
            import time
            start = time.monotonic()
            result = await self._execute_single_tool(tc)
            ms = int((time.monotonic() - start) * 1000)
            result["duration_ms"] = ms
            return result

        results = await asyncio.gather(*[_timed_tool_call(tc) for tc in tool_calls])

        tool_results: List[Dict[str, Any]] = []
        steps: List[Dict[str, Any]] = []
        has_invalid_tool_arguments = False
        for tool_call, tool_result in zip(tool_calls, results):
            result_str = tool_result["raw_result"]
            stored_result = self._truncate_tool_result(tool_call.name, result_str)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": stored_result,
            })

            args = tool_result["arguments"]
            if tool_result["error_type"] == "invalid_arguments":
                has_invalid_tool_arguments = True

            step = {
                "type": "tool_call",
                "iteration": iteration,
                "tool_name": tool_call.name,
                "arguments": args,
                "result_preview": stored_result[:300],
                "result_chars": len(result_str),
                "stored_result_chars": len(stored_result),
                "result_truncated": stored_result != result_str,
                "duration_ms": tool_result["duration_ms"],
            }
            steps.append(step)
            # Store the FULL result (untruncated) in the trace tool_results.
            # The LLM-facing message above gets the truncated form; the trace
            # gets the full form so downstream consumers (e.g.
            # _build_coordinator_summary's json.loads) can parse the
            # complete payload of large DelegateTask results.
            tool_results.append({
                "tool_name": tool_call.name,
                "arguments": args,
                "content": result_str,
                "error_type": tool_result["error_type"],
            })

        return {
            "messages": messages,
            "tool_results": tool_results,
            "steps": steps,
            "has_invalid_tool_arguments": has_invalid_tool_arguments,
        }

    async def _execute_single_tool(self, tool_call: Any) -> Dict[str, Any]:
        """Safely execute a single tool call, returning structured metadata."""
        tool = self.registry.get(tool_call.name)

        if tool is None:
            self.logger.warning("Unknown tool requested: %s", tool_call.name)
            return {
                "raw_result": f"[ERROR] Unknown tool: {tool_call.name}",
                "arguments": {},
                "error_type": "unknown_tool",
            }

        if not self.registry.is_allowed(tool_call.name, self.agent_id):
            self.logger.warning(
                "Tool '%s' not allowed for agent '%s'",
                tool_call.name,
                self.agent_id,
            )
            return {
                "raw_result":
                f"[ERROR] Tool '{tool_call.name}' not allowed for this agent",
                "arguments": {},
                "error_type": "not_allowed",
            }

        try:
            args = json.loads(tool_call.arguments)
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse tool arguments: %s",
                tool_call.arguments,
            )
            return {
                "raw_result": f"[ERROR] Invalid tool arguments: {e}",
                "arguments": {},
                "error_type": "invalid_arguments",
            }

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
            return {
                "raw_result": str(result),
                "arguments": args,
                "error_type": None,
            }
        except Exception as e:
            self.logger.exception(
                "Tool '%s' execution failed",
                tool_call.name,
            )
            return {
                "raw_result": f"[ERROR] Tool execution failed: {e}",
                "arguments": args,
                "error_type": "execution_failed",
            }

    def _truncate_tool_result(self, tool_name: str, result: str) -> str:
        if tool_name in _TRUNCATE_EXEMPT_TOOLS:
            return result
        if len(result) <= self.max_tool_result_chars:
            return result

        prefix = (
            "[TOOL OUTPUT TRUNCATED]\n"
            f"Tool `{tool_name}` returned {len(result)} chars, which exceeds the "
            f"{self.max_tool_result_chars}-char limit for follow-up model turns.\n"
            "Only the beginning and end are kept below.\n"
            "If more detail is needed, rerun the tool with a narrower scope.\n\n")

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
