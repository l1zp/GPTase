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
from gptase.agents import AgentTask
from gptase.agents import GoalEvaluation
from gptase.agents import GoalSession
from gptase.agents import GoalSessionStatus
from gptase.agents import Plan
from gptase.agents.base import list_agent_md_files
from gptase.agents.plan_loader import PlanLoader
from gptase.agents.plan_loader import PlanRegistry
from gptase.agents.planner import PlanManager
from gptase.agents.types import AgentMode
from gptase.agents.types import DirectSession
from gptase.agents.types import DirectSessionStatus
from gptase.agents.types import SessionMessage
from gptase.agents.types import SessionTrace
from gptase.agents.types import SessionType
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(
    __file__).resolve().parent.parent.parent / ".claude" / "agents"
_ORCHESTRATOR_AGENT_ID = "orchestrator"
_CHAT_AGENT_ID = "chat"


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

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a goal-oriented harness task or direct subagent task."""
        task_id = task.get("id", f"task_{datetime.now().timestamp()}")
        self.logger.info("Starting orchestrator task execution: %s", task_id)

        try:
            session_id = task.get("session_id")
            if session_id:
                session_type = str(task.get("session_type") or "")
                if not session_type:
                    if str(session_id).startswith("chat_"):
                        session_type = SessionType.CHAT.value
                    elif str(session_id).startswith("agent_"):
                        session_type = SessionType.AGENT.value
                if session_type in (SessionType.CHAT.value, SessionType.AGENT.value):
                    return await self._continue_direct_session(
                        session_id,
                        task,
                        SessionType(session_type),
                    )
                return await self._continue_goal_session(session_id, task)

            description = str(task.get("goal") or task.get("description") or "").strip()
            if not description and not any(k in task
                                           for k in ("plan", "plan_id", "plan_path")):
                return self._error_result(task_id,
                                          "Task description or plan is required")

            requested_agent_id = task.get("agent_id")
            resolved_agent_id = self._resolve_agent_id(requested_agent_id)
            execution_mode = task.get("execution_mode", "auto")
            if execution_mode == "direct" or (resolved_agent_id
                                              and resolved_agent_id != self.agent_id):
                return await self._execute_direct_task(task_id, task, resolved_agent_id)

            return await self._start_goal_session(task_id, description, task)
        except Exception as exc:
            self.logger.error("Task execution failed: %s", exc)
            return self._error_result(task_id, str(exc))

    async def _execute_direct_task(
        self,
        task_id: str,
        task: Dict[str, Any],
        agent_id: Optional[str],
    ) -> Dict[str, Any]:
        if not agent_id or agent_id not in self.agents:
            return self._error_result(task_id,
                                      f"Unknown agent_id: {task.get('agent_id')}")

        task_obj = AgentTask.from_dict({
            **task,
            "agent_id":
            agent_id,
            "description":
            task.get("description") or task.get("goal") or "Process the following data",
        })
        result = await self.agents[agent_id].process_task_with_mode(
            task_obj, mode=AgentMode.DIRECT)
        return {
            "task_id": task_id,
            "status": result.get("status", "success"),
            "data": result.get("data"),
            "error": result.get("error"),
            "agent_id": agent_id,
            "execution_mode": "direct",
            "timestamp": datetime.now().isoformat(),
        }

    async def execute_direct_session(
        self,
        session_type: SessionType,
        message: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or continue a persisted direct chat/agent session."""
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
                title=self._summarize_text(message),
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
                content=message,
                metadata={
                    "label":
                    "任务提交" if session_type == SessionType.CHAT else "Worker 任务",
                    "tone": "blue" if session_type == SessionType.CHAT else "purple",
                },
            ))
        await self._save_direct_session(session)

        task_obj = AgentTask.from_dict({
            "agent_id": resolved_agent_id,
            "description": message,
            "goal": message,
            "image_paths": image_paths,
        })
        result = await self.agents[resolved_agent_id].process_task_with_mode(
            task_obj,
            mode=AgentMode.DIRECT,
        )

        session.status = (DirectSessionStatus.FAILED if result.get("status")
                          in ("error", "failed") else DirectSessionStatus.COMPLETED)
        session.updated_at = datetime.now()
        session.messages.append(
            SessionMessage(
                id=f"{session.session_id}-agent-{uuid.uuid4().hex[:8]}",
                role="system" if result.get("status") in ("error",
                                                          "failed") else "agent",
                content=result.get("error") or result.get("data", {}).get("content")
                or "Agent 已完成，但没有返回文本内容。",
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
        message: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Stream a direct chat session over websocket-friendly events."""
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
                title=self._summarize_text(message),
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
                content=message,
                metadata={
                    "label":
                    "任务提交" if session_type == SessionType.CHAT else "Worker 任务",
                    "tone": "blue" if session_type == SessionType.CHAT else "purple",
                },
            ))
        await self._save_direct_session(session)
        yield {"type": "session", "data": self._direct_session_response(session)}

        stream_start = time.monotonic()
        content_parts: List[str] = []
        try:
            async for event in self.agents[resolved_agent_id].run_stream(
                    message, step_id=f"{session.session_id}_stream"):
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
                    content=final_content or "Agent 已完成，但没有返回文本内容。",
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

    async def _start_goal_session(
        self,
        task_id: str,
        goal: str,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        auto_execute = bool(task.get("auto_execute", False))
        auto_replan = bool(task.get("auto_replan", False))
        session_id = self._generate_goal_session_id()
        session = GoalSession(
            session_id=session_id,
            goal=goal,
            draft_source="generated",
            auto_execute=auto_execute,
            auto_replan=auto_replan,
            input_data=dict(task.get("input_data") or {}),
            document_path=task.get("document_path"),
            workspace_dir=task.get("workspace_dir"),
            metadata={
                "task_id": task_id,
                "max_auto_replans": int(task.get("max_auto_replans", 3)),
                "user_feedback": [],
            },
        )

        plan = await self._resolve_draft_plan(task, session)
        if not session.goal:
            session.goal = plan.goal or plan.summary or "Complete the requested work"
        session.current_plan = plan
        session.current_plan_id = plan.plan_id
        session.status = (GoalSessionStatus.EXECUTING
                          if auto_execute else GoalSessionStatus.AWAITING_APPROVAL)
        await self._save_goal_session(session)

        if auto_execute:
            session = await self._run_goal_session(session)

        return self._goal_session_response(session)

    async def _continue_goal_session(self, session_id: str,
                                     task: Dict[str, Any]) -> Dict[str, Any]:
        session = await self._load_goal_session(session_id)
        if session is None:
            return self._error_result(task.get("id", session_id),
                                      f"Unknown session_id: {session_id}")

        feedback = str(task.get("feedback") or task.get("user_input") or "").strip()
        approve = bool(task.get("approve_plan", False))
        auto_execute = task.get("auto_execute")
        if auto_execute is not None:
            session.auto_execute = bool(auto_execute)
        if "auto_replan" in task:
            session.auto_replan = bool(task.get("auto_replan"))

        if feedback:
            session.metadata.setdefault("user_feedback", []).append(feedback)

        if approve or (session.status == GoalSessionStatus.AWAITING_APPROVAL
                       and session.auto_execute):
            if feedback and session.status == GoalSessionStatus.AWAITING_APPROVAL:
                session = await self._revise_current_plan(session, feedback)
            session.status = GoalSessionStatus.EXECUTING
            await self._save_goal_session(session)
            session = await self._run_goal_session(session)
            return self._goal_session_response(session)

        if feedback and session.status in (
                GoalSessionStatus.AWAITING_APPROVAL,
                GoalSessionStatus.AWAITING_USER_INPUT,
        ):
            session = await self._revise_current_plan(session, feedback)

        await self._save_goal_session(session)
        return self._goal_session_response(session)

    async def _revise_current_plan(self, session: GoalSession,
                                   feedback: str) -> GoalSession:
        context = self._build_replan_context(session, extra_feedback=feedback)
        revised = await self.plan_manager.create_plan(
            goal=session.goal,
            context=context,
            available_agents=self._available_agents_for_planning(),
        )
        self._normalize_plan_agents(revised)
        session.current_plan = revised
        session.current_plan_id = revised.plan_id
        session.draft_source = "revised"
        session.status = GoalSessionStatus.AWAITING_APPROVAL
        return session

    async def _resolve_draft_plan(self, task: Dict[str, Any],
                                  session: GoalSession) -> Plan:
        loader = PlanLoader()

        if "plan" in task and isinstance(task["plan"], dict):
            session.draft_source = "provided"
            plan = loader.load_data(task["plan"],
                                    fallback_plan_id=f"inline_{session.session_id}")
        elif task.get("plan_path"):
            session.draft_source = "provided"
            plan = loader.load_path(Path(task["plan_path"]).expanduser())
        elif task.get("plan_id"):
            session.draft_source = "provided"
            plan = PlanRegistry.get_instance().get_plan(str(
                task["plan_id"])).model_copy(deep=True)
        else:
            context = str(task.get("planning_context") or "").strip()
            plan = await self.plan_manager.create_plan(
                goal=session.goal,
                context=context,
                available_agents=self._available_agents_for_planning(),
            )

        if not plan.goal:
            plan.goal = session.goal
        self._normalize_plan_agents(plan)
        return plan

    async def _run_goal_session(self, session: GoalSession) -> GoalSession:
        replan_count = int(session.metadata.get("replan_count", 0))
        max_replans = int(session.metadata.get("max_auto_replans", 3))

        while session.current_plan:
            plan_to_execute = session.current_plan.model_copy(deep=True)
            session.status = GoalSessionStatus.EXECUTING
            await self._save_goal_session(session)

            result = await self.plan_manager.execute_plan(
                plan=plan_to_execute,
                input_data=session.input_data,
                session_id=session.session_id,
                document_path=session.document_path,
                workspace_dir=session.workspace_dir,
            )

            session.current_plan = plan_to_execute
            session.current_plan_id = plan_to_execute.plan_id
            session.task_results = result.get("task_results", {})
            session.task_traces = result.get("task_traces", {})
            session.plan_history.append(plan_to_execute.model_copy(deep=True))
            session.status = GoalSessionStatus.EVALUATING_GOAL
            await self._save_goal_session(session)

            evaluation = await self._evaluate_goal(session, result)
            session.goal_evaluation = evaluation

            if evaluation.goal_achieved:
                session.status = GoalSessionStatus.COMPLETED
                await self._save_goal_session(session)
                return session

            if not session.auto_replan:
                session.status = GoalSessionStatus.AWAITING_USER_INPUT
                await self._save_goal_session(session)
                return session

            if replan_count >= max_replans:
                session.status = GoalSessionStatus.BLOCKED
                await self._save_goal_session(session)
                return session

            replan_count += 1
            session.metadata["replan_count"] = replan_count
            context = self._build_replan_context(session)
            next_plan = await self.plan_manager.create_plan(
                goal=session.goal,
                context=context,
                available_agents=self._available_agents_for_planning(),
            )
            self._normalize_plan_agents(next_plan)
            session.current_plan = next_plan
            session.current_plan_id = next_plan.plan_id

        session.status = GoalSessionStatus.FAILED
        await self._save_goal_session(session)
        return session

    async def _evaluate_goal(self, session: GoalSession,
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
            f"Goal:\n{session.goal}\n\n"
            "Return ONLY JSON with schema:\n"
            '{"goal_achieved": true, "reason": "...", "missing_gaps": ["..."], '
            '"next_action": "complete|replan|ask_user|fail"}\n\n'
            f"Current plan summary:\n{json.dumps(session.current_plan.model_dump(), ensure_ascii=False, default=str) if session.current_plan else '{}'}\n\n"
            f"Execution result:\n{json.dumps(execution_result, ensure_ascii=False, default=str)}\n"
        )
        result = await self.run(prompt, mode=AgentMode.DIRECT)
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
                              session: GoalSession,
                              extra_feedback: str = "") -> str:
        parts = []
        if session.plan_history:
            latest = session.plan_history[-1]
            parts.append(
                f"Most recent executed plan:\n{json.dumps(latest.model_dump(), ensure_ascii=False, default=str)}"
            )
        elif session.current_plan:
            parts.append(
                f"Current draft plan:\n{json.dumps(session.current_plan.model_dump(), ensure_ascii=False, default=str)}"
            )
        if session.goal_evaluation:
            parts.append(
                f"Goal evaluation:\n{json.dumps(session.goal_evaluation.model_dump(), ensure_ascii=False)}"
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

    async def _save_goal_session(self, session: GoalSession) -> None:
        now = datetime.now()
        if not getattr(session, "created_at", None):
            session.created_at = now
        session.updated_at = now
        state = {
            "agent_id": self._session_state_key(session.session_id),
            "state_data": session.model_dump(mode="json"),
        }
        await self.memory_manager.store_agent_state(state)

    async def _load_goal_session(self, session_id: str) -> Optional[GoalSession]:
        state = await self.memory_manager.get_agent_state(
            self._session_state_key(session_id))
        if not state:
            return None

        raw = state.get("state_data")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            return None
        return GoalSession(**raw)

    def _session_state_key(self, session_id: str) -> str:
        return f"goal_session:{session_id}"

    def _generate_goal_session_id(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"goal_{ts}_{uuid.uuid4().hex[:8]}"

    def _direct_session_state_key(self, session_type: SessionType,
                                  session_id: str) -> str:
        return f"{session_type.value}_session:{session_id}"

    def _generate_direct_session_id(self, session_type: SessionType) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{session_type.value}_{ts}_{uuid.uuid4().hex[:8]}"

    def _goal_session_response(self, session: GoalSession) -> Dict[str, Any]:
        progress = (session.current_plan.get_progress()
                    if session.current_plan is not None else None)
        return {
            "session_id":
            session.session_id,
            "session_type":
            SessionType.PLAN.value,
            "status":
            session.status.value,
            "goal":
            session.goal,
            "draft_source":
            session.draft_source,
            "current_plan": (session.current_plan.model_dump(
                mode="json") if session.current_plan else None),
            "plan_history": [p.model_dump(mode="json") for p in session.plan_history],
            "progress":
            progress,
            "goal_evaluation":
            session.goal_evaluation.model_dump(),
            "task_results":
            session.task_results,
            "task_traces":
            session.task_traces,
            "current_task":
            session.metadata.get("current_task"),
            "current_agent":
            session.metadata.get("current_agent"),
            "latest_error":
            session.metadata.get("latest_error"),
            "execution_mode":
            "harness",
            "selected_agent_id":
            session.metadata.get("current_agent"),
            "created_at":
            session.created_at.isoformat(),
            "updated_at":
            session.updated_at.isoformat(),
            "timestamp":
            datetime.now().isoformat(),
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

        session = await self._load_goal_session(session_id)
        if session is None:
            return None
        response = self._goal_session_response(session)
        runtime = await self.plan_manager.get_session_status(session_id)
        if runtime:
            completed_steps = runtime.get("completed_steps", 0)
            total_steps = runtime.get("total_steps", 0)
            current_task = runtime.get("current_task")
            if total_steps and completed_steps >= total_steps:
                current_task = None
            current_agent = None
            if current_task and session.current_plan:
                task = session.current_plan.get_task(current_task)
                current_agent = task.agent_id if task else None

            latest_error = None
            step_results = runtime.get("step_results", {})
            for task_id, result_data in step_results.items():
                result_obj = result_data.get("result") if isinstance(result_data,
                                                                     dict) else None
                error = None
                if isinstance(result_obj, dict):
                    error = result_obj.get("error")
                if error:
                    latest_error = {"task_id": task_id, "error": error}

            response["current_task"] = current_task or response.get("current_task")
            response["current_agent"] = current_agent or response.get("current_agent")
            response["latest_error"] = latest_error or response.get("latest_error")
            response["runtime_progress"] = {
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "progress_percent": runtime.get("progress", 0.0),
            }
        return response

    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = self.memory_manager.storage.db
        try:
            cursor = await db.execute(
                """SELECT agent_id, state_data
                   FROM agent_states
                   WHERE agent_id LIKE 'goal_session:%'
                      OR agent_id LIKE 'chat_session:%'
                      OR agent_id LIKE 'agent_session:%'
                   ORDER BY last_updated DESC
                   LIMIT ?""",
                (limit, ),
            )
            rows = await cursor.fetchall()
        except Exception as exc:
            self.logger.warning("Failed to list goal sessions: %s", exc)
            return []

        sessions: List[Dict[str, Any]] = []
        for row in rows:
            try:
                data = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                state_data = data.get("state_data", data)
                if row[0].startswith("goal_session:"):
                    session = GoalSession(**state_data)
                    sessions.append({
                        "session_id":
                        session.session_id,
                        "session_type":
                        SessionType.PLAN.value,
                        "goal":
                        session.goal,
                        "status":
                        session.status.value,
                        "current_plan_id":
                        session.current_plan_id,
                        "selected_agent_id":
                        session.metadata.get("current_agent"),
                        "updated_at":
                        session.updated_at.isoformat(),
                    })
                else:
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
        payload: Dict[str, Any] = {"session_id": session_id, "approve_plan": True}
        if feedback:
            payload["feedback"] = feedback
        return await self.execute_task(payload)

    async def provide_user_input(self, session_id: str, message: str) -> Dict[str, Any]:
        return await self.execute_task({
            "session_id": session_id,
            "user_input": message
        })

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
        task: Dict[str, Any],
        session_type: SessionType,
    ) -> Dict[str, Any]:
        message = str(
            task.get("message") or task.get("goal") or task.get("description")
            or "").strip()
        if not message:
            return self._error_result(task.get("id", session_id),
                                      "Task description is required")
        return await self.execute_direct_session(
            session_type=session_type,
            message=message,
            agent_id=task.get("agent_id"),
            session_id=session_id,
            image_paths=task.get("image_paths"),
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
            return "未命名会话"
        return clean[:30] + ("..." if len(clean) > 30 else "")

    def _result_to_session_traces(self, session: DirectSession,
                                  result: Dict[str, Any]) -> List[SessionTrace]:
        traces: List[SessionTrace] = []
        for index, step in enumerate(result.get("trace", {}).get("steps", [])):
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
