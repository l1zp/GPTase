"""Goal-oriented harness orchestrator for multi-agent task execution."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from gptase.agents import Agent
from gptase.agents import GoalEvaluation
from gptase.agents import Plan
from gptase.agents.base import list_agent_md_files
from gptase.agents.plan_loader import PlanLoader
from gptase.agents.plan_loader import PlanRegistry
from gptase.agents.planner import PlanManager
from gptase.agents.types import DirectSession
from gptase.agents.types import DirectSessionStatus
from gptase.agents.types import SessionMessage
from gptase.agents.types import SessionTrace
from gptase.agents.types import SessionType
from gptase.agents.types import Task
from gptase.core.types import DispatchRequest
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(
    __file__).resolve().parent.parent.parent / ".claude" / "agents"
_MAX_COORDINATOR_TURNS = 3
_ORCHESTRATOR_AGENT_ID = "orchestrator"
_CHAT_AGENT_ID = "chat"

# Session message display labels and fallback content strings
_LABEL_TASK_SUBMIT = "Task Submitted"
_LABEL_WORKER_TASK = "Worker Task"
_MSG_NO_TEXT_CONTENT = "Agent completed but returned no text content."
_TITLE_UNNAMED_SESSION = "Untitled Session"


class AgentOrchestrator(Agent):
    """Single-layer harness runtime that owns goal sessions and plan execution."""

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.agents: Dict[str, Agent] = {}
        self.agent_descriptions: Dict[str, str] = {}
        self.model_manager = None
        self.memory_manager = None
        self.plan_manager: Optional[PlanManager] = None
        self.logger = logger

        self._initialize_agents()

        super().__init__(
            system_prompt=("You are the GPTase orchestrator runtime. "
                           "Use internal reasoning only for plan evaluation "
                           "and orchestration control."),
            tools=[],
            model_config=self.model_manager.get_config_for_agent(_ORCHESTRATOR_AGENT_ID)
            if self.model_manager else None,
            agent_id=_ORCHESTRATOR_AGENT_ID,
        )

        self.plan_manager = PlanManager(self, model_manager=self.model_manager)

    def _initialize_agents(self) -> None:
        from gptase.memory.manager import MemoryManager
        from gptase.models.model import Model

        self.model_manager = Model()
        self.memory_manager = MemoryManager(config=self.config.memory)
        self.agents = self._discover_agents()
        self.logger.info("Discovered %d agents: %s", len(self.agents),
                         list(self.agents.keys()))

    def _discover_agents(self) -> Dict[str, Agent]:
        config_dir = _DEFAULT_CONFIG_DIR
        agents: Dict[str, Agent] = {}

        if not config_dir.exists():
            logger.warning("Agent config directory not found: %s", config_dir)
            return agents

        for md_file in list_agent_md_files(config_dir):
            if "_archived" in str(md_file):
                continue
            if md_file.parent.name == _ORCHESTRATOR_AGENT_ID:
                continue
            try:
                agent = Agent.from_markdown(md_file,
                                            model_manager=self.model_manager,
                                            memory_manager=self.memory_manager)
                agents[agent.agent_id] = agent
                self.agent_descriptions[agent.agent_id] = agent.description
                logger.info("Discovered agent '%s' from %s", agent.agent_id, md_file)
            except Exception as exc:
                logger.warning("Failed to load agent from %s: %s", md_file, exc)

        return agents

    async def dispatch(
        self,
        request: DispatchRequest,
    ) -> Dict[str, Any]:
        """Dispatch a request to the appropriate mode (agent / coordinator / plan)."""
        task_id = request.id or f"task_{datetime.now().timestamp()}"
        self.logger.info("Starting orchestrator task execution: %s", task_id)

        try:
            # Resume existing session
            if request.session_id:
                return await self._continue_session(request.session_id, request)

            # Plan mode: explicit plan_id / plan_path / inline plan dict
            if request.plan or request.plan_id or request.plan_path:
                return await self._execute_plan(task_id, request)

            # Agent mode: explicit agent_id pointing to a worker
            resolved_agent_id = self._resolve_agent_id(request.agent_id)
            if resolved_agent_id and resolved_agent_id != self.agent_id:
                return await self._execute_agent(task_id, request, resolved_agent_id)

            # Coordinator mode: orchestrator loop with delegation + plan handoff
            return await self._execute_coordinator(task_id, request)
        except Exception as exc:
            self.logger.error("Task execution failed: %s", exc)
            return self._error_result(task_id, str(exc))

    async def _execute_agent(
        self,
        task_id: str,
        request: DispatchRequest,
        agent_id: Optional[str],
    ) -> Dict[str, Any]:
        if not agent_id or agent_id not in self.agents:
            return self._error_result(task_id, f"Unknown agent_id: {request.agent_id}")

        task_obj = Task.from_dict({
            **request.model_dump(exclude_none=True),
            "agent_id":
            agent_id,
            "description":
            request.query or "Process the following data",
        })
        result = await self.agents[agent_id].process_task(task_obj)
        return {
            "task_id": task_id,
            "status": result.get("status", "success"),
            "data": result.get("data"),
            "error": result.get("error"),
            "trace": result.get("trace"),
            "agent_id": agent_id,
            "execution_mode": "direct",
            "timestamp": datetime.now().isoformat(),
        }

    async def _continue_session(self, session_id: str,
                                request: DispatchRequest) -> Dict[str, Any]:
        """Resume an existing session (direct chat/agent only)."""
        # Determine session type from ID prefix
        if session_id.startswith(("chat_", "agent_")):
            session_type_str = "chat" if session_id.startswith("chat_") else "agent"
            return await self._continue_direct_session(session_id, request,
                                                       SessionType(session_type_str))
        # Plan sessions are no longer persisted; re-execute
        return await self._execute_plan(request.id or session_id, request)

    def _coordinator_result(
        self,
        task_id: str,
        status: str,
        result: Dict[str, Any],
        merged_coordinator: Optional[Dict[str, Any]],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a standardized coordinator result dict."""
        return {
            "task_id": task_id,
            "status": status,
            "data": result.get("data"),
            "error": error or result.get("error"),
            "trace": self._with_coordinator_trace(result.get("trace"),
                                                  merged_coordinator),
            "agent_id": self.agent_id,
            "execution_mode": "coordinator",
            "timestamp": datetime.now().isoformat(),
        }

    async def _execute_coordinator(
        self,
        task_id: str,
        request: DispatchRequest,
    ) -> Dict[str, Any]:
        """Run the coordinator loop: orchestrator agent with worker delegation and plan handoff."""
        if not request.query:
            return self._error_result(task_id, "Task description is required")

        merged_coordinator: Optional[Dict[str, Any]] = None
        prompt: str = request.query

        for _ in range(_MAX_COORDINATOR_TURNS):
            result = await self.run(
                prompt,
                image_paths=request.image_paths,
                _allow_plan_handoff=True,
                _handoff_description=request.query,
            )
            runtime = self._runtime_trace(result)
            stop_reason = runtime.get("stop_reason")

            # Path 1: Plan handoff
            if stop_reason == "needs_plan":
                proposal = runtime.get("plan_handoff")
                if not isinstance(proposal, dict):
                    return self._error_result(
                        task_id,
                        "Coordinator requested plan handoff without a proposal.",
                    )
                trace = self._with_coordinator_trace(result.get("trace"),
                                                     merged_coordinator)
                return await self._execute_plan(
                    task_id,
                    request.model_copy(update={"_intake_trace": trace}),
                )

            coordinator = self._normalize_coordinator_summary(
                runtime.get("coordinator"))

            # Path 2: Final answer (no worker delegation)
            if stop_reason == "final_answer" and not coordinator:
                return self._coordinator_result(task_id,
                                                result.get("status", "success"), result,
                                                merged_coordinator)

            # Path 3: Non-final stop without coordinator activity
            if not coordinator:
                return self._coordinator_result(task_id, result.get("status", "failed"),
                                                result, merged_coordinator)

            # Path 4: Worker(s) delegated — merge and continue
            merged_coordinator = self._merge_coordinator_summaries(
                merged_coordinator, coordinator)

            if merged_coordinator.get("turn_count", 0) >= _MAX_COORDINATOR_TURNS:
                return self._coordinator_result(
                    task_id, "failed", result, merged_coordinator,
                    "Coordinator loop exceeded the maximum number of"
                    " orchestration turns.")

            prompt = self._build_coordinator_followup_prompt(request.query,
                                                             merged_coordinator,
                                                             runtime)

        return self._error_result(
            task_id,
            "Coordinator loop terminated unexpectedly without a final result.",
        )

    async def _create_or_load_direct_session(
        self,
        session_type: SessionType,
        query: str,
        agent_id: Optional[str],
        session_id: Optional[str],
    ) -> tuple:
        """Resolve agent, load or create a DirectSession, append user message, and save.

        Returns:
            Tuple of (resolved_agent_id, session).

        Raises:
            ValueError: If the agent cannot be resolved.
        """
        resolved_agent_id = self._resolve_direct_agent_id(session_type, agent_id)
        if not resolved_agent_id or resolved_agent_id not in self.agents:
            raise ValueError(f"Unknown agent_id: {agent_id or resolved_agent_id}")

        session = None
        if session_id:
            session = await self._load_direct_session(session_id, session_type)
        if session is None:
            session = DirectSession(
                session_id=session_id or self._generate_direct_session_id(session_type),
                session_type=session_type,
                title=self._summarize_text(query),
                status=DirectSessionStatus.DRAFT,
                agent_id=resolved_agent_id,
            )

        session.agent_id = resolved_agent_id
        session.updated_at = datetime.now()
        session.status = DirectSessionStatus.IN_PROGRESS
        session.messages.append(
            SessionMessage(
                id=f"{session.session_id}-user-{uuid.uuid4().hex[:8]}",
                role="user",
                content=query,
                metadata={
                    "label": _LABEL_TASK_SUBMIT
                    if session_type == SessionType.CHAT else _LABEL_WORKER_TASK,
                    "tone": "blue" if session_type == SessionType.CHAT else "purple",
                },
            ))
        await self._save_direct_session(session)
        return resolved_agent_id, session

    async def execute_direct_session(
        self,
        session_type: SessionType,
        query: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or continue a persisted direct chat/agent session."""
        resolved_agent_id, session = await self._create_or_load_direct_session(
            session_type, query, agent_id, session_id)

        task_obj = Task.from_dict({
            "agent_id": resolved_agent_id,
            "description": query,
            "image_paths": image_paths,
        })
        result = await self.agents[resolved_agent_id].process_task(task_obj)

        session.status = (DirectSessionStatus.FAILED if result.get("status")
                          in ("error", "failed") else DirectSessionStatus.COMPLETED)
        session.updated_at = datetime.now()
        session.messages.append(
            SessionMessage(
                id=f"{session.session_id}-agent-{uuid.uuid4().hex[:8]}",
                role="system" if result.get("status") in ("error",
                                                          "failed") else "agent",
                content=result.get("error") or result.get("data", {}).get("content")
                or _MSG_NO_TEXT_CONTENT,
                metadata={
                    "agentId":
                    resolved_agent_id,
                    "label":
                    "Worker Error"
                    if result.get("status") in ("error", "failed") else "Worker Result",
                    "tone":
                    "red" if result.get("status") in ("error", "failed") else "green",
                },
            ))
        session.traces.extend(self._result_to_session_traces(session, result))
        await self._save_direct_session(session)
        return self._direct_session_response(session)

    async def stream_direct_session(
        self,
        session_type: SessionType,
        query: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Stream a direct chat/agent session over websocket-friendly events."""
        resolved_agent_id, session = await self._create_or_load_direct_session(
            session_type, query, agent_id, session_id)
        yield {"type": "session", "data": self._direct_session_response(session)}

        stream_start = time.monotonic()
        content_parts: List[str] = []
        try:
            async for event in self.agents[resolved_agent_id].run_stream(
                    query, step_id=f"{session.session_id}_stream"):
                delta = event.get("content") or ""
                if delta:
                    content_parts.append(delta)
                    yield {
                        "type": "chunk",
                        "data": {
                            "session_id": session.session_id,
                            "delta": delta,
                        },
                    }

            final_content = "".join(content_parts)
            session.status = DirectSessionStatus.COMPLETED
            session.updated_at = datetime.now()
            session.messages.append(
                SessionMessage(
                    id=f"{session.session_id}-agent-{uuid.uuid4().hex[:8]}",
                    role="agent",
                    content=final_content or _MSG_NO_TEXT_CONTENT,
                    metadata={
                        "agentId": resolved_agent_id,
                        "label": "Worker Result",
                        "tone": "green",
                    },
                ))
            session.traces.append(
                SessionTrace(
                    id=f"{session.session_id}-trace-{uuid.uuid4().hex[:8]}",
                    step_id=session.agent_id,
                    type="log",
                    message=final_content or "stream completed",
                    details={
                        "type": "llm_call",
                        "duration_ms": int((time.monotonic() - stream_start) * 1000),
                        "iteration": 1,
                        "content_preview": (final_content or "")[:500],
                    },
                ))
            await self._save_direct_session(session)
            yield {"type": "done", "data": self._direct_session_response(session)}
        except Exception as exc:
            session.status = DirectSessionStatus.FAILED
            session.updated_at = datetime.now()
            session.messages.append(
                SessionMessage(
                    id=f"{session.session_id}-error-{uuid.uuid4().hex[:8]}",
                    role="system",
                    content=str(exc),
                    metadata={
                        "agentId": resolved_agent_id,
                        "label": "Worker Error",
                        "tone": "red",
                    },
                ))
            await self._save_direct_session(session)
            yield {
                "type": "error",
                "data": {
                    "session_id": session.session_id,
                    "error": str(exc),
                },
            }

    async def _execute_plan(
        self,
        task_id: str,
        request: DispatchRequest,
        plan: Optional[Plan] = None,
    ) -> Dict[str, Any]:
        """Create and execute a Plan, optionally with replan loop."""
        description = request.query
        auto_execute = request.auto_execute
        auto_replan = request.auto_replan
        input_data = dict(request.input_data or {})
        document_path = request.document_path
        workspace_dir = request.workspace_dir

        # Resolve or create plan
        if plan is None:
            plan = await self._resolve_plan(request, description)
        if not description:
            description = plan.goal or plan.summary or "Complete the requested work"

        preflight = self._build_preflight_summary(plan, request)

        # Review mode: return draft without executing
        if not auto_execute:
            return {
                "status": "draft",
                "goal": description,
                "current_plan": plan.model_dump(mode="json"),
                "progress": plan.get_progress(),
                "preflight": preflight,
                "timestamp": datetime.now().isoformat(),
            }

        # Execute plan with optional replan loop
        max_replans = request.max_auto_replans
        replan_count = 0
        task_results: Dict[str, Any] = {}
        plan_history: List[Plan] = []

        while plan:
            result = await self.plan_manager.execute_plan(
                plan=plan.model_copy(deep=True),
                input_data=input_data,
                session_id=task_id,
                document_path=document_path,
                workspace_dir=workspace_dir,
            )

            task_results = result.get("task_results", {})
            plan_history.append(plan.model_copy(deep=True))

            evaluation = await self._evaluate_goal(description, plan, result)

            if evaluation.goal_achieved:
                return {
                    "status": "completed",
                    "goal": description,
                    "current_plan": plan.model_dump(mode="json"),
                    "plan_history": [p.model_dump(mode="json") for p in plan_history],
                    "progress": plan.get_progress(),
                    "task_results": task_results,
                    "goal_evaluation": evaluation.model_dump(),
                    "preflight": preflight,
                    "timestamp": datetime.now().isoformat(),
                }

            if not auto_replan or replan_count >= max_replans:
                status = "blocked" if replan_count >= max_replans else "needs_input"
                return {
                    "status": status,
                    "goal": description,
                    "current_plan": plan.model_dump(mode="json"),
                    "plan_history": [p.model_dump(mode="json") for p in plan_history],
                    "progress": plan.get_progress(),
                    "task_results": task_results,
                    "goal_evaluation": evaluation.model_dump(),
                    "preflight": preflight,
                    "timestamp": datetime.now().isoformat(),
                }

            replan_count += 1
            context = self._build_replan_context(description, plan, evaluation)
            plan = await self.plan_manager.create_plan(
                description=description,
                context=context,
                available_agents=self._available_agents_for_planning(),
            )
            self._normalize_plan_agents(plan)

        return {
            "status": "failed",
            "goal": description,
            "task_results": task_results,
            "timestamp": datetime.now().isoformat(),
        }

    async def _resolve_plan(self, request: DispatchRequest, description: str) -> Plan:
        """Resolve a plan from the request payload or generate one."""
        loader = PlanLoader()

        if request.plan and isinstance(request.plan, dict):
            plan = loader.load_data(request.plan,
                                    fallback_plan_id=f"inline_{uuid.uuid4().hex[:8]}")
        elif request.plan_path:
            plan = loader.load_path(Path(request.plan_path).expanduser())
        elif request.plan_id:
            plan = PlanRegistry.get_instance().get_plan(str(
                request.plan_id)).model_copy(deep=True)
        else:
            context = str(request.planning_context or "").strip()
            plan = await self.plan_manager.create_plan(
                description=description,
                context=context,
                available_agents=self._available_agents_for_planning(),
            )

        if not plan.goal:
            plan.goal = description
        self._normalize_plan_agents(plan)
        return plan

    def _runtime_trace(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return (result.get("trace") or {}).get("runtime") or {}

    def _normalize_coordinator_summary(
        self,
        summary: Any,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(summary, dict):
            return None

        turns = summary.get("turns") or []
        delegated_agents = summary.get("delegated_agents") or []
        worker_results = [
            item for item in (summary.get("worker_results") or [])
            if isinstance(item, dict)
        ]

        normalized_turns: List[Dict[str, Any]] = []
        for index, turn in enumerate(turns, start=1):
            if not isinstance(turn, dict):
                continue
            turn_worker_results = [
                item for item in (turn.get("worker_results") or [])
                if isinstance(item, dict)
            ]
            normalized_turns.append({
                "turn_index":
                int(turn.get("turn_index") or index),
                "delegation_count":
                int(turn.get("delegation_count") or len(turn_worker_results)),
                "delegated_agents":
                list(turn.get("delegated_agents") or []),
                "worker_results":
                turn_worker_results,
                "assistant_content":
                str(turn.get("assistant_content") or ""),
                "stop_reason":
                turn.get("stop_reason"),
            })

        if not normalized_turns and worker_results:
            normalized_turns = [{
                "turn_index":
                1,
                "delegation_count":
                int(summary.get("delegation_count") or len(worker_results)),
                "delegated_agents":
                list(delegated_agents),
                "worker_results":
                worker_results,
                "assistant_content":
                "",
                "stop_reason":
                summary.get("stop_reason"),
            }]

        if not normalized_turns:
            return None

        merged_worker_results: List[Dict[str, Any]] = []
        merged_agents: List[str] = []
        for turn in normalized_turns:
            merged_worker_results.extend(turn.get("worker_results") or [])
            merged_agents.extend(turn.get("delegated_agents") or [])

        return {
            "turn_count":
            len(normalized_turns),
            "delegation_count":
            sum(int(turn.get("delegation_count") or 0) for turn in normalized_turns),
            "delegated_agents":
            list(dict.fromkeys(merged_agents)),
            "worker_results":
            merged_worker_results,
            "turns":
            normalized_turns,
        }

    def _merge_coordinator_summaries(
        self,
        existing: Optional[Dict[str, Any]],
        new_summary: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if existing is None:
            return new_summary
        if new_summary is None:
            return existing

        merged_turns = list(existing.get("turns") or []) + list(
            new_summary.get("turns") or [])
        merged_worker_results: List[Dict[str, Any]] = []
        merged_agents: List[str] = []
        for turn in merged_turns:
            merged_worker_results.extend(turn.get("worker_results") or [])
            merged_agents.extend(turn.get("delegated_agents") or [])

        return {
            "turn_count":
            len(merged_turns),
            "delegation_count":
            sum(int(turn.get("delegation_count") or 0) for turn in merged_turns),
            "delegated_agents":
            list(dict.fromkeys(merged_agents)),
            "worker_results":
            merged_worker_results,
            "turns":
            merged_turns,
        }

    def _with_coordinator_trace(
        self,
        trace: Optional[Dict[str, Any]],
        coordinator_summary: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if trace is None:
            return None
        if not coordinator_summary:
            return trace
        runtime = dict((trace.get("runtime") or {}))
        runtime["coordinator"] = coordinator_summary
        return {
            **trace,
            "runtime": runtime,
        }

    def _build_coordinator_followup_prompt(
        self,
        goal: str,
        coordinator_summary: Dict[str, Any],
        runtime: Dict[str, Any],
    ) -> str:
        turns = list(coordinator_summary.get("turns") or [])
        latest_turn = turns[-1] if turns else {}
        payload = {
            "goal": goal,
            "coordinator_turns": turns,
            "latest_worker_results": latest_turn.get("worker_results", []),
            "latest_assistant_content": latest_turn.get("assistant_content", ""),
            "latest_stop_reason": runtime.get("stop_reason"),
        }
        return ("Continue coordinating this task. First synthesize the worker results "
                "already gathered. If the goal is satisfied, answer directly. If more "
                "specialized work is needed, delegate again. If the work has become a "
                "multi-step structured workflow, request plan handoff.\n\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}")

    def _build_replan_context(self,
                              goal: str,
                              plan: Plan,
                              evaluation: GoalEvaluation,
                              extra_feedback: str = "") -> str:
        parts = [f"Goal:\n{goal}"]
        parts.append(
            f"Previous plan:\n{json.dumps(plan.model_dump(), ensure_ascii=False, default=str)}"
        )
        parts.append(
            f"Goal evaluation:\n{json.dumps(evaluation.model_dump(), ensure_ascii=False)}"
        )
        if extra_feedback:
            parts.append(f"User feedback:\n{extra_feedback}")
        return "\n\n".join(parts)

    def _normalize_plan_agents(self, plan: Plan) -> None:
        for task in plan.tasks:
            if task.agent_id:
                resolved = self._resolve_agent_id(task.agent_id)
                if not resolved:
                    raise ValueError(
                        f"Plan references unknown agent_id: {task.agent_id}")
                task.agent_id = resolved

    async def _evaluate_goal(self, goal: str, plan: Plan,
                             execution_result: Dict[str, Any]) -> GoalEvaluation:
        progress = execution_result.get("progress", {})
        failed = int(progress.get("failed", 0))
        completed = int(progress.get("completed", 0))
        if failed > 0 and completed == 0:
            return GoalEvaluation(
                goal_achieved=False,
                reason="The current plan failed before producing enough output.",
                missing_gaps=["Repair failed tasks or revise the plan."],
                next_action="fail")

        prompt = (
            "Evaluate whether the user's goal has been achieved.\n\n"
            f"Goal:\n{goal}\n\n"
            "Return ONLY JSON with schema:\n"
            '{"goal_achieved": true, "reason": "...", "missing_gaps": ["..."], '
            '"next_action": "complete|replan|ask_user|fail"}\n\n'
            f"Current plan summary:\n{json.dumps(plan.model_dump(), ensure_ascii=False, default=str)}\n\n"
            f"Execution result:\n{json.dumps(execution_result, ensure_ascii=False, default=str)}\n"
        )
        result = await self.run(prompt)
        content = result.get("data", {}).get("content", "")
        try:
            data = json.loads(self.plan_manager._extract_json(content))
            return GoalEvaluation(**data)
        except Exception:
            return GoalEvaluation(
                goal_achieved=False,
                reason=
                "Goal evaluator returned invalid JSON; using conservative fallback.",
                missing_gaps=["Goal achievement could not be confirmed automatically."],
                next_action="ask_user",
            )

    def _build_replan_context(self,
                              goal: str,
                              plan: Plan,
                              evaluation: GoalEvaluation,
                              extra_feedback: str = "") -> str:
        parts = [f"Goal:\n{goal}"]
        parts.append(
            f"Previous plan:\n{json.dumps(plan.model_dump(), ensure_ascii=False, default=str)}"
        )
        parts.append(
            f"Goal evaluation:\n{json.dumps(evaluation.model_dump(), ensure_ascii=False)}"
        )
        if extra_feedback:
            parts.append(f"User feedback:\n{extra_feedback}")
        return "\n\n".join(parts)

    def _available_agents_for_planning(self) -> List[Dict[str, str]]:
        agents: List[Dict[str, str]] = []
        for agent_id in sorted(self.agents.keys()):
            agents.append({
                "agent_id": agent_id,
                "description": self.agent_descriptions.get(agent_id, ""),
            })
        agents.append({
            "agent_id":
            self.agent_id,
            "description":
            "Use only when no specialized worker fits or for synthesis.",
        })
        return agents

    def _resolve_agent_id(self, agent_id: Optional[str]) -> Optional[str]:
        if not agent_id:
            return None
        if agent_id == self.agent_id:
            return self.agent_id
        candidates = [
            agent_id,
            str(agent_id).replace("_", "-"),
            str(agent_id).replace("-", "_"),
        ]
        for candidate in candidates:
            if candidate in self.agents:
                return candidate
        return None

    def _direct_session_state_key(self, session_type: SessionType,
                                  session_id: str) -> str:
        return f"{session_type.value}_session:{session_id}"

    def _generate_direct_session_id(self, session_type: SessionType) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{session_type.value}_{ts}_{uuid.uuid4().hex[:8]}"

    def _build_preflight_summary(self, plan: Plan,
                                 request: DispatchRequest) -> Dict[str, Any]:
        warnings: List[str] = []
        errors: List[str] = []

        document_path = request.document_path
        if not document_path:
            warnings.append(
                "No document_path provided; file-relative tasks may have limited context."
            )

        bash_tasks = []
        tasks_missing_expected_output = []
        for task in plan.tasks:
            task_tools = task.tools or []
            if any(tool.lower() == "bash"
                   for tool in task_tools) or task.action.lower() == "bash":
                bash_tasks.append(task.task_id)
            if not task.expected_output:
                tasks_missing_expected_output.append(task.task_id)

        if bash_tasks:
            warnings.append(
                f"Tasks {', '.join(bash_tasks)} use Bash-capable execution; review them before approval."
            )
        if tasks_missing_expected_output:
            warnings.append(
                "Some tasks omit expected_output, which can make review and validation harder."
            )

        return {
            "status": "error" if errors else "warning" if warnings else "ok",
            "warnings": warnings,
            "errors": errors,
        }

    def _error_result(self, task_id: str, error: str) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

    async def get_system_status(self) -> Dict[str, Any]:
        agents_info = {}
        for agent_id, agent in self.agents.items():
            agents_info[agent_id] = {
                "agent_id": agent_id,
                "type": agent.__class__.__name__,
                "status": "active",
            }
        memory_usage = await self.memory_manager.get_usage()
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": agents_info,
            "memory": memory_usage,
        }

    async def list_available_agents(self) -> List[Dict[str, Any]]:
        return [{
            "agent_id": agent_id,
            "type": agent.__class__.__name__,
            "status": "active",
            "description": self.agent_descriptions.get(agent_id, ""),
        } for agent_id, agent in self.agents.items()]

    async def get_agent_memory(self, agent_id: str) -> Dict[str, Any]:
        if self.memory_manager:
            summary = await self.memory_manager.create_summary(
                context=f"agent:{agent_id}")
            return {"agent_id": agent_id, "memory_summary": summary}
        return {"agent_id": agent_id, "memory_summary": None}

    async def get_agent_working_memory(self, agent_id: str) -> Dict[str, Any]:
        """Return the compressed working memory snapshot for an agent."""
        if not self.memory_manager:
            return {"agent_id": agent_id, "working_memory": None}

        memory = await self.memory_manager.get_agent_working_memory(agent_id)
        if memory is None:
            return {"agent_id": agent_id, "working_memory": None}

        return {
            "agent_id": agent_id,
            "working_memory": {
                "summary": memory.summary,
                "metadata": memory.metadata,
                "last_updated": memory.last_updated.isoformat(),
            },
        }

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        direct_session = await self._load_any_direct_session(session_id)
        if direct_session is not None:
            return self._direct_session_response(direct_session)

        # Plan sessions no longer persisted as GoalSession
        return None

    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = self.memory_manager.storage.db
        try:
            cursor = await db.execute(
                """SELECT agent_id, state_data
                   FROM agent_states
                   WHERE agent_id LIKE 'chat_session:%'
                      OR agent_id LIKE 'agent_session:%'
                   ORDER BY last_updated DESC
                   LIMIT ?""",
                (limit, ),
            )
            rows = await cursor.fetchall()
        except Exception as exc:
            self.logger.warning("Failed to list sessions: %s", exc)
            return []

        sessions: List[Dict[str, Any]] = []
        for row in rows:
            try:
                data = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                state_data = data.get("state_data", data)
                session = DirectSession(**state_data)
                sessions.append({
                    "session_id": session.session_id,
                    "session_type": session.session_type.value,
                    "goal": session.title,
                    "status": session.status.value,
                    "current_plan_id": None,
                    "selected_agent_id": session.agent_id,
                    "updated_at": session.updated_at.isoformat(),
                })
            except Exception:
                continue
        return sessions

    async def approve_plan(self,
                           session_id: str,
                           feedback: Optional[str] = None) -> Dict[str, Any]:
        payload = DispatchRequest(session_id=session_id,
                                  approve_plan=True,
                                  feedback=feedback or None)
        return await self.dispatch(payload)

    async def provide_user_input(self, session_id: str, message: str) -> Dict[str, Any]:
        return await self.dispatch(
            DispatchRequest(session_id=session_id, user_input=message))

    async def close(self) -> None:
        """Release orchestrator-owned resources."""
        if self.plan_manager is not None:
            await self.plan_manager.close()
        for agent in self.agents.values():
            await agent.close()
        if self.memory_manager is not None:
            await self.memory_manager.close()

    async def _continue_direct_session(
        self,
        session_id: str,
        request: DispatchRequest,
        session_type: SessionType,
    ) -> Dict[str, Any]:
        if not request.query:
            return self._error_result(request.id or session_id,
                                      "Task description is required")
        return await self.execute_direct_session(
            session_type=session_type,
            query=request.query,
            agent_id=request.agent_id,
            session_id=session_id,
            image_paths=request.image_paths,
        )

    async def _save_direct_session(self, session: DirectSession) -> None:
        state = {
            "agent_id":
            self._direct_session_state_key(session.session_type, session.session_id),
            "state_data":
            session.model_dump(mode="json"),
        }
        await self.memory_manager.store_agent_state(state)

    async def _load_direct_session(
        self,
        session_id: str,
        session_type: SessionType,
    ) -> Optional[DirectSession]:
        state = await self.memory_manager.get_agent_state(
            self._direct_session_state_key(session_type, session_id))
        if not state:
            return None
        raw = state.get("state_data")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            return None
        return DirectSession(**raw)

    async def _load_any_direct_session(self,
                                       session_id: str) -> Optional[DirectSession]:
        for session_type in (SessionType.CHAT, SessionType.AGENT):
            session = await self._load_direct_session(session_id, session_type)
            if session is not None:
                return session
        return None

    def _direct_session_response(self, session: DirectSession) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "session_type": session.session_type.value,
            "status": session.status.value,
            "goal": session.title,
            "selected_agent_id": session.agent_id,
            "messages":
            [message.model_dump(mode="json") for message in session.messages],
            "traces": [trace.model_dump(mode="json") for trace in session.traces],
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "current_plan": None,
            "plan_history": [],
            "task_results": {},
            "task_traces": {},
        }

    def _resolve_direct_agent_id(self, session_type: SessionType,
                                 agent_id: Optional[str]) -> Optional[str]:
        if session_type == SessionType.CHAT:
            return self._resolve_agent_id(_CHAT_AGENT_ID)
        return self._resolve_agent_id(agent_id)

    def _summarize_text(self, text: str) -> str:
        clean = " ".join(str(text).split()).strip()
        if not clean:
            return _TITLE_UNNAMED_SESSION
        return clean[:30] + ("..." if len(clean) > 30 else "")

    def _result_to_session_traces(self, session: DirectSession,
                                  result: Dict[str, Any]) -> List[SessionTrace]:
        traces: List[SessionTrace] = []
        for step in result.get("trace", {}).get("steps", []):
            traces.append(
                SessionTrace(
                    id=f"{session.session_id}-trace-{uuid.uuid4().hex[:8]}",
                    step_id=session.agent_id,
                    type="success" if step.get("type") == "sdk_run" else "log",
                    message=step.get("result_preview") or step.get("content_preview")
                    or step.get("note") or step.get("tool_name") or "",
                    details={
                        "type": step.get("type"),
                        "duration_ms": step.get("duration_ms"),
                        "iteration": step.get("iteration"),
                        "tool_name": step.get("tool_name"),
                        "arguments": step.get("arguments"),
                        "content_preview": step.get("content_preview"),
                        "result_preview": step.get("result_preview"),
                        "note": step.get("note"),
                        "message_count": step.get("message_count"),
                        "result_chars": step.get("result_chars"),
                        "usage": step.get("usage"),
                    },
                ))
        return traces
