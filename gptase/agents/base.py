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
from collections.abc import AsyncIterator
from contextlib import suppress
import importlib.util
import inspect
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, Union

import yaml

from gptase.agents.runtime import AgentRuntime
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.agents.types import AgentDefinition
from gptase.agents.types import Task
from gptase.models.model import Model
from gptase.tools.base import BaseTool
from gptase.tools.base import get_tool_registry
from gptase.tools.mcp import McpServerConfig
from gptase.utils.config import FrameworkConfig
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
                 memory_manager: Optional[Any] = None,
                 workspace_dir: Optional[str] = None,
                 max_iterations: int = 10):
        """Initialize agent.

        Args:
            system_prompt: System prompt for the agent.
            tools: Optional list of tool names (e.g., Read, Grep, Bash).
            model_config: Optional ModelConfig for LLM execution.
            model_name: Optional model name override for routing.
            agent_id: Optional identifier for this agent instance.
            workspace_dir: Optional workspace directory for file operations.
            max_iterations: Maximum tool-call iterations for the execution
                loop. Used by ToolExecutor (LLM path) and as max_turns for
                the Claude SDK path. Defaults to 10.
        """
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model_config = model_config
        self._model_name = model_name
        self.agent_id = agent_id or ""
        self.description: str = ""
        self.deterministic: bool = False
        self.auto_resolve_artifacts: bool = False
        self.workspace_dir = workspace_dir
        self.max_iterations = max_iterations
        self._memory_manager = memory_manager
        self._owns_memory_manager = False
        self._memory_service = None
        self._memory_service_initialized = False

        self.logger = logging.getLogger(
            f"{__name__}.{self.agent_id}" if self.agent_id else __name__)

    @property
    def _has_mcp_tools(self) -> bool:
        """True if any tool uses the MCP naming convention (server__tool)."""
        return any("__" in t for t in self.tools)

    # ------------------------------------------------------------------
    # Markdown-based construction
    # ------------------------------------------------------------------

    @classmethod
    def from_markdown(
        cls,
        source: Union[str, Path],
        model_manager: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
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

        # Discover and register agent-local tools (sibling tools.py).
        # Triggered for both flat and directory layouts; if no sibling
        # tools.py exists, this is a no-op.
        cls._register_agent_local_tools(md_path, definition.name)

        model_config = None
        if model_manager is not None:
            model_config = model_manager.get_config_for_agent(definition.name)

        agent = cls(
            system_prompt=definition.system_prompt,
            tools=definition.tools,
            model_config=model_config,
            agent_id=definition.name,
            memory_manager=memory_manager,
            max_iterations=definition.max_iterations,
        )
        agent.description = definition.description
        agent.deterministic = definition.deterministic
        agent.auto_resolve_artifacts = definition.auto_resolve_artifacts
        if definition.deterministic and len(definition.tools) != 1:
            raise AgentInitializationError(
                f"Agent '{definition.name}' is marked deterministic but declares "
                f"{len(definition.tools)} tools; expected exactly 1.")
        if definition.deterministic and definition.auto_resolve_artifacts:
            raise AgentInitializationError(
                f"Agent '{definition.name}' has both `deterministic` and "
                f"`auto_resolve_artifacts` set; pick one. Deterministic agents "
                f"already resolve task_inputs paths via _resolve_path_inputs.")
        logger.info("Created agent '%s' with tools: %s", definition.name,
                    definition.tools)
        if definition.skills:
            logger.info("Agent '%s' loaded skills: %s", definition.name,
                        definition.skills)
        return agent

    @staticmethod
    def _register_agent_local_tools(md_path: Path, agent_id: str) -> None:
        """Discover and register tools defined in a sibling tools.py.

        Convention: ``.claude/agents/<agent_id>/tools.py`` may declare any
        number of ``BaseTool`` subclasses. They are auto-registered with
        ``allowed_agents=[<agent_id>]`` so only the owning agent can call
        them.

        Behavior:
            - tools.py absent: silently skip (most agents have no local tools).
            - tools.py import error: raise AgentInitializationError.
            - module exposes no BaseTool subclass: warn and continue.
            - tool name conflicts with an already-registered tool that has
              no permission restriction (i.e. a built-in like Bash/Read):
              raise AgentInitializationError to protect default tools.
        """
        tools_py = md_path.parent / "tools.py"
        if not tools_py.exists():
            return

        module_name = f"_agent_local_tools_{agent_id.replace('-', '_')}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, tools_py)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot build module spec for {tools_py}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:
            raise AgentInitializationError(
                f"Failed to load agent-local tools for '{agent_id}' "
                f"from {tools_py}: {exc}") from exc

        registry = get_tool_registry()
        registered = 0
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BaseTool or not issubclass(obj, BaseTool):
                continue
            # Only register classes defined in this module (skip imports).
            if obj.__module__ != module_name:
                continue
            try:
                instance = obj()
            except Exception as exc:
                raise AgentInitializationError(
                    f"Failed to instantiate tool '{obj.__name__}' "
                    f"for agent '{agent_id}': {exc}") from exc

            tool_name = getattr(instance, "name", None)
            if not tool_name:
                raise AgentInitializationError(
                    f"Tool class '{obj.__name__}' in {tools_py} has no name "
                    "attribute; cannot register.")

            existing = registry.get(tool_name)
            if existing is not None and tool_name not in registry._permissions:
                raise AgentInitializationError(
                    f"Agent-local tool '{tool_name}' for agent '{agent_id}' "
                    f"conflicts with a default tool of the same name. "
                    "Pick a unique name to avoid shadowing built-in tools.")

            registry.register(instance, allowed_agents=[agent_id])
            registered += 1

        if registered == 0:
            logger.warning(
                "Agent-local tools.py at %s defined no BaseTool subclasses",
                tools_py,
            )

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
        deterministic = bool(frontmatter.get("deterministic", False))
        auto_resolve_artifacts = bool(frontmatter.get("auto_resolve_artifacts", False))

        return AgentDefinition(
            name=name,
            description=description,
            tools=tools,
            system_prompt=body_content,
            skills=loaded_skill_names,
            max_iterations=max_iterations,
            deterministic=deterministic,
            auto_resolve_artifacts=auto_resolve_artifacts,
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

    async def run(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        image_paths: Optional[List[str]] = None,
        _resume_snapshot: Optional[Dict[str, Any]] = None,
        _on_turn_complete: Optional[Callable[[Any, Any], Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a task using the appropriate execution engine.

        Args:
            prompt: Task prompt (string) or pre-built message content
                    (list of content dicts for multimodal).
            image_paths: Optional list of image file paths to include
                    in the message. Only used when prompt is a string.
            _resume_snapshot: Internal. Serialized state to restore a
                    previously interrupted tool-calling loop.
            _on_turn_complete: Internal. Callback invoked after each
                    tool-calling iteration with (turn_result, turn_state).

        Returns:
            Dictionary with status and result data.
        """
        original_prompt = prompt

        memory_context = await self._load_memory_context()
        if memory_context:
            from gptase.memory.agent_memory import inject_memory_context
            prompt = inject_memory_context(prompt, memory_context)

        # Build multimodal content if images are provided
        if image_paths and isinstance(prompt, str):
            multimodal: List[Dict[str, Any]] = []
            for image_path in image_paths:
                image_content = self._load_image_as_content(image_path)
                if image_content:
                    multimodal.append(image_content)
            multimodal.append({"type": "text", "text": prompt})
            prompt = multimodal

        if self.is_claude_model():
            result = await self._run_with_sdk(prompt)
        else:
            result = await self._run_with_llm(
                prompt,
                resume_snapshot=_resume_snapshot,
                on_turn_complete=_on_turn_complete,
            )

        await self._update_working_memory(original_prompt, result)
        return result

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

    def _convert_to_claude_content(
            self, content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI multimodal format to Claude API content blocks.

        Args:
            content: List of OpenAI-format content dicts (image_url, text).

        Returns:
            List of Claude-format content blocks.
        """
        claude_content: List[Dict[str, Any]] = []
        for block in content:
            if block.get("type") == "image_url":
                data_url = block.get("image_url", {}).get("url", "")
                # Parse data:image/png;base64,<data>
                if data_url.startswith("data:"):
                    header, b64_data = data_url.split(",", 1)
                    media_type = header.split(":")[1].split(";")[0]
                    claude_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    })
            elif block.get("type") == "text":
                claude_content.append({
                    "type": "text",
                    "text": block.get("text", ""),
                })
        return claude_content

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
        except ImportError:
            raise ImportError("Claude Agent SDK not installed. "
                              "Install with: pip install claude-agent-sdk") from None

        has_images = (isinstance(task, list)
                      and any(c.get("type") == "image_url" for c in task))

        if isinstance(task, list) and has_images:
            claude_content = self._convert_to_claude_content(task)

            async def _multimodal_prompt() -> AsyncIterator[Dict[str, Any]]:
                yield {
                    "type": "user",
                    "session_id": "",
                    "message": {
                        "role": "user",
                        "content": claude_content,
                    },
                    "parent_tool_use_id": None,
                }

            sdk_prompt: Union[str, AsyncIterator[Dict[str, Any]]] = _multimodal_prompt()
        elif isinstance(task, list):
            text_parts = [c.get("text", "") for c in task if c.get("type") == "text"]
            sdk_prompt = " ".join(text_parts) or "Analyze the provided content"
        else:
            sdk_prompt = task

        mcp_servers = FrameworkConfig().mcp_servers if self._has_mcp_tools else {}

        options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            allowed_tools=self.tools if self.tools else [],
            max_turns=self.max_iterations,
            mcp_servers=mcp_servers,
        )

        result_content = None
        sdk_start = time.monotonic()
        async for message in query(prompt=sdk_prompt, options=options):
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
                "runtime": {
                    "stop_reason": "sdk_completed",
                    "turn_count": None,
                    "turns": [],
                    "resume_supported": False,
                },
                "total_duration_ms":
                sdk_ms,
            },
        }

    async def _run_with_llm(
        self,
        task: Union[str, List[Dict[str, Any]]],
        resume_snapshot: Optional[Dict[str, Any]] = None,
        on_turn_complete: Optional[Callable[[Any, Any], Any]] = None,
    ) -> Dict[str, Any]:
        """Execute via custom LLM loop with tool support.

        This path is used for non-Claude models (OpenAI, DeepSeek, etc.).

        Args:
            task: Task description or multimodal content list.

        Returns:
            Result dictionary.
        """
        model = Model(default_config=self.model_config, enable_tracking=True)
        await model.initialize_tracking()

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

        framework_config = FrameworkConfig()
        mcp_server_configs = ({
            name: McpServerConfig(**cfg)
            for name, cfg in framework_config.mcp_servers.items()
        } if self._has_mcp_tools else {})

        runtime = AgentRuntime(
            model=model,
            agent_id=self.agent_id,
            max_turns=self.max_iterations,
            mcp_server_configs=mcp_server_configs,
        )

        try:
            runtime_result = await runtime.run(
                messages=messages,
                allowed_tools=self.tools,
                max_turns=self.max_iterations,
                resume_snapshot=resume_snapshot,
                on_turn_complete=on_turn_complete,
            )
            trace = {
                "steps": runtime_result.snapshot.steps,
                "total_input_tokens": runtime_result.snapshot.total_input_tokens,
                "total_output_tokens": runtime_result.snapshot.total_output_tokens,
                "total_duration_ms": runtime_result.snapshot.total_duration_ms,
                "runtime": {
                    "stop_reason":
                    getattr(runtime_result.stop_reason, "value",
                            runtime_result.stop_reason),
                    "turn_count":
                    runtime_result.turn_count,
                    "turns": [
                        turn.model_dump(mode="json")
                        for turn in runtime_result.snapshot.turns
                    ],
                    "resume_supported":
                    True,
                    "coordinator": (runtime_result.coordinator_summary.model_dump(
                        mode="json") if runtime_result.coordinator_summary else None),
                },
            }
            data = {
                "content": runtime_result.content,
                "reasoning": runtime_result.reasoning,
                "usage": runtime_result.usage,
                "iterations": runtime_result.turn_count,
            }

            if runtime_result.stop_reason == RuntimeStopReason.FINAL_ANSWER:
                return {
                    "status": "success",
                    "data": data,
                    "trace": trace,
                }

            error = runtime_result.error or (
                "Maximum tool iterations reached"
                if runtime_result.stop_reason == RuntimeStopReason.MAX_TURNS else
                "Interactive runtime stopped before producing a final answer")
            return {
                "status": "error",
                "error": error,
                "data": data,
                "trace": trace,
            }
        finally:
            await model.shutdown()

    async def run_stream(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ):
        """Stream plain-text responses for simple chat-style interactions.

        This method attempts native token streaming when the underlying
        execution path supports it. For Claude SDK agents and tool-equipped
        agents, it falls back to ``run()`` and emits a single final chunk so
        websocket consumers can still use a uniform interface.

        Args:
            prompt: User message string to stream a response for.
            session_id: Optional session ID for tracking.
            step_id: Optional step ID for conversation linkage.

        Yields:
            Dict with keys ``content``, ``reasoning_content``,
            ``is_complete``, and ``metadata`` for each streaming chunk.

        Raises:
            ValueError: If *prompt* is not a string.
        """
        if not isinstance(prompt, str):
            raise ValueError("run_stream only supports string content")

        original_prompt = prompt
        memory_context = await self._load_memory_context()
        if memory_context:
            from gptase.memory.agent_memory import inject_memory_context
            prompt = inject_memory_context(prompt, memory_context)

        # Claude SDK path and tool-enabled agents currently use a non-streaming
        # fallback so websocket clients still receive a final event.
        if self.is_claude_model() or self.tools:
            # Hand the original task back to run() so memory is injected once.
            result = await self.run(original_prompt)
            final_content = result.get("data", {}).get(
                "content", "") if result.get("status") == "success" else result.get(
                    "error", "")
            yield {
                "content": final_content,
                "reasoning_content": None,
                "is_complete": True,
                "error": None if result.get("status") == "success" else final_content,
                "metadata": {
                    "session_id": session_id,
                    "step_id": step_id,
                    "stream_mode": "fallback",
                },
            }
            return

        model = Model(default_config=self.model_config, enable_tracking=True)
        await model.initialize_tracking()
        chunks: List[str] = []
        try:
            messages: List[Dict[str, Any]] = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ]
            async for chunk in model.generate_stream(messages,
                                                     agent_id=self.agent_id,
                                                     agent_name=self.agent_id or None):
                if chunk.content:
                    chunks.append(chunk.content)
                yield {
                    "content": chunk.content,
                    "reasoning_content": chunk.reasoning_content,
                    "is_complete": chunk.is_complete,
                    "metadata": chunk.metadata,
                }

            final_content = "".join(chunks)
            await self._update_working_memory(
                original_prompt,
                {
                    "status": "success",
                    "data": {
                        "content": final_content
                    }
                },
            )
        finally:
            with suppress(Exception):
                await model.shutdown()

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a structured task with optional image support.

        Extracts image paths, builds a formatted user prompt, and routes
        to run() with appropriate parameters.

        Args:
            task: Task instance with description and optional image fields.

        Returns:
            Task result dictionary.
        """
        try:
            image_paths = self._extract_image_paths(task)
            prompt = self._build_user_prompt(task, include_images=False)
            self.logger.info(
                "Processing task for agent '%s' | task_id=%s | prompt_chars=%d | image_count=%d",
                self.agent_id,
                task.task_id,
                len(prompt),
                len(image_paths),
            )
            return await self.run(
                prompt,
                image_paths=image_paths or None,
            )
        except Exception as e:
            self.logger.error("Task processing failed for %s: %s", self.agent_id, e)
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id,
            }

    def _extract_image_paths(self, task: Task) -> List[str]:
        """Extract and deduplicate image paths from a task.

        Checks 'image_path', 'image_paths', and 'images' fields.
        Handles workspace_dir prefix for relative paths.

        Args:
            task: Task instance potentially containing image references.

        Returns:
            Deduplicated list of image file paths.
        """
        workspace_dir = task.workspace_dir or self.workspace_dir or ""
        if workspace_dir:
            workspace_path = Path(workspace_dir)
            if workspace_path.is_file():
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
        task: Task,
        include_images: bool = True,
    ) -> str:
        """Build a formatted user prompt from a task.

        Args:
            task: Task instance with description and optional data fields.
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

    async def close(self) -> None:
        """Release agent-owned resources."""
        self._memory_service = None
        self._memory_service_initialized = False
        if self._memory_manager is not None and self._owns_memory_manager:
            await self._memory_manager.close()
            self._memory_manager = None

    async def _load_memory_context(self) -> str:
        service = await self._get_agent_memory_service()
        if service is None:
            return ""
        return await service.build_memory_context(self.agent_id)

    async def _update_working_memory(
        self,
        original_prompt: Union[str, List[Dict[str, Any]]],
        result: Dict[str, Any],
    ) -> None:
        service = await self._get_agent_memory_service()
        if service is None:
            return
        await service.update_memory(self.agent_id, original_prompt, result)

    async def _get_agent_memory_service(self):
        if not self.agent_id:
            return None

        if self._memory_service_initialized:
            return self._memory_service

        from gptase.memory.agent_memory import AgentMemoryService
        from gptase.memory.manager import MemoryManager
        from gptase.utils.config import FrameworkConfig

        self._memory_service_initialized = True
        framework_config = FrameworkConfig()
        if not framework_config.memory.enabled:
            return None

        if self._memory_manager is None:
            self._memory_manager = MemoryManager(config=framework_config.memory)
            self._owns_memory_manager = True
            await self._memory_manager.initialize()

        self._memory_service = AgentMemoryService(self._memory_manager,
                                                  framework_config.memory)
        return self._memory_service


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
