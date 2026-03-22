"""Goal-oriented harness orchestrator for multi-agent task execution."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
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
from gptase.tools.base import get_tool_registry
from gptase.tools.handlers import DelegateTaskTool
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(
    __file__).resolve().parent.parent.parent / ".claude" / "agents"


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

        system_prompt = "You are the central Agent Orchestrator."
        tools = ["DelegateTask"]

        orchestrator_md = _DEFAULT_CONFIG_DIR / "orchestrator.md"
        if not orchestrator_md.exists():
            orchestrator_md = _DEFAULT_CONFIG_DIR / "orchestrator" / "orchestrator.md"
        if orchestrator_md.exists():
            try:
                definition = Agent._parse_markdown(orchestrator_md.read_text(),
                                                   orchestrator_md.stem)
                system_prompt = definition.system_prompt
                tools = definition.tools
            except Exception as exc:
                logger.warning(
                    "Failed to parse orchestrator.md, using minimal default: %s", exc)

        super().__init__(system_prompt=system_prompt,
                         tools=tools,
                         model_config=self.model_manager.get_config_for_agent("auto")
                         if self.model_manager else None,
                         agent_id="auto")

        self.plan_manager = PlanManager(self, model_manager=self.model_manager)

        registry = get_tool_registry()
        delegate_tool = DelegateTaskTool(orchestrator=self)
        registry.register(delegate_tool, allowed_agents=["auto"])

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
            try:
                definition = Agent._parse_markdown(md_file.read_text(), md_file.stem)
                agent = Agent.from_markdown(md_file, model_manager=self.model_manager)
                agents[agent.agent_id] = agent
                self.agent_descriptions[agent.agent_id] = definition.description
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
                return await self._continue_goal_session(session_id, task)

            description = str(task.get("goal") or task.get("description") or "").strip()
            if not description and not any(k in task for k in ("plan", "plan_id", "plan_path")):
                return self._error_result(task_id, "Task description or plan is required")

            requested_agent_id = task.get("agent_id")
            resolved_agent_id = self._resolve_agent_id(requested_agent_id)
            execution_mode = task.get("execution_mode", "auto")
            if execution_mode == "direct" or (
                    resolved_agent_id and resolved_agent_id != self.agent_id):
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
            return self._error_result(task_id, f"Unknown agent_id: {task.get('agent_id')}")

        task_obj = AgentTask.from_dict({
            **task,
            "agent_id": agent_id,
            "description": task.get("description") or task.get("goal")
            or "Process the following data",
        })
        result = await self.agents[agent_id].process_task_with_mode(task_obj,
                                                                    mode=AgentMode.DIRECT)
        return {
            "task_id": task_id,
            "status": result.get("status", "success"),
            "data": result.get("data"),
            "error": result.get("error"),
            "agent_id": agent_id,
            "execution_mode": "direct",
            "timestamp": datetime.now().isoformat(),
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
        session.status = (GoalSessionStatus.EXECUTING if auto_execute else
                          GoalSessionStatus.AWAITING_APPROVAL)
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
            plan = PlanRegistry.get_instance().get_plan(str(task["plan_id"])).model_copy(
                deep=True)
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

            result = await self.plan_manager.execute_plan(plan=plan_to_execute,
                                                          session_id=session.session_id,
                                                          document_path=session.document_path,
                                                          workspace_dir=session.workspace_dir)

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
            return GoalEvaluation(goal_achieved=False,
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
                goal_achieved=(failed == 0 and completed > 0),
                reason="Used fallback heuristic goal evaluation.",
                missing_gaps=[] if failed == 0 else ["Some tasks failed."],
                next_action="complete" if failed == 0 and completed > 0 else "ask_user",
            )

    def _build_replan_context(self, session: GoalSession,
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
                    raise ValueError(f"Plan references unknown agent_id: {task.agent_id}")
                task.agent_id = resolved

    def _available_agents_for_planning(self) -> List[Dict[str, str]]:
        agents: List[Dict[str, str]] = []
        for agent_id in sorted(self.agents.keys()):
            agents.append({
                "agent_id": agent_id,
                "description": self.agent_descriptions.get(agent_id, ""),
            })
        agents.append({
            "agent_id": self.agent_id,
            "description": "Use only when no specialized worker fits or for synthesis.",
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
        state = {
            "agent_id": self._session_state_key(session.session_id),
            "state_data": session.model_dump(mode="json"),
        }
        await self.memory_manager.store_agent_state(state)

    async def _load_goal_session(self, session_id: str) -> Optional[GoalSession]:
        state = await self.memory_manager.get_agent_state(self._session_state_key(
            session_id))
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

    def _goal_session_response(self, session: GoalSession) -> Dict[str, Any]:
        progress = (session.current_plan.get_progress()
                    if session.current_plan is not None else None)
        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "goal": session.goal,
            "draft_source": session.draft_source,
            "current_plan": (session.current_plan.model_dump(mode="json")
                              if session.current_plan else None),
            "plan_history": [p.model_dump(mode="json") for p in session.plan_history],
            "progress": progress,
            "goal_evaluation": session.goal_evaluation.model_dump(),
            "task_results": session.task_results,
            "task_traces": session.task_traces,
            "current_task": session.metadata.get("current_task"),
            "current_agent": session.metadata.get("current_agent"),
            "latest_error": session.metadata.get("latest_error"),
            "execution_mode": "harness",
            "timestamp": datetime.now().isoformat(),
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

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
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
                result_obj = result_data.get("result") if isinstance(result_data, dict) else None
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
                session = GoalSession(**state_data)
                sessions.append({
                    "session_id": session.session_id,
                    "goal": session.goal,
                    "status": session.status.value,
                    "current_plan_id": session.current_plan_id,
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
        return await self.execute_task({"session_id": session_id, "user_input": message})
