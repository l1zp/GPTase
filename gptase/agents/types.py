"""Type definitions for the Agent module."""

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


@dataclass
class AgentDefinition:
    """Parsed agent definition from markdown with YAML frontmatter.

    Attributes:
        name: Unique identifier for the agent.
        description: Human-readable description of what the agent does.
        tools: List of tools the agent can use.
        system_prompt: System prompt content (body of the markdown file).
    """

    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""

    @property
    def agent_id(self) -> str:
        """Alias for name, for backward compatibility."""
        return self.name


class AgentState(BaseModel):
    """Agent state for persistence.

    Attributes:
        agent_id: Unique identifier for the agent.
        status: Current agent status (one of STATUS_* constants).
        current_task: Description of the current task being processed.
    """

    agent_id: str
    status: str = 'idle'
    current_task: Optional[str] = None


class AgentTask(BaseModel):
    """Task specification for Agent execution.

    This class provides a type-safe interface for agent task inputs,
    with support for multimodal content (images) and arbitrary metadata.

    Attributes:
        description: Human-readable task description.
        base_dir: Base directory for resolving relative image paths.
        image_path: Single image path for the task.
        image_paths: List of image paths for the task.
        images: List of image paths.
    """

    model_config = ConfigDict(extra="allow")  # Allow additional fields

    description: str = Field(
        default="Process the following data",
        description="Human-readable task description",
    )
    base_dir: Optional[str] = Field(
        default=None,
        description="Base directory for resolving relative image paths",
    )
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        """Create AgentTask from a dictionary.

        Args:
            data: Task data dictionary.

        Returns:
            AgentTask instance.
        """
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values.

        Returns:
            Dictionary representation of the task.
        """
        return self.model_dump(exclude_none=True)

    def get_extra_fields(self) -> Dict[str, Any]:
        """Get all extra fields not defined in the model.

        Returns:
            Dictionary of extra fields.
        """
        defined_fields = set(self.model_fields.keys())
        return {k: v for k, v in self.model_dump().items() if k not in defined_fields}
