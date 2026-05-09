"""Interactive runtime for non-Claude agent execution."""

from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from gptase.agents.runtime_types import CoordinatorRuntimeSummary
from gptase.agents.runtime_types import CoordinatorTurnSummary
from gptase.agents.runtime_types import CoordinatorWorkerResult
from gptase.agents.runtime_types import InteractiveRuntimeResult
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.runtime_types import InteractiveSessionState
from gptase.agents.runtime_types import InteractiveToolResult
from gptase.agents.runtime_types import InteractiveTurn
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.models.model import Model
from gptase.tools.base import get_tool_registry
from gptase.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

TurnCallback = Callable[[InteractiveRuntimeSnapshot, InteractiveTurn], Any]


def _message_content_chars(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        else:
            total += len(str(content))
    return total


class AgentRuntime:
    """Owns the turn loop for non-Claude agents."""

    def __init__(
        self,
        model: Model,
        agent_id: str = "",
        max_turns: int = 10,
        max_tool_result_chars: int = 8000,
        mcp_server_configs: Optional[Dict[str, Any]] = None,
    ):
        self.model = model
        self.agent_id = agent_id
        self.max_turns = max_turns
        self.max_tool_result_chars = max_tool_result_chars
        self.mcp_server_configs = mcp_server_configs or {}
        self.registry = get_tool_registry()
        self.tool_executor = ToolExecutor(
            model=model,
            agent_id=agent_id,
            max_iterations=max_turns,
            max_tool_result_chars=max_tool_result_chars,
            mcp_server_configs=mcp_server_configs,
        )
        self.logger = logging.getLogger(
            f"{__name__}.{self.agent_id}" if self.agent_id else __name__)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        allowed_tools: Optional[List[str]] = None,
        max_turns: Optional[int] = None,
        resume_snapshot: Optional[Dict[str, Any]] = None,
        on_turn_complete: Optional[TurnCallback] = None,
    ) -> InteractiveRuntimeResult:
        tool_schemas = self.registry.get_schemas(
            allowed_tools) if allowed_tools else None
        state = self._build_initial_state(messages, max_turns, resume_snapshot)
        last_content = ""
        last_reasoning = None
        last_usage: Dict[str, int] = {}

        async with self.registry.mcp_connected(self.mcp_server_configs):
            stop_reason: Optional[RuntimeStopReason] = None
            error: Optional[str] = None

            while not stop_reason and state.turn_index < state.max_turns:
                iteration = state.turn_index + 1
                turn_start = time.monotonic()

                response = await self.model.generate(
                    state.messages,
                    config=self.model.default_config,
                    tools=tool_schemas,
                    agent_id=self.agent_id or None,
                )

                llm_ms = int((time.monotonic() - turn_start) * 1000)
                state.total_input_tokens += response.usage.get("prompt_tokens", 0)
                state.total_output_tokens += response.usage.get("completion_tokens", 0)

                last_content = response.content or ""
                last_reasoning = response.reasoning_content
                last_usage = dict(response.usage)

                tool_call_payload = [{
                    "name": tc.name,
                    "arguments": tc.arguments,
                } for tc in (response.tool_calls or [])]
                state.steps.append({
                    "type":
                    "llm_call",
                    "iteration":
                    iteration,
                    "message_count":
                    len(state.messages),
                    "message_content_chars":
                    _message_content_chars(state.messages),
                    "content_preview":
                    last_content[:500],
                    "tool_calls_requested":
                    tool_call_payload,
                    "usage":
                    last_usage,
                    "duration_ms":
                    llm_ms,
                })

                if not response.tool_calls:
                    turn = InteractiveTurn(
                        turn_index=iteration,
                        assistant_content=last_content,
                        reasoning_content=last_reasoning,
                        stop_reason=RuntimeStopReason.FINAL_ANSWER,
                    )
                    state.turns.append(turn)
                    state.turn_index = iteration
                    state.total_duration_ms += llm_ms
                    stop_reason = RuntimeStopReason.FINAL_ANSWER
                    break

                assistant_message: Dict[str, Any] = {
                    "role":
                    "assistant",
                    "content":
                    last_content,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    } for tc in response.tool_calls],
                }
                state.messages.append(assistant_message)

                tool_exec = await self.tool_executor.execute_calls(
                    response.tool_calls,
                    state.messages,
                    iteration,
                )
                state.steps.extend(tool_exec["steps"])

                state.total_duration_ms += int((time.monotonic() - turn_start) * 1000)
                turn = InteractiveTurn(
                    turn_index=iteration,
                    assistant_content=last_content,
                    reasoning_content=last_reasoning,
                    tool_results=[
                        InteractiveToolResult(**tool_result)
                        for tool_result in tool_exec["tool_results"]
                    ],
                )

                if tool_exec["has_invalid_tool_arguments"]:
                    turn.stop_reason = RuntimeStopReason.ERROR
                    state.turn_index = iteration
                    stop_reason = RuntimeStopReason.ERROR
                    error = "Interactive runtime stopped due to invalid tool arguments."
                    # fall through to shared turn recording + callback

                state.turns.append(turn)
                state.turn_index = iteration

                snapshot = self._snapshot_from_state(state)
                if on_turn_complete is not None:
                    maybe_awaitable = on_turn_complete(snapshot, turn)
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable

            # Single exit point
            if stop_reason is None:
                stop_reason = RuntimeStopReason.MAX_TURNS
                error = "Maximum tool iterations reached"

            return self._finalize_result(
                state=state,
                content=last_content,
                reasoning=last_reasoning,
                usage=last_usage,
                stop_reason=stop_reason,
                error=error,
            )

    def _build_initial_state(
        self,
        messages: List[Dict[str, Any]],
        max_turns: Optional[int],
        resume_snapshot: Optional[Dict[str, Any]],
    ) -> InteractiveSessionState:
        effective_max_turns = max_turns or self.max_turns
        if resume_snapshot:
            snapshot = InteractiveRuntimeSnapshot.model_validate(resume_snapshot)
            return InteractiveSessionState(
                **snapshot.model_dump(),
                turn_index=len(snapshot.turns),
                max_turns=effective_max_turns,
            )

        return InteractiveSessionState(
            messages=list(messages),
            max_turns=effective_max_turns,
        )

    def _snapshot_from_state(
        self,
        state: InteractiveSessionState,
    ) -> InteractiveRuntimeSnapshot:
        return InteractiveRuntimeSnapshot.model_validate(state.model_dump())

    def _finalize_result(
        self,
        *,
        state: InteractiveSessionState,
        content: str,
        reasoning: Optional[str],
        usage: Dict[str, int],
        stop_reason: RuntimeStopReason,
        error: Optional[str] = None,
    ) -> InteractiveRuntimeResult:
        snapshot = self._snapshot_from_state(state)
        coordinator_summary = self._build_coordinator_summary(state)
        return InteractiveRuntimeResult(
            content=content,
            reasoning=reasoning,
            stop_reason=stop_reason,
            turn_count=len(state.turns),
            usage=usage,
            snapshot=snapshot,
            error=error,
            coordinator_summary=coordinator_summary,
        )

    def _extract_json_object(self, content: str) -> str:
        content = content.strip()
        if content.startswith("{") or content.startswith("["):
            return content
        brace_start = content.find("{")
        if brace_start == -1:
            return content
        depth = 0
        for index in range(brace_start, len(content)):
            if content[index] == "{":
                depth += 1
            elif content[index] == "}":
                depth -= 1
                if depth == 0:
                    return content[brace_start:index + 1]
        return content

    def _build_coordinator_summary(
        self,
        state: InteractiveSessionState,
    ) -> Optional[CoordinatorRuntimeSummary]:
        turn_summaries: List[CoordinatorTurnSummary] = []
        worker_results: List[CoordinatorWorkerResult] = []
        delegated_agents: List[str] = []
        for turn in state.turns:
            turn_worker_results: List[CoordinatorWorkerResult] = []
            turn_delegated_agents: List[str] = []
            for tool_result in turn.tool_results:
                if tool_result.tool_name != "DelegateTask":
                    continue
                try:
                    payload = json.loads(self._extract_json_object(tool_result.content))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                agent_id = str(payload.get("agent_id") or "").strip()
                if not agent_id:
                    continue
                delegated_agents.append(agent_id)
                turn_delegated_agents.append(agent_id)
                worker_result = CoordinatorWorkerResult(
                    agent_id=agent_id,
                    status=str(payload.get("status") or "success"),
                    content=str(payload.get("content") or ""),
                    error=(str(payload.get("error"))
                           if payload.get("error") is not None else None),
                )
                worker_results.append(worker_result)
                turn_worker_results.append(worker_result)

            if turn_worker_results:
                turn_summaries.append(
                    CoordinatorTurnSummary(
                        turn_index=turn.turn_index,
                        delegation_count=len(turn_worker_results),
                        delegated_agents=list(dict.fromkeys(turn_delegated_agents)),
                        worker_results=turn_worker_results,
                        assistant_content=turn.assistant_content,
                        stop_reason=turn.stop_reason,
                    ))

        if not worker_results:
            return None

        return CoordinatorRuntimeSummary(
            turn_count=len(turn_summaries),
            delegation_count=len(worker_results),
            delegated_agents=list(dict.fromkeys(delegated_agents)),
            worker_results=worker_results,
            turns=turn_summaries,
        )
