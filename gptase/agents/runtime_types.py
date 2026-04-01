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
    NEEDS_PLAN = "needs_plan"
    ERROR = "error"


class PlanHandoffProposal(BaseModel):
    """Structured recommendation to hand work off to plan mode."""

    model_config = ConfigDict(use_enum_values=True)

    reason: str = ""
    goal: str = ""
    planning_context: str = ""
    evidence_summary: str = ""
    suggested_next_step: str = ""


class InteractiveToolResult(BaseModel):
    """Normalized trace payload for a single executed tool call."""

    model_config = ConfigDict(use_enum_values=True)

    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    raw_arguments: Optional[str] = None
    content: str = ""
    result_chars: int = 0
    stored_result_chars: int = 0
    result_truncated: bool = False
    duration_ms: int = 0
    error_type: Optional[str] = None


class InteractiveTurn(BaseModel):
    """One completed runtime turn."""

    model_config = ConfigDict(use_enum_values=True)

    turn_index: int
    assistant_content: str = ""
    reasoning_content: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    tool_results: List[InteractiveToolResult] = Field(default_factory=list)
    usage: Dict[str, int] = Field(default_factory=dict)
    duration_ms: int = 0
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
    """Terminal output from the interactive runtime."""

    model_config = ConfigDict(use_enum_values=True)

    content: str = ""
    reasoning: Optional[str] = None
    stop_reason: RuntimeStopReason
    turn_count: int = 0
    turns: List[InteractiveTurn] = Field(default_factory=list)
    usage: Dict[str, int] = Field(default_factory=dict)
    snapshot: InteractiveRuntimeSnapshot
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error: Optional[str] = None
    plan_handoff: Optional[PlanHandoffProposal] = None


class InteractiveSessionState(BaseModel):
    """Mutable state while a runtime session is executing."""

    model_config = ConfigDict(use_enum_values=True)

    messages: List[Dict[str, Any]] = Field(default_factory=list)
    turns: List[InteractiveTurn] = Field(default_factory=list)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    turn_index: int = 0
    max_turns: int = 10
    allowed_tools: List[str] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
