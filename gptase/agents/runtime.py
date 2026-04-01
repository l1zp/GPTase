"""Interactive runtime for non-Claude agent execution."""

from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from gptase.agents.runtime_types import InteractiveRuntimeResult
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.runtime_types import InteractiveSessionState
from gptase.agents.runtime_types import InteractiveToolResult
from gptase.agents.runtime_types import InteractiveTurn
from gptase.agents.runtime_types import PlanHandoffProposal
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
        step_id: Optional[str] = None,
        max_turns: int = 10,
        max_tool_result_chars: int = 8000,
        mcp_server_configs: Optional[Dict[str, Any]] = None,
    ):
        self.model = model
        self.agent_id = agent_id
        self.step_id = step_id
        self.max_turns = max_turns
        self.max_tool_result_chars = max_tool_result_chars
        self.mcp_server_configs = mcp_server_configs or {}
        self.registry = get_tool_registry()
        self.tool_executor = ToolExecutor(
            model=model,
            agent_id=agent_id,
            step_id=step_id,
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
        allow_plan_handoff: bool = False,
        handoff_goal: Optional[str] = None,
    ) -> InteractiveRuntimeResult:
        tool_schemas = self.registry.get_schemas(
            allowed_tools) if allowed_tools else None
        state = self._build_initial_state(messages, allowed_tools, max_turns,
                                          resume_snapshot)
        last_content = ""
        last_reasoning = None
        last_usage: Dict[str, int] = {}

        try:
            if self.mcp_server_configs:
                await self.registry.ensure_mcp_connected(self.mcp_server_configs)

            while state.turn_index < state.max_turns:
                iteration = state.turn_index + 1
                turn_start = time.monotonic()

                response = await self.model.generate(
                    state.messages,
                    config=self.model.default_config,
                    tools=tool_schemas,
                    agent_id=self.agent_id or None,
                    step_id=self.step_id,
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
                        usage=last_usage,
                        duration_ms=llm_ms,
                        stop_reason=RuntimeStopReason.FINAL_ANSWER,
                    )
                    state.turns.append(turn)
                    state.turn_index = iteration
                    state.total_duration_ms += llm_ms
                    return self._finalize_result(
                        state=state,
                        content=last_content,
                        reasoning=last_reasoning,
                        usage=last_usage,
                        stop_reason=RuntimeStopReason.FINAL_ANSWER,
                    )

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

                turn_duration_ms = int((time.monotonic() - turn_start) * 1000)
                state.total_duration_ms += turn_duration_ms
                turn = InteractiveTurn(
                    turn_index=iteration,
                    assistant_content=last_content,
                    reasoning_content=last_reasoning,
                    tool_calls=[{
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    } for tc in response.tool_calls],
                    tool_results=[
                        InteractiveToolResult(**tool_result)
                        for tool_result in tool_exec["tool_results"]
                    ],
                    usage=last_usage,
                    duration_ms=turn_duration_ms,
                    stop_reason=(RuntimeStopReason.ERROR
                                 if tool_exec["has_invalid_tool_arguments"] else None),
                )
                if tool_exec["has_invalid_tool_arguments"]:
                    state.turns.append(turn)
                    state.turn_index = iteration
                    snapshot = self._snapshot_from_state(state)
                    if on_turn_complete is not None:
                        maybe_awaitable = on_turn_complete(snapshot, turn)
                        if inspect.isawaitable(maybe_awaitable):
                            await maybe_awaitable
                    return self._finalize_result(
                        state=state,
                        content=last_content,
                        reasoning=last_reasoning,
                        usage=last_usage,
                        stop_reason=RuntimeStopReason.ERROR,
                        error=
                        "Interactive runtime stopped due to invalid tool arguments.",
                    )

                plan_handoff = None
                if allow_plan_handoff and turn.tool_results:
                    plan_handoff = await self._evaluate_handoff(
                        goal=handoff_goal or "",
                        turn=turn,
                    )
                    if plan_handoff is not None:
                        turn.stop_reason = RuntimeStopReason.NEEDS_PLAN

                state.turns.append(turn)
                state.turn_index = iteration

                snapshot = self._snapshot_from_state(state)
                if on_turn_complete is not None:
                    maybe_awaitable = on_turn_complete(snapshot, turn)
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable

                if plan_handoff is not None:
                    return self._finalize_result(
                        state=state,
                        content=last_content,
                        reasoning=last_reasoning,
                        usage=last_usage,
                        stop_reason=RuntimeStopReason.NEEDS_PLAN,
                        plan_handoff=plan_handoff,
                    )

            return self._finalize_result(
                state=state,
                content=last_content,
                reasoning=last_reasoning,
                usage=last_usage,
                stop_reason=RuntimeStopReason.MAX_TURNS,
                error="Maximum tool iterations reached",
            )
        finally:
            if self.mcp_server_configs:
                await self.registry.disconnect_mcp()

    def _build_initial_state(
        self,
        messages: List[Dict[str, Any]],
        allowed_tools: Optional[List[str]],
        max_turns: Optional[int],
        resume_snapshot: Optional[Dict[str, Any]],
    ) -> InteractiveSessionState:
        effective_max_turns = max_turns or self.max_turns
        if resume_snapshot:
            snapshot = InteractiveRuntimeSnapshot.model_validate(resume_snapshot)
            if snapshot.turns:
                return InteractiveSessionState(
                    messages=list(snapshot.messages),
                    turns=list(snapshot.turns),
                    steps=list(snapshot.steps),
                    turn_index=len(snapshot.turns),
                    max_turns=effective_max_turns,
                    allowed_tools=list(allowed_tools or []),
                    total_input_tokens=snapshot.total_input_tokens,
                    total_output_tokens=snapshot.total_output_tokens,
                    total_duration_ms=snapshot.total_duration_ms,
                )

        return InteractiveSessionState(
            messages=list(messages),
            turns=[],
            steps=[],
            turn_index=0,
            max_turns=effective_max_turns,
            allowed_tools=list(allowed_tools or []),
        )

    def _snapshot_from_state(
        self,
        state: InteractiveSessionState,
    ) -> InteractiveRuntimeSnapshot:
        return InteractiveRuntimeSnapshot(
            messages=state.messages,
            turns=state.turns,
            steps=state.steps,
            total_input_tokens=state.total_input_tokens,
            total_output_tokens=state.total_output_tokens,
            total_duration_ms=state.total_duration_ms,
        )

    def _finalize_result(
        self,
        *,
        state: InteractiveSessionState,
        content: str,
        reasoning: Optional[str],
        usage: Dict[str, int],
        stop_reason: RuntimeStopReason,
        error: Optional[str] = None,
        plan_handoff: Optional[PlanHandoffProposal] = None,
    ) -> InteractiveRuntimeResult:
        snapshot = self._snapshot_from_state(state)
        return InteractiveRuntimeResult(
            content=content,
            reasoning=reasoning,
            stop_reason=stop_reason,
            turn_count=len(state.turns),
            turns=list(state.turns),
            usage=usage,
            snapshot=snapshot,
            steps=list(state.steps),
            total_input_tokens=state.total_input_tokens,
            total_output_tokens=state.total_output_tokens,
            total_duration_ms=state.total_duration_ms,
            error=error,
            plan_handoff=plan_handoff,
        )

    async def _evaluate_handoff(
        self,
        goal: str,
        turn: InteractiveTurn,
    ) -> Optional[PlanHandoffProposal]:
        evaluator_messages = [{
            "role":
            "system",
            "content":
            ("Decide whether the work should continue in the interactive loop or "
             "handoff into structured plan mode. Return ONLY JSON with schema "
             '{"action":"continue|needs_plan","reason":"...","planning_context":"...",'
             '"evidence_summary":"...","suggested_next_step":"..."}'),
        }, {
            "role": "user",
            "content": self._build_handoff_prompt(goal, turn),
        }]
        try:
            response = await self.model.generate(
                evaluator_messages,
                config=self.model.default_config,
                agent_id=self.agent_id or None,
                step_id=self.step_id,
            )
        except Exception:
            return None

        try:
            payload = json.loads(self._extract_json_object(response.content or ""))
        except Exception:
            return None

        if payload.get("action") != "needs_plan":
            return None

        return PlanHandoffProposal(
            reason=str(payload.get("reason") or ""),
            goal=goal,
            planning_context=str(payload.get("planning_context") or ""),
            evidence_summary=str(payload.get("evidence_summary") or ""),
            suggested_next_step=str(payload.get("suggested_next_step") or ""),
        )

    def _build_handoff_prompt(self, goal: str, turn: InteractiveTurn) -> str:
        tool_summary = []
        for tool_result in turn.tool_results:
            tool_summary.append({
                "tool_name": tool_result.tool_name,
                "arguments": tool_result.arguments,
                "content_preview": tool_result.content[:500],
                "error_type": tool_result.error_type,
            })
        payload = {
            "goal": goal,
            "assistant_content": turn.assistant_content,
            "reasoning_content": turn.reasoning_content,
            "tool_results": tool_summary,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

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
