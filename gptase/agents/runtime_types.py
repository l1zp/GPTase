"""Types for the interactive agent runtime."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class RuntimeStopReason(str, Enum):
    """Terminal conditions for the interactive runtime."""

    FINAL_ANSWER = "final_answer"
    MAX_TURNS = "max_turns"
    NEEDS_USER_INPUT = "needs_user_input"
    ERROR = "error"


class CoordinatorWorkerResult(BaseModel):
    """Structured record of one delegated worker result."""

    model_config = ConfigDict(use_enum_values=True)

    agent_id: str
    status: str = "success"
    content: str = ""
    error: Optional[str] = None


class CoordinatorTurnSummary(BaseModel):
    """Structured record of one runtime turn that delegated worker tasks."""

    model_config = ConfigDict(use_enum_values=True)

    turn_index: int
    delegation_count: int = 0
    delegated_agents: List[str] = Field(default_factory=list)
    worker_results: List[CoordinatorWorkerResult] = Field(default_factory=list)
    assistant_content: str = ""
    stop_reason: Optional[RuntimeStopReason] = None


class CoordinatorRuntimeSummary(BaseModel):
    """Structured summary of runtime delegation activity."""

    model_config = ConfigDict(use_enum_values=True)

    turn_count: int = 0
    delegation_count: int = 0
    delegated_agents: List[str] = Field(default_factory=list)
    worker_results: List[CoordinatorWorkerResult] = Field(default_factory=list)
    turns: List[CoordinatorTurnSummary] = Field(default_factory=list)


class InteractiveToolResult(BaseModel):
    """Normalized trace payload for a single executed tool call."""

    model_config = ConfigDict(use_enum_values=True)

    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    error_type: Optional[str] = None


class InteractiveTurn(BaseModel):
    """One completed runtime turn."""

    model_config = ConfigDict(use_enum_values=True)

    turn_index: int
    assistant_content: str = ""
    reasoning_content: Optional[str] = None
    tool_results: List[InteractiveToolResult] = Field(default_factory=list)
    stop_reason: Optional[RuntimeStopReason] = None


class InteractiveRuntimeSnapshot(BaseModel):
    """Serializable checkpoint for resuming a local planned task."""

    model_config = ConfigDict(use_enum_values=True)

    messages: List[Dict[str, Any]] = Field(default_factory=list)
    turns: List[InteractiveTurn] = Field(default_factory=list)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0


class InteractiveRuntimeResult(BaseModel):
    """Terminal output from the interactive runtime.

    Turn details, steps, and token/duration totals live in `snapshot`.
    """

    model_config = ConfigDict(use_enum_values=True)

    content: str = ""
    reasoning: Optional[str] = None
    stop_reason: RuntimeStopReason
    turn_count: int = 0
    usage: Dict[str, int] = Field(default_factory=dict)
    snapshot: InteractiveRuntimeSnapshot
    error: Optional[str] = None
    coordinator_summary: Optional[CoordinatorRuntimeSummary] = None


class InteractiveSessionState(InteractiveRuntimeSnapshot):
    """Mutable state while a runtime session is executing.

    Extends InteractiveRuntimeSnapshot with runtime control fields.
    """

    model_config = ConfigDict(use_enum_values=True)

    turn_index: int = 0
    max_turns: int = 10
