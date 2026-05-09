"""Type definitions for the Agent module."""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


@dataclass
class AgentDefinition:
    """Parsed agent definition from markdown with YAML frontmatter.

    Attributes:
        name: Unique identifier for the agent.
        description: Human-readable description of what this agent does.
        tools: List of tools the agent can use.
        system_prompt: System prompt content (body of the markdown file).
        skills: List of skill names loaded into the system prompt.
        max_iterations: Maximum tool-call iterations for the execution loop.
            Used by ToolExecutor (LLM path) and as max_turns for the Claude
            SDK path. Defaults to 10. Set higher for research-heavy agents.
    """

    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    skills: List[str] = field(default_factory=list)
    max_iterations: int = 10
    result_validation: str = ""
    # When True, the orchestrator's DelegateTask tool bypasses the agent's
    # own LLM loop and directly invokes its (sole) registered tool. Used
    # for pure-Python trampoline agents like enzyme-variant-normalizer
    # whose only job is to call one tool; the LLM hop adds latency,
    # network fragility, and serialization cost without value.
    deterministic: bool = False
    # When True (and the agent is NOT deterministic), DelegateTask walks
    # task_inputs values for upstream artifact paths, parses them, and
    # mines `images[].image_path` entries to populate Task.image_paths so
    # Agent.run() embeds the actual image bytes as multimodal content.
    # Bridges the gap left when PlanTaskDispatcher (Slice 3 deletion)
    # stopped doing this lookup automatically.
    auto_resolve_artifacts: bool = False

    @property
    def agent_id(self) -> str:
        """Alias for name, for backward compatibility."""
        return self.name


# ======================================================================
# Task — the basic unit of work that an Agent processes
# ======================================================================


class Task(BaseModel):
    """Basic unit of work that an Agent processes.

    Live fields read by Agent.process_task and tools.handlers DelegateTask:
    task_id, description, action, workspace_dir, agent_id, inputs, and the
    image_path / image_paths / images trio.

    extra="allow" preserves any additional kwargs forwarded via
    DispatchRequest.model_dump(), so callers can still spread arbitrary
    fields without raising — see core/orchestrator.py:157.
    """

    model_config = ConfigDict(extra="allow")

    # ---- Identity ---------------------------------------------------
    task_id: str = Field(
        default_factory=lambda: f"task_{uuid4().hex[:8]}",
        description="Unique identifier",
    )
    description: str = Field(
        default="Process the following data",
        description="Human-readable task description",
    )
    action: str = Field(
        default="process",
        description="Action type for the task",
    )

    # ---- Workspace --------------------------------------------------
    workspace_dir: Optional[str] = Field(
        default=None,
        description="Workspace directory for the task",
    )

    # ---- Routing ----------------------------------------------------
    agent_id: Optional[str] = Field(
        default=None,
        description="Target agent for delegation",
    )

    # ---- Structured inputs ------------------------------------------
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured input data",
    )

    # ---- Image support ----------------------------------------------
    image_path: Optional[str] = Field(
        default=None,
        description="Single image path for the task",
    )
    image_paths: Optional[List[str]] = Field(
        default=None,
        description="List of image paths for the task",
    )
    images: Optional[List[str]] = Field(
        default=None,
        description="List of image paths",
    )

    # ---- Helpers ----------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task from a dictionary.

        Args:
            data: Task data dictionary.

        Returns:
            Task instance.
        """
        return cls(**data)


# ======================================================================
# Session Types
# ======================================================================


class SessionType(str, Enum):
    """Top-level session type surfaced to the web UI."""

    CHAT = "chat"
    AGENT = "agent"


class DirectSessionStatus(str, Enum):
    """Lifecycle status for direct chat/agent sessions."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionMessage(BaseModel):
    """Persisted message shown in the workspace message thread."""

    id: str
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionTrace(BaseModel):
    """Persisted execution trace item for direct sessions."""

    id: str
    step_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class DirectSession(BaseModel):
    """Persistent direct session for chat and worker-agent modes."""

    session_id: str
    session_type: SessionType
    title: str
    status: DirectSessionStatus = DirectSessionStatus.DRAFT
    agent_id: str
    messages: List[SessionMessage] = Field(default_factory=list)
    traces: List[SessionTrace] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
