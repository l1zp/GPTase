"""Plan manager for Agent plan mode.

This module provides the PlanManager class which handles:
1. Using LLM to decompose a user goal into structured tasks
2. Executing tasks in dependency order
3. Tracking plan progress and collecting results
4. Dispatching tasks to specific agents, handling failures, and checkpointing

Plan is the base abstraction for task orchestration. Predefined plans
skip the LLM planning step and execute directly.
"""

import asyncio
from datetime import datetime
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
import uuid

from gptase.agents.base import Agent
from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import FailureDecision
from gptase.agents.execution_types import PlanCheckpoint
from gptase.agents.execution_types import TaskExecutionResult
from gptase.agents.plan_dispatcher import TaskDispatcher
from gptase.agents.plan_failure_handler import FailureHandler
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
from gptase.agents.types import TaskStatus
from gptase.memory.manager import MemoryManager
from gptase.utils.exceptions import AgentInitializationError

if TYPE_CHECKING:
    from gptase.agents.base import Agent

logger = logging.getLogger(__name__)

_PLAN_OUTPUT_SCHEMA = """\
Output a JSON object with this exact schema:
```json
{
  "summary": "Brief overview of the plan strategy",
  "max_parallel": 3,
  "default_retry_count": 1,
  "tasks": [
    {
      "task_id": "1",
      "description": "What this task should accomplish",
      "reasoning": "Why this task is needed",
      "dependencies": [],
      "agent_id": "specialized-agent-id",
      "action": "process",
      "inputs": {},
      "expected_output": "What the output should look like"
    }
  ]
}
```"""

_PLANNING_SYSTEM_ADDENDUM = f"""\

## Task Planning Instructions

When asked to create a plan, decompose the goal into a sequence of
atomic, actionable tasks. Each task should be completable in a single
agent execution step.

Rules:
- Tasks must be atomic — one clear action each.
- Specify dependencies to ensure correct execution order.
- Use string task IDs (e.g. "1", "2", "3").
- Each task must be assignable to exactly one agent_id.
- Each task must be completable by a single subagent using its own internal multi-turn agent loop.
- You may use available tools to gather planning context, but do not execute the user's full task during planning.
- Tool use during planning is only for evidence gathering, scoping, and validating the draft plan.
- Return ONLY valid JSON, no extra text or markdown fences outside the JSON block.

{_PLAN_OUTPUT_SCHEMA}
"""


class PlanExecutionError(Exception):

    def __init__(self, plan_id: str, reason: str, details: Optional[Dict] = None):
        super().__init__(f"Plan execution failed [{plan_id}]: {reason}")
        self.plan_id = plan_id
        self.reason = reason
        self.details = details or {}


class PlanManager:
    """Manages plan generation and execution for an Agent.

    The PlanManager is composed into an Agent instance (not inherited).
    It uses the agent's LLM to generate plans and the dispatcher to
    execute individual tasks.

    Attributes:
        agent: The owning Agent instance.
        current_plan: The plan currently being managed.
    """

    def __init__(self, agent: "Agent", model_manager: Optional[Any] = None):
        self.agent = agent
        self.model_manager = model_manager
        self.current_plan: Optional[Plan] = None
        self.logger = logging.getLogger(
            f"{__name__}.{agent.agent_id}" if agent.agent_id else __name__)

        self.dispatcher = TaskDispatcher(
            memory_manager=MemoryManager(),
            model_manager=model_manager,
        )
        self.failure_handler = FailureHandler(model=model_manager)
        self._planner_agent: Optional[Agent] = None

    async def close(self) -> None:
        """Release planner-owned resources."""
        await self.dispatcher.close()

    async def create_plan(
        self,
        description: str,
        context: str = "",
        available_agents: Optional[List[Dict[str, str]]] = None,
    ) -> Plan:
        self.logger.info("Creating plan for: %s", description[:100])

        planning_prompt = f"Create a plan for the following goal:\n\n{description}"
        if context:
            planning_prompt += f"\n\nAdditional context:\n{context}"
        if available_agents:
            planning_prompt += "\n\nAvailable agents:\n"
            for agent in available_agents:
                agent_id = agent.get("agent_id", "")
                agent_desc = agent.get("description", "")
                planning_prompt += f"- {agent_id}: {agent_desc}\n"
        planning_prompt += (
            "\n\nRespond with ONLY a JSON object matching the schema described "
            "in your instructions. Do not include markdown fences.")

        planner_agent = self._get_planner_agent()
        result = await planner_agent.run(planning_prompt)

        if result.get("status") != "success":
            raise ValueError(f"Planning failed: {result.get('error', 'Unknown error')}")

        content = result.get("data", {}).get("content", "")
        if not content:
            raise ValueError("Planning returned empty content")

        plan = self._parse_plan_output(content, description)
        self._validate_dependencies(plan)

        self.current_plan = plan

        self.logger.info(
            "Plan created: %s with %d tasks",
            plan.plan_id,
            len(plan.tasks),
        )
        return plan

    async def execute_plan(
        self,
        plan: Plan,
        input_data: Optional[Dict[str, Any]] = None,
        context_checkpoint: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        document_path: Optional[str] = None,
        auto_checkpoint: bool = True,
        on_task_complete: Optional[Callable[[PlannedTask], Any]] = None,
    ) -> Dict[str, Any]:
        """Execute all tasks in the plan respecting dependencies."""
        plan.status = "executing"
        plan.updated_at = datetime.now()
        self.current_plan = plan
        input_data = input_data or {}

        if context_checkpoint:
            context = ExecutionContext.from_checkpoint(context_checkpoint,
                                                       validate_plan=plan)
            self._sync_plan_status_from_context(plan, context)
            self.logger.info("Restored plan context from checkpoint: %s",
                             context.session_id)
        elif session_id:
            stored_checkpoint = await self._load_checkpoint_from_db(session_id)
            if stored_checkpoint:
                context = ExecutionContext.from_checkpoint(stored_checkpoint,
                                                           validate_plan=plan)
                self._sync_plan_status_from_context(plan, context)
                self.logger.info("Resumed plan session: %s", session_id)
            else:
                session_id = session_id or self._generate_session_id()
                context = ExecutionContext(
                    plan_id=plan.plan_id,
                    input_data=input_data,
                    document_path=document_path,
                    session_id=session_id,
                    workspace_dir=workspace_dir,
                )
        else:
            session_id = session_id or self._generate_session_id()
            context = ExecutionContext(
                plan_id=plan.plan_id,
                input_data=input_data,
                document_path=document_path,
                session_id=session_id,
                workspace_dir=workspace_dir,
            )

        context.set_variable("input_data", input_data)
        if "text" in input_data:
            context.set_variable("input_text", input_data["text"])

        self.logger.info(
            "Starting plan execution: %s (%d tasks)",
            plan.plan_id,
            len(plan.tasks),
        )

        if auto_checkpoint:
            await self._save_checkpoint_to_db(context, plan, "in_progress")

        try:
            while not plan.is_complete():
                next_tasks = plan.get_next_tasks()

                if not next_tasks:
                    remaining = [
                        t for t in plan.tasks
                        if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
                    ]
                    if remaining:
                        self.logger.error(
                            "Plan deadlock: %d tasks stuck with unmet dependencies",
                            len(remaining),
                        )
                        plan.status = "failed"
                        break
                    break

                tasks_to_run = next_tasks[:plan.max_parallel]
                for task in tasks_to_run:
                    task.status = TaskStatus.IN_PROGRESS
                    context.mark_task_started(task.task_id, agent_id=task.agent_id)

                if auto_checkpoint:
                    await self._save_checkpoint_to_db(context, plan, "in_progress")

                async def checkpointing_callback(completed_task: PlannedTask) -> None:
                    if on_task_complete:
                        maybe_awaitable = on_task_complete(completed_task)
                        if inspect.isawaitable(maybe_awaitable):
                            await maybe_awaitable
                    if auto_checkpoint:
                        await self._save_checkpoint_to_db(context, plan, "in_progress")

                async def turn_checkpointing_callback(
                    task_id: str,
                    snapshot: InteractiveRuntimeSnapshot,
                    turn_index: int,
                ) -> None:
                    context.update_active_task_runtime(
                        task_id,
                        snapshot.model_dump(mode="json"),
                        turn_index,
                    )
                    if auto_checkpoint:
                        await self._save_checkpoint_to_db(context, plan, "in_progress")

                execution_coros = [
                    self._execute_single_task(task, plan, context,
                                              checkpointing_callback,
                                              turn_checkpointing_callback)
                    for task in tasks_to_run
                ]
                await asyncio.gather(*execution_coros)

                if auto_checkpoint:
                    await self._save_checkpoint_to_db(context, plan, "in_progress")

            progress = plan.get_progress()
            if progress["failed"] > 0:
                plan.status = "failed"
            else:
                plan.status = "completed"

            plan.updated_at = datetime.now()

            if auto_checkpoint:
                await self._save_checkpoint_to_db(context, plan, plan.status)

            self.logger.info(
                "Plan execution finished: %s (status=%s, %d/%d completed)",
                plan.plan_id,
                plan.status,
                progress["completed"],
                progress["total"],
            )

            result_dict = context.to_result()
            result_dict["progress"] = progress
            result_dict["status"] = plan.status
            return result_dict

        except Exception as e:
            self.logger.error("Plan execution failed: %s", e)
            plan.status = "failed"
            plan.updated_at = datetime.now()
            if auto_checkpoint:
                await self._save_checkpoint_to_db(context, plan, "failed")
            raise PlanExecutionError(plan.plan_id, str(e)) from e

    async def _execute_single_task(
        self,
        task: PlannedTask,
        plan: Plan,
        context: ExecutionContext,
        on_task_complete: Optional[Callable[[PlannedTask], Any]] = None,
        on_task_turn: Optional[Callable[[str, InteractiveRuntimeSnapshot, int],
                                        Any]] = None,
    ) -> None:
        self.logger.info("Executing task '%s': %s", task.task_id, task.description[:80])

        task_res = TaskExecutionResult(task_id=task.task_id,
                                       status=TaskStatus.IN_PROGRESS)
        context.update_task_result(task.task_id, task_res)

        attempt = 0
        max_retries = task.retry_count or plan.default_retry_count or 0

        while True:
            try:
                if task.agent_id and task.agent_id != self.agent.agent_id:
                    result = await self.dispatcher.dispatch(task, context)
                else:
                    result = await self._execute_local_task(
                        task,
                        plan,
                        context,
                        on_task_turn=on_task_turn,
                    )

                if result.is_success():
                    task.status = TaskStatus.COMPLETED
                    task.result = result.data

                    task_res.status = TaskStatus.COMPLETED
                    task_res.result = result
                    task_res.retry_attempts = attempt
                    context.update_task_result(task.task_id, task_res)
                    context.mark_task_finished(task.task_id)

                    self.logger.info("Task '%s' completed successfully", task.task_id)
                    break

                error_msg = result.error or "Unknown error"
                decision = await self.failure_handler.decide(task, error_msg, context,
                                                             attempt)
                task_res.failure_decision = decision
                task_res.result = result

                if decision == FailureDecision.ABORT:
                    self.logger.error("Task '%s' failure is critical, aborting plan",
                                      task.task_id)
                    task.status = TaskStatus.FAILED
                    task.error = error_msg
                    task_res.status = TaskStatus.FAILED
                    context.update_task_result(task.task_id, task_res)
                    context.mark_task_finished(task.task_id)
                    raise PlanExecutionError(
                        plan.plan_id, f"Task {task.task_id} aborted: {error_msg}")

                if decision == FailureDecision.SKIP:
                    self.logger.info("Skipping failed task '%s'", task.task_id)
                    task.status = TaskStatus.SKIPPED
                    task.error = error_msg
                    task_res.status = TaskStatus.SKIPPED
                    context.update_task_result(task.task_id, task_res)
                    context.mark_task_finished(task.task_id)
                    break

                if decision == FailureDecision.RETRY:
                    attempt += 1
                    if attempt > max_retries:
                        self.logger.error(
                            "Max retries exceeded for task '%s', aborting",
                            task.task_id)
                        task.status = TaskStatus.FAILED
                        task.error = error_msg
                        task_res.status = TaskStatus.FAILED
                        context.update_task_result(task.task_id, task_res)
                        context.mark_task_finished(task.task_id)
                        raise PlanExecutionError(
                            plan.plan_id, f"Task {task.task_id} max retries exceeded.")
                    self.logger.info("Retrying task '%s' (attempt %d/%d)", task.task_id,
                                     attempt, max_retries)
                    continue

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task_res.status = TaskStatus.FAILED
                task_res.result = None
                context.update_task_result(task.task_id, task_res)
                context.mark_task_finished(task.task_id)
                self.logger.error("Task '%s' raised exception: %s", task.task_id, e)
                raise

        if on_task_complete:
            maybe_awaitable = on_task_complete(task)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

    async def _execute_local_task(
        self,
        task: PlannedTask,
        plan: Plan,
        context: ExecutionContext,
        on_task_turn: Optional[Callable[[str, InteractiveRuntimeSnapshot, int],
                                        Any]] = None,
    ) -> "TaskResult":
        import time

        from gptase.agents.execution_types import TaskResult
        start = time.time()

        prompt = self._build_task_prompt(task, plan)
        active_task = context.active_tasks.get(task.task_id, {})
        resume_snapshot = active_task.get("runtime_snapshot")
        if resume_snapshot:
            try:
                snapshot = InteractiveRuntimeSnapshot.model_validate(resume_snapshot)
                if not snapshot.turns:
                    resume_snapshot = None
            except Exception:
                resume_snapshot = None

        async def _runtime_turn_callback(snapshot: InteractiveRuntimeSnapshot,
                                         turn: Any) -> None:
            if on_task_turn is None:
                return
            maybe_awaitable = on_task_turn(task.task_id, snapshot, turn.turn_index)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

        run_kwargs: Dict[str, Any] = {}
        if resume_snapshot is not None:
            run_kwargs["_resume_snapshot"] = resume_snapshot
        if on_task_turn is not None:
            run_kwargs["_on_turn_complete"] = _runtime_turn_callback

        try:
            try:
                result = await self.agent.run(prompt, **run_kwargs)
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise
                result = await self.agent.run(prompt)
            dt = time.time() - start
            return TaskResult(agent_id=self.agent.agent_id,
                              task_id=task.task_id,
                              action=task.action,
                              status=result.get("status", "success"),
                              data=result.get("data", {}),
                              trace=result.get("trace"),
                              error=result.get("error"),
                              execution_time=dt)
        except Exception as e:
            dt = time.time() - start
            return TaskResult(agent_id=self.agent.agent_id,
                              task_id=task.task_id,
                              action=task.action,
                              status="failed",
                              error=str(e),
                              execution_time=dt)

    def _build_task_prompt(self, task: PlannedTask, plan: Plan) -> str:
        parts = [
            f"## Plan Goal\n{plan.goal}\n",
            f"## Current Task (ID: {task.task_id})\n{task.description}\n",
        ]

        if task.expected_output:
            parts.append(f"## Expected Output\n{task.expected_output}\n")

        if task.dependencies:
            dep_context = []
            for dep_id in task.dependencies:
                dep_task = plan.get_task(dep_id)
                if dep_task and dep_task.result:
                    content = dep_task.result.get("content", "")
                    if content:
                        dep_context.append(f"### Result from Task {dep_id}\n{content}")
            if dep_context:
                parts.append("## Context from Previous Tasks\n"
                             + "\n\n".join(dep_context))

        if task.inputs:
            parts.append(
                f"## Additional Inputs\n```json\n{json.dumps(task.inputs, indent=2, ensure_ascii=False)}\n```"
            )

        parts.append("\nComplete this task according to the instructions above.")
        return "\n".join(parts)

    def _parse_plan_output(self, content: str, description: str) -> Plan:
        json_str = self._extract_json(content)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse plan JSON: {e}\nContent: {content[:500]}") from e

        if not isinstance(data, dict) or "tasks" not in data or not isinstance(
                data["tasks"], list):
            raise ValueError(
                "Plan output must be a well-structured JSON object with a 'tasks' array"
            )

        tasks = []
        for task_data in data["tasks"]:
            if not isinstance(
                    task_data, dict
            ) or "task_id" not in task_data or "description" not in task_data:
                continue
            tasks.append(
                PlannedTask(
                    task_id=str(task_data["task_id"]),
                    description=task_data["description"],
                    reasoning=task_data.get("reasoning"),
                    dependencies=[str(d) for d in task_data.get("dependencies", [])],
                    agent_id=task_data.get("agent_id"),
                    action=task_data.get("action", "process"),
                    tools=task_data.get("tools"),
                    inputs=task_data.get("inputs", {}),
                    expected_output=task_data.get("expected_output"),
                    retry_count=task_data.get("retry_count", 0),
                    optional=task_data.get("optional", False),
                ))

        if not tasks:
            raise ValueError("Plan contains no valid tasks")

        return Plan(
            goal=description,
            summary=data.get("summary", ""),
            tasks=tasks,
            max_parallel=data.get("max_parallel", 10),
            default_retry_count=data.get("default_retry_count", 0),
        )

    def _extract_json(self, content: str) -> str:
        content = content.strip()
        if "```json" in content:
            parts = content.split("```json", 1)
            if len(parts) > 1:
                return parts[1].split("```", 1)[0].strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 3:
                json_part = parts[1]
                if "\n" in json_part:
                    json_part = json_part.split("\n", 1)[1]
                return json_part.strip()
        if content.startswith("{") or content.startswith("["):
            return content
        brace_start = content.find("{")
        if brace_start != -1:
            depth = 0
            for i in range(brace_start, len(content)):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return content[brace_start:i + 1]
        return content

    def _validate_dependencies(self, plan: Plan) -> None:
        task_ids = {t.task_id for t in plan.tasks}
        for task in plan.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    self.logger.warning(
                        "Task '%s' depends on unknown task '%s', removing",
                        task.task_id, dep)
                    task.dependencies.remove(dep)

        visited: set = set()
        rec_stack: set = set()

        def has_cycle(t_id: str) -> bool:
            visited.add(t_id)
            rec_stack.add(t_id)
            tk = plan.get_task(t_id)
            if tk:
                for d in tk.dependencies:
                    if d not in visited:
                        if has_cycle(d):
                            return True
                    elif d in rec_stack:
                        return True
            rec_stack.discard(t_id)
            return False

        for task in plan.tasks:
            if task.task_id not in visited:
                if has_cycle(task.task_id):
                    raise ValueError(
                        f"Circular dependency detected involving task '{task.task_id}'")

    @staticmethod
    def get_planning_system_addendum() -> str:
        return _PLANNING_SYSTEM_ADDENDUM

    def _get_planner_agent(self) -> Agent:
        """Return the dedicated planner agent, or a safe fallback."""
        if self._planner_agent is not None:
            return self._planner_agent

        # In tests and other lightweight contexts, reuse the parent agent if we
        # cannot safely construct a standalone planner.
        if not isinstance(self.agent, Agent) and self.model_manager is None:
            self._planner_agent = self.agent
            return self._planner_agent

        if self.model_manager is None and getattr(self.agent, "model_config",
                                                  None) is None:
            self._planner_agent = self.agent
            return self._planner_agent

        try:
            planner_agent = Agent.from_markdown(
                "planner",
                model_manager=self.model_manager,
            )
        except AgentInitializationError:
            planner_agent = Agent(
                system_prompt=
                "You are a planning specialist. Produce executable draft plans.",
                tools=[
                    "Read",
                    "Grep",
                    "Glob",
                    "Bash",
                    "brave-search__brave_web_search",
                    "tavily-search__tavily_search",
                    "tavily-search__tavily_extract",
                ],
                model_config=getattr(self.agent, "model_config", None),
                model_name=getattr(self.agent, "_model_name", None),
                agent_id=(f"{self.agent.agent_id}_planner"
                          if self.agent.agent_id else "planner"),
                max_iterations=6,
            )

        planner_agent.system_prompt = (
            f"{planner_agent.system_prompt.rstrip()}\n\n{self.get_planning_system_addendum()}"
        )
        self._planner_agent = planner_agent
        return self._planner_agent

    def _sync_plan_status_from_context(self, plan: Plan,
                                       context: "ExecutionContext") -> None:
        """Sync task statuses from context back into the plan for resume.

        When resuming from a checkpoint, the plan object is freshly loaded
        (all tasks PENDING). This method restores task statuses so the
        execution loop correctly skips completed tasks and retries failed ones.

        Resume semantics:
        - COMPLETED: keep as COMPLETED (skip on re-run)
        - FAILED / IN_PROGRESS: reset to PENDING (retry from this point)
        """
        for task_id, exec_result in context.task_results.items():
            task = plan.get_task(task_id)
            if task is None:
                continue
            if exec_result.status == TaskStatus.COMPLETED:
                task.status = TaskStatus.COMPLETED
                if exec_result.result is not None:
                    task.result = exec_result.result.data
            else:
                # FAILED or IN_PROGRESS: reset so the task is retried
                task.status = TaskStatus.PENDING

        resumable_active_tasks = {}
        for task_id, active_data in context.active_tasks.items():
            exec_result = context.task_results.get(task_id)
            if exec_result is None or exec_result.status == TaskStatus.COMPLETED:
                continue
            if isinstance(active_data, dict) and active_data.get("runtime_snapshot"):
                resumable_active_tasks[task_id] = active_data
        context.active_tasks = resumable_active_tasks

    def _generate_session_id(self) -> str:
        return f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def _save_checkpoint_to_db(self,
                                     context: ExecutionContext,
                                     plan: Plan,
                                     status: str = "in_progress") -> str:
        total_tasks = len(plan.tasks)
        completed_tasks = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)

        checkpoint = PlanCheckpoint(
            session_id=context.session_id,
            plan_id=context.plan_id,
            input_data=context.input_data,
            document_path=context.document_path,
            task_results=context.task_results,
            variables=context.variables,
            active_tasks=context.active_tasks,
            status=status,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
        )

        checkpoint_data = checkpoint.model_dump()
        checkpoint_data["created_at"] = checkpoint.created_at.isoformat()
        now = datetime.now().isoformat()

        try:
            db = self.dispatcher.memory_manager.storage.db
            await db.execute(
                """INSERT OR REPLACE INTO plan_checkpoints
                   (checkpoint_id, session_id, plan_id, created_at, updated_at,
                    checkpoint_data, status, total_steps, completed_steps)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    checkpoint.checkpoint_id,
                    checkpoint.session_id,
                    checkpoint.plan_id,
                    checkpoint.created_at.isoformat(),
                    now,
                    json.dumps(checkpoint_data),
                    checkpoint.status,
                    checkpoint.total_tasks,
                    checkpoint.completed_tasks,
                ),
            )
            await db.commit()
            self.logger.debug("Saved plan checkpoint: %s (progress: %d/%d)",
                              checkpoint.session_id, completed_tasks, total_tasks)
        except Exception as e:
            self.logger.warning("Failed to save checkpoint: %s", e)

        return checkpoint.checkpoint_id

    async def _load_checkpoint_from_db(self,
                                       session_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = self.dispatcher.memory_manager.storage.db
            cursor = await db.execute(
                "SELECT checkpoint_data FROM plan_checkpoints WHERE session_id = ?",
                (session_id, ))
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
        except Exception as e:
            self.logger.warning("Failed to load checkpoint: %s", e)
        return None

    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            db = self.dispatcher.memory_manager.storage.db
            cursor = await db.execute(
                "SELECT session_id, plan_id, status, completed_tasks, total_tasks, updated_at FROM plan_checkpoints ORDER BY updated_at DESC LIMIT ?",
                (limit, ))
            rows = await cursor.fetchall()
            sessions = []
            for r in rows:
                if r[4] > 0:
                    prog = round((r[3] / r[4]) * 100, 1)
                else:
                    prog = 0.0
                sessions.append({
                    "session_id": r[0],
                    "plan_id": r[1],
                    "status": r[2],
                    "completed_steps": r[3],
                    "total_steps": r[4],
                    "progress": prog,
                })
            return sessions
        except Exception as e:
            self.logger.warning("Failed to list sessions: %s", e)
            return []

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = self.dispatcher.memory_manager.storage.db
            cursor = await db.execute(
                "SELECT checkpoint_data FROM plan_checkpoints WHERE session_id = ?",
                (session_id, ))
            row = await cursor.fetchone()
            if row:
                data = json.loads(row[0])
                task_results = data.get("task_results", {})
                failed_steps = 0
                in_progress_steps = 0
                completed_steps = data.get("completed_tasks", 0)
                for result_data in task_results.values():
                    if not isinstance(result_data, dict):
                        continue
                    status = result_data.get("status")
                    if status == TaskStatus.FAILED.value:
                        failed_steps += 1
                    elif status == TaskStatus.IN_PROGRESS.value:
                        in_progress_steps += 1
                if data.get("total_tasks", 0) > 0:
                    prog = round(
                        (data.get("completed_tasks", 0) / data.get("total_tasks", 1))
                        * 100, 1)
                else:
                    prog = 0.0
                pending_steps = max(
                    data.get("total_tasks", 0) - completed_steps - failed_steps
                    - in_progress_steps, 0)
                data["completed_steps"] = completed_steps
                data["total_steps"] = data.get("total_tasks", 0)
                data["failed_steps"] = failed_steps
                data["pending_steps"] = pending_steps
                data["in_progress_steps"] = in_progress_steps
                data["progress"] = prog
                data["step_results"] = task_results
                data["active_tasks"] = data.get("active_tasks", {})
                data["active_agent_ids"] = sorted({
                    details.get("agent_id")
                    for details in data["active_tasks"].values()
                    if isinstance(details, dict) and details.get("agent_id")
                })
                return data
        except Exception as e:
            self.logger.warning("Failed to get session status: %s", e)
        return None
