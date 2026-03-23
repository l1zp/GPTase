"""Unified Agent interface with dual execution paths.

This module provides a single Agent class that automatically routes to
Claude Agent SDK or a custom LLM loop based on the configured model.

Usage:
    # From markdown definition:
    agent = Agent.from_markdown("path/to/agent.md")
    result = await agent.run("Analyze this code")

    # Direct construction:
    agent = Agent(
        system_prompt="You are a helpful assistant.",
        tools=["Read", "Grep", "Bash"],
    )

    # Multimodal usage:
    result = await agent.run(
        task="Analyze this figure",
        image_paths=["path/to/image.png"],
    )
"""

import base64
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Union

import yaml

from gptase.agents.types import AgentDefinition
from gptase.agents.types import AgentMode
from gptase.agents.types import AgentState
from gptase.agents.types import AgentTask
from gptase.utils.exceptions import AgentInitializationError

logger = logging.getLogger(__name__)

# Claude model prefixes for SDK routing
_CLAUDE_MODEL_PREFIXES = ("claude-", )

# Pattern for YAML frontmatter in markdown agent definitions
_FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

# Base directory for Claude-related config files
_CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent / ".claude"

# Default directories for agent and skill definitions
_DEFAULT_CONFIG_DIR = _CLAUDE_DIR / "agents"
_DEFAULT_SKILLS_DIR = _CLAUDE_DIR / "skills"


def _normalize_to_list(value: Union[str, List[str]]) -> List[str]:
    """Normalize a comma-separated string or list to a list of stripped strings.

    Args:
        value: Either a comma-separated string or a list of strings.

    Returns:
        List of stripped, non-empty strings.
    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value or []


class Agent:
    """Unified agent that routes to Claude SDK or custom LLM loop.

    When the configured model is a Claude model, execution is delegated
    to claude_agent_sdk query which provides built-in tools (bash,
    text_editor) and manages the agent loop.

    For non-Claude models, a simple LLM loop using Model.generate()
    is used instead.

    Attributes:
        system_prompt: System prompt for the agent.
        tools: List of tool names the agent can use (e.g., Read, Grep, Bash).
        model_config: Optional ModelConfig for non-Claude execution.
        model_name: Model name for routing (default from FrameworkConfig).
    """

    def __init__(self,
                 system_prompt: str,
                 tools: Optional[List[str]] = None,
                 model_config: Optional[Any] = None,
                 model_name: Optional[str] = None,
                 agent_id: Optional[str] = None,
                 workspace_dir: Optional[str] = None,
                 mode: AgentMode = AgentMode.DIRECT,
                 max_iterations: int = 10):
        """Initialize agent.

        Args:
            system_prompt: System prompt for the agent.
            tools: Optional list of tool names (e.g., Read, Grep, Bash).
            model_config: Optional ModelConfig for LLM execution.
            model_name: Optional model name override for routing.
            agent_id: Optional identifier for this agent instance.
            workspace_dir: Optional workspace directory for file operations.
            mode: Default execution mode (DIRECT or PLAN).
            max_iterations: Maximum tool-call iterations for the execution
                loop. Used by ToolExecutor (LLM path) and as max_turns for
                the Claude SDK path. Defaults to 10.
        """
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model_config = model_config
        self._model_name = model_name
        self.agent_id = agent_id or ""
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.max_iterations = max_iterations
        self._planner = None

        self.logger = logging.getLogger(
            f"{__name__}.{self.agent_id}" if self.agent_id else __name__)

    # ------------------------------------------------------------------
    # Markdown-based construction
    # ------------------------------------------------------------------

    @classmethod
    def from_markdown(
        cls,
        source: Union[str, Path],
        model_manager: Optional[Any] = None,
        config_dir: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ) -> "Agent":
        """Create an Agent from a markdown definition.

        Args:
            source: Either a path to a .md file, or an agent name
                (which will be looked up in *config_dir*).
            model_manager: Optional Model instance for LLM configuration.
            config_dir: Directory to search for agent .md files when
                *source* is a name. Defaults to ``.claude/agents/``.
            skills_dir: Directory to search for skill definitions.
                Defaults to ``.claude/skills/``.

        Returns:
            A fully initialised Agent instance.

        Raises:
            AgentInitializationError: If the definition cannot be found
                or parsed.
        """
        path = Path(source)

        # If source is a direct file path
        if path.suffix == ".md" and path.exists():
            md_path = path
        else:
            # Treat source as an agent name – look up in config_dir
            search_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
            md_path = cls._find_agent_file(str(source), search_dir)
            if md_path is None:
                raise AgentInitializationError(
                    f"Agent '{source}' not found in {search_dir}")

        try:
            definition = cls._parse_markdown(md_path.read_text(),
                                             md_path.stem,
                                             skills_dir=skills_dir)
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to parse agent definition '{source}': {e}") from e

        model_config = None
        if model_manager is not None:
            model_config = model_manager.get_config_for_agent(definition.name)

        agent = cls(
            system_prompt=definition.system_prompt,
            tools=definition.tools,
            model_config=model_config,
            agent_id=definition.name,
            max_iterations=definition.max_iterations,
        )
        logger.info("Created agent '%s' with tools: %s", definition.name,
                    definition.tools)
        if definition.skills:
            logger.info("Agent '%s' loaded skills: %s", definition.name,
                        definition.skills)
        return agent

    @staticmethod
    def _parse_markdown(content: str,
                        default_name: str,
                        skills_dir: Optional[Path] = None) -> AgentDefinition:
        """Parse markdown content with YAML frontmatter into AgentDefinition.

        Args:
            content: Markdown content with YAML frontmatter.
            default_name: Fallback agent name if not in frontmatter.
            skills_dir: Optional directory to search for skill definitions.

        Returns:
            AgentDefinition instance.

        Raises:
            ValueError: If content is invalid.
        """
        frontmatter_match = _FRONTMATTER_PATTERN.match(content)
        if not frontmatter_match:
            raise ValueError("Invalid agent format: missing YAML frontmatter. "
                             "Expected '---\\nname: ...\\n---'")

        frontmatter_text = frontmatter_match.group(1)
        body_content = content[frontmatter_match.end():].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}") from e

        if not isinstance(frontmatter, dict):
            raise ValueError("YAML frontmatter must be a dictionary")

        name = frontmatter.get("name", default_name)
        description = frontmatter.get("description", "")
        tools = _normalize_to_list(frontmatter.get("tools", []))
        skills_raw = _normalize_to_list(frontmatter.get("skills", []))

        resolved_skills_dir = skills_dir or _DEFAULT_SKILLS_DIR
        skill_sections: List[str] = []
        loaded_skill_names: List[str] = []

        for skill_name in skills_raw:
            skill_content = Agent._load_skill_content(skill_name, resolved_skills_dir)
            if skill_content:
                skill_sections.append(skill_content)
                loaded_skill_names.append(skill_name)

        if skill_sections:
            body_content = body_content + "\n\n" + "\n\n".join(skill_sections)

        max_iterations = int(frontmatter.get("max_iterations", 10))

        return AgentDefinition(
            name=name,
            description=description,
            tools=tools,
            system_prompt=body_content,
            skills=loaded_skill_names,
            max_iterations=max_iterations,
        )

    @staticmethod
    def _find_agent_file(name: str, config_dir: Path) -> Optional[Path]:
        """Find an agent markdown file by name.

        Supports both hyphenated and underscore name formats, and two
        layout styles:

            config_dir/{name}.md             flat file (existing)
            config_dir/{name}/{name}.md      directory-based (new)

        Flat layout takes precedence over directory layout.

        Args:
            name: Agent name (with hyphens or underscores).
            config_dir: Directory to search in.

        Returns:
            Path to agent file, or None if not found.
        """
        for n in (name, name.replace("_", "-"), name.replace("-", "_")):
            # Flat layout: agents/abc.md
            md_file = config_dir / f"{n}.md"
            if md_file.exists():
                return md_file
            # Directory layout: agents/abc/abc.md
            dir_file = config_dir / n / f"{n}.md"
            if dir_file.exists():
                return dir_file
        return None

    @staticmethod
    def _load_skill_content(skill_name: str, skills_dir: Path) -> Optional[str]:
        """Load skill content from a SKILL.md file.

        Reads the skill's markdown file and strips its frontmatter.

        Args:
            skill_name: Name of the skill (directory name under skills_dir).
            skills_dir: Directory containing skill subdirectories.

        Returns:
            Skill body content (without frontmatter), or None if not found.
        """
        skill_file = skills_dir / skill_name / "SKILL.md"
        try:
            raw = skill_file.read_text()
            fm_match = _FRONTMATTER_PATTERN.match(raw)
            return raw[fm_match.end():].strip() if fm_match else raw.strip()
        except OSError as exc:
            logger.warning("Skill '%s' not loaded: %s; skipping.", skill_name, exc)
            return None

    @property
    def model_name(self) -> str:
        """Get the effective model name for routing."""
        if self._model_name:
            return self._model_name
        if self.model_config and hasattr(self.model_config, "model_name"):
            return self.model_config.model_name
        raise ValueError(
            "model_name or model_config must be provided when creating Agent. "
            "Use Agent.from_markdown(..., model_manager=model) or pass "
            "model_name/model_config to Agent.__init__.")

    def is_claude_model(self) -> bool:
        """Check if the configured model is a Claude model."""
        name = self.model_name.lower()
        return any(name.startswith(prefix) for prefix in _CLAUDE_MODEL_PREFIXES)

    @property
    def planner(self):
        """Get or create the PlanManager for this agent."""
        if self._planner is None:
            from gptase.agents.planner import PlanManager
            self._planner = PlanManager(self)
        return self._planner

    async def run(
        self,
        content: Union[str, List[Dict[str, Any]]],
        image_paths: Optional[List[str]] = None,
        mode: Optional[AgentMode] = None,
    ) -> Dict[str, Any]:
        """Execute a task using the appropriate execution engine.

        Args:
            content: Task description (string) or pre-built message content
                     (list of content dicts for multimodal).
            image_paths: Optional list of image file paths to include
                     in the message. Only used when content is a string.
            mode: Optional mode override. If None, uses self.mode.

        Returns:
            Dictionary with status and result data.
        """
        effective_mode = mode or self.mode

        # Plan mode: decompose into tasks, then execute
        if effective_mode == AgentMode.PLAN and isinstance(content, str):
            return await self._run_with_plan(content)

        # Build multimodal content if images are provided
        if image_paths and isinstance(content, str):
            multimodal: List[Dict[str, Any]] = []
            for image_path in image_paths:
                image_content = self._load_image_as_content(image_path)
                if image_content:
                    multimodal.append(image_content)
            multimodal.append({"type": "text", "text": content})
            content = multimodal

        has_images = isinstance(content, list) and any(
            c.get("type") == "image_url" for c in content
        )
        if self.is_claude_model() and not has_images:
            return await self._run_with_sdk(content)
        else:
            return await self._run_with_llm(content)

    async def _run_with_plan(
        self,
        goal: str,
    ) -> Dict[str, Any]:
        """Execute via plan mode: decompose into tasks, then execute.

        Creates a plan by calling the LLM, then executes each task
        in dependency order.

        Args:
            goal: The user's goal to plan and execute.

        Returns:
            Result dictionary with plan execution results.
        """
        try:
            plan = await self.planner.create_plan(goal=goal)
            result = await self.planner.execute_plan(plan)
            return result
        except Exception as e:
            self.logger.error("Plan mode execution failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
            }

    def _load_image_as_content(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Load an image file and return as multimodal content dict.

        Args:
            image_path: Path to image file.

        Returns:
            Dict with image_url content, or None if loading fails.
        """
        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning(f"Image file not found: {image_path}")
                return None

            # Read and encode image
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Detect MIME type from extension
            suffix = path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_types.get(suffix, "image/jpeg")

            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}"
                }
            }
        except Exception as e:
            logger.warning(f"Failed to load image {image_path}: {e}")
            return None

    async def _run_with_sdk(
        self,
        task: Union[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Execute via Claude Agent SDK.

        The SDK provides built-in bash and text_editor tools.
        Tools are passed to ClaudeAgentOptions for execution.

        Args:
            task: Task description or multimodal content.

        Returns:
            Result dictionary.
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions
            from claude_agent_sdk import query
            from gptase.utils.config import FrameworkConfig

            # SDK currently only supports string tasks
            if isinstance(task, list):
                # Extract text from multimodal content for SDK
                text_parts = [
                    c.get("text", "") for c in task if c.get("type") == "text"
                ]
                task_str = " ".join(text_parts) or "Analyze the provided images"
            else:
                task_str = task

            mcp_servers = (
                FrameworkConfig().mcp_servers
                if any("__" in t for t in self.tools)
                else {}
            )

            options = ClaudeAgentOptions(
                system_prompt=self.system_prompt,
                allowed_tools=self.tools if self.tools else [],
                max_turns=self.max_iterations,
                mcp_servers=mcp_servers,
            )

            # Use query() for SDK execution
            result_content = None
            sdk_start = time.monotonic()
            async for message in query(prompt=task_str, options=options):
                if hasattr(message, "result"):
                    result_content = message.result
            sdk_ms = int((time.monotonic() - sdk_start) * 1000)

            return {
                "status": "success",
                "data": {
                    "content": result_content
                },
                "trace": {
                    "steps": [{
                        "type": "sdk_run",
                        "note": "SDK execution; per-step data not available",
                        "duration_ms": sdk_ms,
                    }],
                    "total_duration_ms": sdk_ms,
                },
            }

        except ImportError:
            raise ImportError("Claude Agent SDK not installed. "
                              "Install with: pip install claude-agent-sdk") from None
        except Exception as e:
            logger.error(f"SDK execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def _run_with_llm(
        self,
        task: Union[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Execute via custom LLM loop with tool support.

        This path is used for non-Claude models (OpenAI, DeepSeek, etc.).

        Args:
            task: Task description or multimodal content list.

        Returns:
            Result dictionary.
        """
        try:
            from gptase.models.model import Model
            from gptase.tools.executor import ToolExecutor
            from gptase.tools.mcp import McpServerConfig
            from gptase.utils.config import FrameworkConfig

            model = Model(default_config=self.model_config)

            # Build initial messages
            user_content = task if isinstance(task, list) else task
            messages: List[Dict[str, Any]] = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_content
                },
            ]

            # Load MCP server configs from FrameworkConfig
            framework_config = FrameworkConfig()
            # Only initialize MCP for agents that explicitly expose MCP tools.
            mcp_server_configs = {}
            if any("__" in tool_name for tool_name in self.tools):
                mcp_server_configs = {
                    name: McpServerConfig(**cfg)
                    for name, cfg in framework_config.mcp_servers.items()
                }

            executor = ToolExecutor(
                model=model,
                agent_id=self.agent_id,
                max_iterations=self.max_iterations,
                mcp_server_configs=mcp_server_configs,
            )

            return await executor.execute(messages, self.tools)

        except Exception as e:
            logger.error("LLM execution failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
            }

    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """Process a structured task with optional image support.

        Extracts image paths, builds a formatted user prompt, and routes
        to run() with appropriate parameters.

        Args:
            task: AgentTask instance with description and optional image fields.

        Returns:
            Task result dictionary.
        """
        return await self.process_task_with_mode(task)

    async def process_task_with_mode(
        self,
        task: AgentTask,
        mode: Optional[AgentMode] = None,
    ) -> Dict[str, Any]:
        """Process a structured task while allowing an explicit mode override."""
        try:
            image_paths = self._extract_image_paths(task)
            prompt = self._build_user_prompt(task, include_images=False)
            return await self.run(prompt, image_paths=image_paths or None, mode=mode)
        except Exception as e:
            self.logger.error("Task processing failed for %s: %s", self.agent_id, e)
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id,
            }

    def _extract_image_paths(self, task: AgentTask) -> List[str]:
        """Extract and deduplicate image paths from a task.

        Checks 'image_path', 'image_paths', and 'images' fields.
        Handles workspace_dir prefix for relative paths.

        Args:
            task: AgentTask instance potentially containing image references.

        Returns:
            Deduplicated list of image file paths.
        """
        workspace_dir = task.workspace_dir or self.workspace_dir or ""
        if workspace_dir:
            workspace_path = Path(workspace_dir)
            if workspace_path.suffix:
                workspace_dir = str(workspace_path.parent)
        paths: List[str] = []

        if task.image_path:
            paths.append(task.image_path)
        if task.image_paths:
            paths.extend(task.image_paths)
        if task.images:
            for img_path in task.images:
                if workspace_dir and not os.path.isabs(img_path):
                    img_path = os.path.join(workspace_dir, img_path)
                paths.append(img_path)

        seen: set = set()
        return [p for p in paths
                if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]

    def _build_user_prompt(
        self,
        task: AgentTask,
        include_images: bool = True,
    ) -> str:
        """Build a formatted user prompt from a task.

        Args:
            task: AgentTask instance with description and optional data fields.
            include_images: Whether to append image paths to the prompt.

        Returns:
            Formatted prompt string.
        """
        # Get all task data, excluding image-related fields for the data section
        task_dict = task.model_dump()
        task_copy = {
            k: v
            for k, v in task_dict.items()
            if k not in ("image_path", "image_paths", "images")
        }
        task_text = json.dumps(task_copy, indent=2, ensure_ascii=False)
        prompt = (f"Task: {task.description}\n\n"
                  f"Input Data:\n{task_text}\n")
        if include_images:
            image_paths = self._extract_image_paths(task)
            if image_paths:
                prompt += f"\nImages: {', '.join(image_paths)}\n"

        # Treat the task workspace or agent's explicit workspace_dir as the workspace
        workspace_dir = task.workspace_dir or self.workspace_dir

        if workspace_dir:
            prompt += (
                f"\nNote: Your workspace directory is located at `{workspace_dir}`. "
                "Please use this directory for reading from and writing to any intermediate or output files.\n"
            )

        # Update the agent's workspace_dir attribute so tools or other methods can access it during the run
        if not self.workspace_dir and workspace_dir:
            self.workspace_dir = workspace_dir

        prompt += "\nProcess this task according to your instructions.\n"
        return prompt

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"{self.__class__.__name__}(id={self.agent_id})"


def list_agent_md_files(agents_dir: Path) -> List[Path]:
    """Discover agent markdown files from flat and directory layouts.

    Supports two layouts:
        agents_dir/{name}.md             flat file
        agents_dir/{name}/{name}.md      directory-based

    Args:
        agents_dir: Directory containing agent definitions.

    Returns:
        List of Path objects pointing to agent .md files.
    """
    md_files = list(agents_dir.glob("*.md"))
    for subdir in agents_dir.iterdir():
        if subdir.is_dir():
            nested = subdir / f"{subdir.name}.md"
            if nested.exists():
                md_files.append(nested)
    return md_files
