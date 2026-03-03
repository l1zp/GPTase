"""Pydantic models for SOP definitions and execution.

This module defines all data models used in the SOP system:
- SOPStep: Single workflow step definition
- ParallelStep: Group of parallel steps
- SOPDefinition: Complete SOP workflow definition
- TaskResult: Result from dispatching to an agent
- ExecutionContext: Runtime state during execution
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class FailureDecision(str, Enum):
    """Decision for handling step failures.

    Attributes:
        ABORT: Stop the entire workflow
        SKIP: Skip this step and continue
        RETRY: Retry the step (up to max retries)
    """

    ABORT = "abort"
    SKIP = "skip"
    RETRY = "retry"


class StepStatus(str, Enum):
    """Status of a workflow step.

    Attributes:
        PENDING: Step has not started
        RUNNING: Step is currently executing
        SUCCESS: Step completed successfully
        FAILED: Step failed
        SKIPPED: Step was skipped
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SOPStep(BaseModel):
    """Single workflow step definition.

    Represents one step in an SOP workflow that dispatches to an agent.

    Attributes:
        step_id: Unique identifier for this step (string or int).
        agent: Agent ID to dispatch to.
        action: Action to perform (passed to agent).
        description: Human-readable description of the step.
        inputs: Input mappings with template variables.
        retry_count: Number of retry attempts on failure.
        optional: Whether this step is optional (skip on failure).
    """

    step_id: str
    agent: str
    action: str = "process"
    description: str = ""
    inputs: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    optional: bool = False

    @field_validator("step_id", mode="before")
    @classmethod
    def convert_step_id(cls, v: Union[str, int]) -> str:
        """Convert integer step_id to string.

        Args:
            v: The step ID value (string or integer).
        """
        return str(v)


class ParallelStep(BaseModel):
    """Group of parallel workflow steps.

    Steps in a parallel group execute concurrently and their results
    are collected before proceeding to the next workflow item.

    Attributes:
        parallel: List of steps to execute in parallel.
    """

    parallel: List[SOPStep] = Field(default_factory=list)


# Workflow item can be a single step or a parallel group
WorkflowItem = Union[SOPStep, ParallelStep]


class SOPDefinition(BaseModel):
    """Complete SOP workflow definition.

    Represents a complete Standard Operating Procedure with metadata
    and workflow steps.

    Attributes:
        plan_id: Unique identifier for this SOP.
        name: Human-readable name.
        description: Description of what this SOP does.
        version: Version string.
        workflow: List of workflow items (steps or parallel groups).
        default_retry_count: Default retry count for steps.
        max_parallel: Maximum number of parallel tasks.
    """

    plan_id: str
    name: str = ""
    description: str = ""
    version: str = "1.0"
    workflow: List[WorkflowItem] = Field(default_factory=list)
    default_retry_count: int = Field(default=0, ge=0)
    max_parallel: int = Field(default=10, ge=1)

    @field_validator("workflow", mode="before")
    @classmethod
    def parse_workflow(cls, v: List[Any]) -> List[WorkflowItem]:
        """Parse workflow items from dict to proper types.

        Converts dictionaries to either SOPStep or ParallelStep
        based on the presence of 'parallel' key.

        Args:
            v: List of workflow items (dicts or model instances).
        """
        result = []
        for item in v:
            if isinstance(item, dict):
                if "parallel" in item:
                    # Parse parallel group
                    parallel_steps = []
                    for step_data in item["parallel"]:
                        if isinstance(step_data, dict):
                            parallel_steps.append(SOPStep(**step_data))
                        else:
                            parallel_steps.append(step_data)
                    result.append(ParallelStep(parallel=parallel_steps))
                else:
                    # Parse single step
                    result.append(SOPStep(**item))
            else:
                result.append(item)
        return result

    def get_all_steps(self) -> List[SOPStep]:
        """Get all steps in the workflow, flattening parallel groups.

        Returns:
            List of all SOPStep objects in execution order.
        """
        steps = []
        for item in self.workflow:
            if isinstance(item, ParallelStep):
                steps.extend(item.parallel)
            else:
                steps.append(item)
        return steps

    def get_step_by_id(self, step_id: str) -> Optional[SOPStep]:
        """Find a step by its ID.

        Args:
            step_id: The step ID to search for.

        Returns:
            The matching SOPStep or None if not found.
        """
        for step in self.get_all_steps():
            if step.step_id == step_id:
                return step
        return None


class TaskResult(BaseModel):
    """Result from dispatching a task to an agent.

    Captures the outcome of a single agent dispatch operation.

    Attributes:
        agent_id: ID of the agent that was dispatched to.
        step_id: ID of the workflow step (if applicable).
        action: Action that was performed.
        status: Status of the task (success/failed).
        data: Result data from the agent.
        error: Error message if the task failed.
        execution_time: Time taken to execute in seconds.
    """

    agent_id: str
    step_id: Optional[str] = None
    action: str = "process"
    status: str = "success"
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

    def is_success(self) -> bool:
        """Check if the task succeeded."""
        return self.status == "success"

    def is_failed(self) -> bool:
        """Check if the task failed."""
        return self.status == "failed"


class StepResult(BaseModel):
    """Result of executing a workflow step.

    Tracks the state and output of a step in the workflow.

    Attributes:
        step_id: ID of the executed step.
        status: Status of the step execution.
        result: Task result if step was dispatched.
        retry_attempts: Number of retry attempts made.
        failure_decision: How a failure was handled (if applicable).
    """

    step_id: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[TaskResult] = None
    retry_attempts: int = 0
    failure_decision: Optional[FailureDecision] = None


class ExecutionContext(BaseModel):
    """Runtime state during SOP execution.

    Maintains the state of an SOP execution including input data,
    step results, and variable bindings for template resolution.

    Attributes:
        plan_id: ID of the SOP being executed.
        input_data: Original input to the SOP.
        step_results: Results from completed steps, keyed by step_id.
        variables: Additional variables for template resolution.
        current_step: ID of the currently executing step.
        session_id: Optional session ID for tracking.
        document_path: Optional document path for resolving relative paths.
    """

    plan_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    step_results: Dict[str, StepResult] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    current_step: Optional[str] = None
    session_id: Optional[str] = None
    document_path: Optional[str] = None

    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """Get result for a specific step.

        Args:
            step_id: The step ID to look up.

        Returns:
            StepResult or None if step hasn't been executed.
        """
        return self.step_results.get(step_id)

    def get_step_data(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get the data output from a step.

        Args:
            step_id: The step ID to look up.

        Returns:
            Step output data or None if not available.
        """
        step_result = self.step_results.get(step_id)
        if step_result and step_result.result:
            return step_result.result.data
        return None

    def update_step_result(self, step_id: str, result: StepResult) -> None:
        """Update the result for a step.

        Args:
            step_id: The step ID to update.
            result: The step result to store.
        """
        self.step_results[step_id] = result

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable for template resolution.

        Args:
            name: Variable name.
            value: Variable value.
        """
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable value.

        Args:
            name: Variable name.
            default: Default value if not found.

        Returns:
            Variable value or default.
        """
        return self.variables.get(name, default)

    def to_result(self) -> Dict[str, Any]:
        """Convert context to final result dictionary.

        Returns:
            Dictionary with all step results and aggregated data.
        """
        results = {}
        for step_id, step_result in self.step_results.items():
            if step_result.result and step_result.result.data:
                results[step_id] = step_result.result.data

        return {
            "plan_id": self.plan_id,
            "status": "success",
            "step_results": results,
            "variables": self.variables,
            "session_id": self.session_id,
        }


class FailureContext(BaseModel):
    """Context for failure handling decisions.

    Provides information needed by the FailureHandler to make
    recovery decisions.

    Attributes:
        step: The step that failed.
        error: Error message from the failure.
        context: Current execution context.
        attempt: Current retry attempt number.
        max_retries: Maximum allowed retries.
    """

    step: SOPStep
    error: str
    context: ExecutionContext
    attempt: int = 0
    max_retries: int = 3

    def can_retry(self) -> bool:
        """Check if retry is possible."""
        return self.attempt < self.max_retries
