from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from gptase.agents.types import Plan
from gptase.agents.types import TaskStatus


class FailureDecision(str, Enum):
    ABORT = "abort"
    SKIP = "skip"
    RETRY = "retry"


class TaskResult(BaseModel):
    agent_id: str
    task_id: Optional[str] = None
    action: str = "process"
    status: str = "success"
    data: Optional[Dict[str, Any]] = None
    trace: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    failure_category: Optional[str] = None
    execution_time: Optional[float] = None

    def is_success(self) -> bool:
        return self.status == "success"

    def is_failed(self) -> bool:
        return self.status == "failed"


class TaskAttemptSummary(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    attempt_index: int
    status: TaskStatus = TaskStatus.IN_PROGRESS
    error: Optional[str] = None
    failure_category: Optional[str] = None
    failure_decision: Optional[FailureDecision] = None
    execution_time: Optional[float] = None
    started_at: str
    finished_at: Optional[str] = None


class PlanTaskState(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: str
    agent_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    output: Optional[Dict[str, Any]] = None
    trace: Optional[Dict[str, Any]] = None
    resume_state: Optional[Dict[str, Any]] = None
    attempts: List[TaskAttemptSummary] = Field(default_factory=list)
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    failure_decision: Optional[FailureDecision] = None


class ExecutionContext(BaseModel):
    plan_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    tasks: Dict[str, PlanTaskState] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    document_path: Optional[str] = None
    workspace_dir: Optional[str] = None

    def get_task(self, task_id: str) -> Optional[PlanTaskState]:
        return self.tasks.get(task_id)

    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        task_state = self.tasks.get(task_id)
        return task_state.output if task_state else None

    def get_replicated_task_data(self, base_id: str) -> Optional[List[Dict[str, Any]]]:
        """Collect results from replicated tasks matching ``{base_id}_r<N>`` pattern."""
        import re

        pattern = re.compile(rf"^{re.escape(base_id)}_r(\d+)$")
        replicas: List[tuple[int, Dict[str, Any]]] = []
        for task_id in self.tasks:
            match = pattern.match(task_id)
            if match:
                data = self.get_task_data(task_id)
                if data is not None:
                    replicas.append((int(match.group(1)), data))
        replicas.sort(key=lambda item: item[0])
        ordered_data = [data for _, data in replicas]
        return ordered_data if ordered_data else None

    def upsert_task(self, task_state: PlanTaskState) -> None:
        self.tasks[task_state.task_id] = task_state

    def set_variable(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def begin_task(
        self,
        task_id: str,
        *,
        agent_id: Optional[str] = None,
        started_at: Optional[str] = None,
    ) -> None:
        started = started_at or datetime.now().isoformat()
        task_state = self.tasks.get(task_id) or PlanTaskState(task_id=task_id)
        if task_state.started_at is None:
            task_state.started_at = started
        task_state.agent_id = agent_id or task_state.agent_id
        task_state.status = TaskStatus.IN_PROGRESS
        task_state.updated_at = started
        self.tasks[task_id] = task_state

    def begin_task_attempt(
        self,
        task_id: str,
        *,
        agent_id: Optional[str] = None,
        started_at: Optional[str] = None,
    ) -> TaskAttemptSummary:
        started = started_at or datetime.now().isoformat()
        self.begin_task(task_id, agent_id=agent_id, started_at=started)
        task_state = self.tasks[task_id]
        if task_state.attempts and task_state.attempts[-1].finished_at is None:
            return task_state.attempts[-1]

        attempt = TaskAttemptSummary(
            attempt_index=len(task_state.attempts),
            started_at=started,
        )
        task_state.attempts.append(attempt)
        task_state.updated_at = started
        return attempt

    def update_task_resume_state(
        self,
        task_id: str,
        snapshot: Dict[str, Any],
        *,
        agent_id: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        updated = updated_at or datetime.now().isoformat()
        self.begin_task(task_id, agent_id=agent_id, started_at=updated)
        task_state = self.tasks[task_id]
        task_state.resume_state = snapshot
        task_state.updated_at = updated

    def finalize_task(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        result: Optional[TaskResult] = None,
        failure_decision: Optional[FailureDecision] = None,
        finished_at: Optional[str] = None,
    ) -> None:
        finished = finished_at or datetime.now().isoformat()
        task_state = self.tasks.get(task_id) or PlanTaskState(task_id=task_id)
        task_state.status = status
        task_state.updated_at = finished
        task_state.failure_decision = failure_decision
        task_state.resume_state = None

        if result is not None:
            task_state.agent_id = result.agent_id or task_state.agent_id
            task_state.output = result.data
            task_state.trace = result.trace

        if not task_state.attempts:
            task_state.attempts.append(
                TaskAttemptSummary(
                    attempt_index=0,
                    started_at=task_state.started_at or finished,
                ))

        latest_attempt = task_state.attempts[-1]
        latest_attempt.status = status
        latest_attempt.error = result.error if result else latest_attempt.error
        latest_attempt.failure_category = (result.failure_category if result else
                                           latest_attempt.failure_category)
        latest_attempt.failure_decision = failure_decision
        latest_attempt.execution_time = (result.execution_time
                                         if result else latest_attempt.execution_time)
        latest_attempt.finished_at = finished
        self.tasks[task_id] = task_state

    def to_result(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "status": "success",
            "tasks": {
                task_id: task_state.model_dump(mode="json")
                for task_id, task_state in self.tasks.items()
            },
            "variables": self.variables,
            "session_id": self.session_id,
            "workspace_dir": self.workspace_dir,
        }

    def to_checkpoint(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "input_data": self.input_data,
            "document_path": self.document_path,
            "tasks": {
                task_id: task_state.model_dump(mode="json")
                for task_id, task_state in self.tasks.items()
            },
            "variables": self.variables,
            "workspace_dir": self.workspace_dir,
        }

    @classmethod
    def from_checkpoint(cls,
                        checkpoint: Dict[str, Any],
                        validate_plan: Optional[Plan] = None) -> "ExecutionContext":
        tasks: Dict[str, PlanTaskState] = {}

        if isinstance(checkpoint.get("tasks"), dict):
            for task_id, task_data in checkpoint.get("tasks", {}).items():
                if not isinstance(task_data, dict):
                    continue
                payload = dict(task_data)
                payload.setdefault("task_id", task_id)
                tasks[task_id] = PlanTaskState(**payload)
        else:
            legacy_results = checkpoint.get("task_results", {})
            legacy_active = checkpoint.get("active_tasks", {})
            for task_id, result_data in legacy_results.items():
                if not isinstance(result_data, dict):
                    continue
                task_result = None
                if result_data.get("result"):
                    task_result = TaskResult(**result_data["result"])
                failure_decision = None
                if result_data.get("failure_decision"):
                    failure_decision = FailureDecision(result_data["failure_decision"])
                status = TaskStatus.PENDING
                if result_data.get("status"):
                    status = TaskStatus(result_data["status"])
                task_state = PlanTaskState(
                    task_id=task_id,
                    agent_id=task_result.agent_id if task_result else None,
                    status=status,
                    output=task_result.data if task_result else None,
                    trace=task_result.trace if task_result else None,
                    failure_decision=failure_decision,
                )
                if task_result is not None:
                    now = datetime.now().isoformat()
                    task_state.attempts.append(
                        TaskAttemptSummary(
                            attempt_index=0,
                            status=status,
                            error=task_result.error,
                            failure_category=task_result.failure_category,
                            failure_decision=failure_decision,
                            execution_time=task_result.execution_time,
                            started_at=now,
                            finished_at=now
                            if status != TaskStatus.IN_PROGRESS else None,
                        ))
                tasks[task_id] = task_state

            for task_id, active_data in legacy_active.items():
                if not isinstance(active_data, dict):
                    continue
                task_state = tasks.get(task_id) or PlanTaskState(task_id=task_id)
                task_state.agent_id = active_data.get("agent_id", task_state.agent_id)
                task_state.started_at = active_data.get("started_at",
                                                        task_state.started_at)
                task_state.resume_state = active_data.get("runtime_snapshot")
                if task_state.resume_state:
                    task_state.status = TaskStatus.IN_PROGRESS
                tasks[task_id] = task_state

        context = cls(
            plan_id=checkpoint["plan_id"],
            session_id=checkpoint.get("session_id"),
            input_data=checkpoint.get("input_data", {}),
            document_path=checkpoint.get("document_path"),
            tasks=tasks,
            variables=checkpoint.get("variables", {}),
            workspace_dir=checkpoint.get("workspace_dir"),
        )

        if validate_plan:
            valid_task_ids = {t.task_id for t in validate_plan.tasks}
            invalid_tasks = set(tasks.keys()) - valid_task_ids
            for tid in invalid_tasks:
                context.tasks.pop(tid, None)

        return context


class PlanCheckpoint(BaseModel):
    checkpoint_version: str = "1.0"
    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)

    session_id: str
    plan_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    document_path: Optional[str] = None
    tasks: Dict[str, PlanTaskState] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    workspace_dir: Optional[str] = None

    total_tasks: int = 0
    completed_tasks: int = 0
    status: str = "in_progress"
    plan_hash: Optional[str] = None

    def is_task_completed(self, task_id: str) -> bool:
        result = self.tasks.get(task_id)
        return result is not None and result.status == TaskStatus.COMPLETED

    def get_progress(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
