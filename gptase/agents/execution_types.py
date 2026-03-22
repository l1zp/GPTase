from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
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
    current_task: Optional[str] = None
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

    def update_task_result(self, task_id: str, result: TaskExecutionResult) -> None:
        self.task_results[task_id] = result

    def set_variable(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

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
            "current_task": self.current_task,
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
            current_task=checkpoint.get("current_task"),
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
    current_task: Optional[str] = None
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
