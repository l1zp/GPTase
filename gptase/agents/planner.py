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
import json
import logging
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
import uuid

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import FailureDecision
from gptase.agents.execution_types import PlanCheckpoint
from gptase.agents.execution_types import TaskExecutionResult
from gptase.agents.plan_dispatcher import TaskDispatcher
from gptase.agents.plan_failure_handler import FailureHandler
from gptase.agents.types import AgentMode
from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
from gptase.agents.types import TaskStatus
from gptase.memory.manager import MemoryManager

if TYPE_CHECKING:
    from gptase.agents.base import Agent

logger = logging.getLogger(__name__)

_PLAN_OUTPUT_SCHEMA = """\
Output a JSON object with this exact schema:
```json
{
  "summary": "Brief overview of the plan strategy",
  "tasks": [
    {
      "task_id": "1",
      "description": "What this task should accomplish",
      "reasoning": "Why this task is needed",
      "dependencies": [],
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
        self.current_plan: Optional[Plan] = None
        self.logger = logging.getLogger(
            f"{__name__}.{agent.agent_id}" if agent.agent_id else __name__)

        self.dispatcher = TaskDispatcher(
            memory_manager=MemoryManager(),
            model_manager=model_manager,
        )
        self.failure_handler = FailureHandler(model=model_manager)

    async def create_plan(
        self,
        goal: str,
        context: str = "",
    ) -> Plan:
        self.logger.info("Creating plan for goal: %s", goal[:100])

        planning_prompt = f"Create a plan for the following goal:\n\n{goal}"
        if context:
            planning_prompt += f"\n\nAdditional context:\n{context}"
        planning_prompt += (
            "\n\nRespond with ONLY a JSON object matching the schema described "
            "in your instructions. Do not include markdown fences.")

        result = await self.agent.run(planning_prompt, mode=AgentMode.DIRECT)

        if result.get("status") != "success":
            raise ValueError(f"Planning failed: {result.get('error', 'Unknown error')}")

        content = result.get("data", {}).get("content", "")
        if not content:
            raise ValueError("Planning returned empty content")

        plan = self._parse_plan_output(content, goal)
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
        on_task_complete: Optional[Callable[[PlannedTask], None]] = None,
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

                execution_coros = [
                    self._execute_single_task(task, plan, context, on_task_complete)
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
        on_task_complete: Optional[Callable[[PlannedTask], None]] = None,
    ) -> None:
        self.logger.info("Executing task '%s': %s", task.task_id, task.description[:80])
        context.current_task = task.task_id

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
                    result = await self._execute_local_task(task, plan, context)

                if result.is_success():
                    task.status = TaskStatus.COMPLETED
                    task.result = result.data

                    task_res.status = TaskStatus.COMPLETED
                    task_res.result = result
                    task_res.retry_attempts = attempt
                    context.update_task_result(task.task_id, task_res)

                    self.logger.info("Task '%s' completed successfully", task.task_id)
                    break

                error_msg = result.error or "Unknown error"
                decision = await self.failure_handler.decide(task, error_msg, context,
                                                             attempt)
                task_res.failure_decision = decision

                if decision == FailureDecision.ABORT:
                    self.logger.error("Task '%s' failure is critical, aborting plan",
                                      task.task_id)
                    task.status = TaskStatus.FAILED
                    task.error = error_msg
                    task_res.status = TaskStatus.FAILED
                    context.update_task_result(task.task_id, task_res)
                    raise PlanExecutionError(
                        plan.plan_id, f"Task {task.task_id} aborted: {error_msg}")

                if decision == FailureDecision.SKIP:
                    self.logger.info("Skipping failed task '%s'", task.task_id)
                    task.status = TaskStatus.SKIPPED
                    task.error = error_msg
                    task_res.status = TaskStatus.SKIPPED
                    context.update_task_result(task.task_id, task_res)
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
                self.logger.error("Task '%s' raised exception: %s", task.task_id, e)
                raise

        if on_task_complete:
            on_task_complete(task)

    async def _execute_local_task(self, task: PlannedTask, plan: Plan,
                                  context: ExecutionContext) -> "TaskResult":
        import time

        from gptase.agents.execution_types import TaskResult
        start = time.time()

        prompt = self._build_task_prompt(task, plan)
        try:
            result = await self.agent.run(prompt, mode=AgentMode.DIRECT)
            dt = time.time() - start
            return TaskResult(agent_id=self.agent.agent_id,
                              task_id=task.task_id,
                              action=task.action,
                              status=result.get("status", "success"),
                              data=result.get("data", {}),
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

    def _parse_plan_output(self, content: str, goal: str) -> Plan:
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
                    expected_output=task_data.get("expected_output"),
                    inputs=task_data.get("inputs", {}),
                ))

        if not tasks:
            raise ValueError("Plan contains no valid tasks")

        return Plan(
            goal=goal,
            summary=data.get("summary", ""),
            tasks=tasks,
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
            current_task=context.current_task,
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
                if data.get("total_tasks", 0) > 0:
                    prog = round(
                        (data.get("completed_tasks", 0) / data.get("total_tasks", 1))
                        * 100, 1)
                else:
                    prog = 0.0
                data["completed_steps"] = data.get("completed_tasks", 0)
                data["total_steps"] = data.get("total_tasks", 0)
                data["progress"] = prog
                data["step_results"] = data.get("task_results", {})
                return data
        except Exception as e:
            self.logger.warning("Failed to get session status: %s", e)
        return None
