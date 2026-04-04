from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from gptase.agents.types import Plan
from gptase.agents.types import Task
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


class TaskExecutionResult(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    retry_attempts: int = 0
    failure_decision: Optional[FailureDecision] = None


class ExecutionContext(BaseModel):
    plan_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    task_results: Dict[str, TaskExecutionResult] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    active_tasks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    session_id: Optional[str] = None
    document_path: Optional[str] = None
    workspace_dir: Optional[str] = None

    def get_task_result(self, task_id: str) -> Optional[TaskExecutionResult]:
        return self.task_results.get(task_id)

    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        task_res = self.task_results.get(task_id)
        if task_res and task_res.result:
            return task_res.result.data
        return None

    def get_replicated_task_data(self, base_id: str) -> Optional[List[Dict[str, Any]]]:
        """Collect results from replicated tasks matching ``{base_id}_r<N>`` pattern.

        Returns a sorted list of result dicts for replica tasks, or None if no
        replicas are found.  Used by TaskDispatcher to resolve ``{{stepX}}``
        references when step X was defined with ``replicate: N``.
        """
        import re

        pattern = re.compile(rf"^{re.escape(base_id)}_r(\d+)$")
        replicas: List[tuple[int, Dict[str, Any]]] = []
        for task_id in self.task_results:
            match = pattern.match(task_id)
            if match:
                data = self.get_task_data(task_id)
                if data is not None:
                    replicas.append((int(match.group(1)), data))
        replicas.sort(key=lambda item: item[0])
        ordered_data = [data for _, data in replicas]
        return ordered_data if ordered_data else None

    def update_task_result(self, task_id: str, result: TaskExecutionResult) -> None:
        self.task_results[task_id] = result

    def set_variable(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def mark_task_started(self,
                          task_id: str,
                          *,
                          agent_id: Optional[str] = None,
                          started_at: Optional[str] = None) -> None:
        existing = dict(self.active_tasks.get(task_id, {}))
        existing.update({
            "task_id":
            task_id,
            "agent_id":
            agent_id or existing.get("agent_id"),
            "started_at":
            existing.get("started_at") or started_at or datetime.now().isoformat(),
        })
        self.active_tasks[task_id] = existing

    def update_active_task_runtime(
        self,
        task_id: str,
        snapshot: Dict[str, Any],
        turn_index: int,
        *,
        turned_at: Optional[str] = None,
    ) -> None:
        entry = dict(self.active_tasks.get(task_id, {}))
        entry.update({
            "task_id": task_id,
            "runtime_snapshot": snapshot,
            "last_turn_index": turn_index,
            "last_turn_at": turned_at or datetime.now().isoformat(),
        })
        self.active_tasks[task_id] = entry

    def mark_task_finished(self, task_id: str) -> None:
        self.active_tasks.pop(task_id, None)

    def to_result(self) -> Dict[str, Any]:
        results = {}
        traces = {}
        for task_id, task_res in self.task_results.items():
            if task_res.result:
                if task_res.result.data:
                    results[task_id] = task_res.result.data
                if task_res.result.trace:
                    traces[task_id] = task_res.result.trace

        return {
            "plan_id": self.plan_id,
            "status": "success",
            "task_results": results,
            "task_traces": traces,
            "variables": self.variables,
            "session_id": self.session_id,
            "workspace_dir": self.workspace_dir,
            "active_tasks": self.active_tasks,
        }

    def to_checkpoint(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "input_data": self.input_data,
            "document_path": self.document_path,
            "task_results": {
                task_id: result.model_dump()
                for task_id, result in self.task_results.items()
            },
            "variables": self.variables,
            "active_tasks": self.active_tasks,
            "workspace_dir": self.workspace_dir,
        }

    @classmethod
    def from_checkpoint(cls,
                        checkpoint: Dict[str, Any],
                        validate_plan: Optional[Plan] = None) -> "ExecutionContext":
        task_results = {}
        for task_id, result_data in checkpoint.get("task_results", {}).items():
            task_result = None
            if result_data.get("result"):
                task_result = TaskResult(**result_data["result"])

            failure_decision = None
            if result_data.get("failure_decision"):
                failure_decision = FailureDecision(result_data["failure_decision"])

            status = TaskStatus.PENDING
            if result_data.get("status"):
                status = TaskStatus(result_data["status"])

            task_results[task_id] = TaskExecutionResult(
                task_id=task_id,
                status=status,
                result=task_result,
                retry_attempts=result_data.get("retry_attempts", 0),
                failure_decision=failure_decision,
            )

        context = cls(
            plan_id=checkpoint["plan_id"],
            session_id=checkpoint.get("session_id"),
            input_data=checkpoint.get("input_data", {}),
            document_path=checkpoint.get("document_path"),
            task_results=task_results,
            variables=checkpoint.get("variables", {}),
            active_tasks=checkpoint.get("active_tasks", {}),
            workspace_dir=checkpoint.get("workspace_dir"),
        )

        if validate_plan:
            valid_task_ids = {t.task_id for t in validate_plan.tasks}
            invalid_tasks = set(task_results.keys()) - valid_task_ids
            for tid in invalid_tasks:
                context.task_results.pop(tid, None)

        return context


class PlanCheckpoint(BaseModel):
    checkpoint_version: str = "1.0"
    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)

    session_id: str
    plan_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    document_path: Optional[str] = None
    task_results: Dict[str, TaskExecutionResult] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    active_tasks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    workspace_dir: Optional[str] = None

    total_tasks: int = 0
    completed_tasks: int = 0
    status: str = "in_progress"
    plan_hash: Optional[str] = None

    def is_task_completed(self, task_id: str) -> bool:
        result = self.task_results.get(task_id)
        return result is not None and result.status == TaskStatus.COMPLETED

    def get_progress(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
