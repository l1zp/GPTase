"""Unified Agent interface with dual execution paths.

This module provides a single Agent class that automatically routes to
Claude Agent SDK or a custom LLM loop based on the configured model.

Usage:
    agent = Agent(
        system_prompt="You are a helpful assistant.",
        tools=["Read", "Grep", "Bash"],
    )
    result = await agent.run("Analyze this code")

    # Multimodal usage:
    result = await agent.run_with_images(
        task="Analyze this figure",
        image_paths=["path/to/image.png"],
    )
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from gptase.utils.constants import STATUS_ERROR
from gptase.utils.constants import STATUS_IDLE
from gptase.utils.constants import STATUS_SUCCESS

logger = logging.getLogger(__name__)

# Claude model prefixes for SDK routing
_CLAUDE_MODEL_PREFIXES = ("claude-", )


class AgentState(BaseModel):
    """Agent state for persistence.

    Attributes:
        agent_id: Unique identifier for the agent.
        status: Current agent status (one of STATUS_* constants).
        current_task: Description of the current task being processed.
    """

    agent_id: str
    status: str = STATUS_IDLE
    current_task: Optional[str] = None


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
                 workspace_dir: Optional[str] = None):
        """Initialize agent.

        Args:
            system_prompt: System prompt for the agent.
            tools: Optional list of tool names (e.g., Read, Grep, Bash).
            model_config: Optional ModelConfig for LLM execution.
            model_name: Optional model name override for routing.
            agent_id: Optional identifier for this agent instance.
        """
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model_config = model_config
        self._model_name = model_name
        self.agent_id = agent_id or ""
        self.workspace_dir = workspace_dir
        self.status = STATUS_IDLE
        self.current_task: Optional[str] = None
        self.logger = logging.getLogger(
            f"{__name__}.{self.agent_id}" if self.agent_id else __name__)

    @property
    def model_name(self) -> str:
        """Get the effective model name for routing."""
        if self._model_name:
            return self._model_name
        if self.model_config and hasattr(self.model_config, "model_name"):
            return self.model_config.model_name
        # Fall back to FrameworkConfig
        try:
            from gptase.utils.config import FrameworkConfig
            config = FrameworkConfig()
            return config.llm_model
        except Exception:
            return "unknown"

    def is_claude_model(self) -> bool:
        """Check if the configured model is a Claude model."""
        name = self.model_name.lower()
        return any(name.startswith(prefix) for prefix in _CLAUDE_MODEL_PREFIXES)

    async def run(self, task: Union[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Execute a task using the appropriate execution engine.

        Args:
            task: Task description (string) or pre-built message content
                  (list of content dicts for multimodal).

        Returns:
            Dictionary with status and result data.
        """
        if self.is_claude_model():
            return await self._run_with_sdk(task)
        else:
            return await self._run_with_llm(task)

    async def run_with_images(
        self,
        task: str,
        image_paths: List[str],
    ) -> Dict[str, Any]:
        """Execute a task with images using multimodal messages.

        Args:
            task: Task description / user prompt.
            image_paths: List of paths to image files.

        Returns:
            Dictionary with status and result data.
        """
        # Build multimodal content
        content = []

        # Add images first
        for image_path in image_paths:
            image_content = self._load_image_as_content(image_path)
            if image_content:
                content.append(image_content)

        # Add text prompt
        content.append({
            "type": "text",
            "text": task,
        })

        # Run with multimodal message
        return await self.run(content)

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

            # SDK currently only supports string tasks
            if isinstance(task, list):
                # Extract text from multimodal content for SDK
                text_parts = [
                    c.get("text", "") for c in task if c.get("type") == "text"
                ]
                task_str = " ".join(text_parts) or "Analyze the provided images"
            else:
                task_str = task

            options = ClaudeAgentOptions(
                system_prompt=self.system_prompt,
                allowed_tools=self.tools if self.tools else [],
            )

            # Use query() for SDK execution
            result_content = None
            async for message in query(prompt=task_str, options=options):
                if hasattr(message, "result"):
                    result_content = message.result

            return {
                "status": "success",
                "data": {
                    "content": result_content
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
        """Execute via custom LLM loop using Model.generate().

        This path is used for non-Claude models (OpenAI, DeepSeek, etc.).

        Args:
            task: Task description or multimodal content list.

        Returns:
            Result dictionary.
        """
        try:
            from gptase.models.model import Model

            model = Model(default_config=self.model_config)

            # Build user content
            if isinstance(task, str):
                user_content = task
            else:
                # Multimodal content - use as-is
                user_content = task

            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_content
                },
            ]

            response = await model.generate(messages, config=self.model_config)

            return {
                "status": "success",
                "data": {
                    "content": response.content,
                    "reasoning": response.reasoning_content,
                    "usage": response.usage,
                },
            }

        except Exception as e:
            logger.error(f"LLM execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def update_status(self,
                            status: str,
                            current_task: Optional[str] = None) -> None:
        """Update agent status.

        Args:
            status: New status value (should be one of STATUS_* constants).
            current_task: Optional description of current task.
        """
        self.status = status
        if current_task is not None:
            self.current_task = current_task
        self.logger.debug("Status updated to: %s", status)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a structured task dict with optional image support.

        Extracts image paths, builds a formatted user prompt, and routes
        to run() or run_with_images() as appropriate.

        Args:
            task: Task dict with 'description' and optional image keys.

        Returns:
            Task result dictionary.
        """
        await self.update_status(STATUS_SUCCESS)
        try:
            image_paths = self._extract_image_paths(task)
            if image_paths:
                prompt = self._build_user_prompt(task, include_images=False)
                return await self.run_with_images(prompt, image_paths)
            return await self.run(self._build_user_prompt(task))
        except Exception as e:
            self.logger.error("Task processing failed for %s: %s", self.agent_id, e)
            return {
                "status": STATUS_ERROR,
                "error": str(e),
                "agent_id": self.agent_id,
            }

    def _extract_image_paths(self, task: Dict[str, Any]) -> List[str]:
        """Extract and deduplicate image paths from a task dict.

        Checks 'image_path', 'image_paths', and 'images' keys.
        Handles base_dir prefix for relative paths.

        Args:
            task: Task dict potentially containing image references.

        Returns:
            Deduplicated list of image file paths.
        """
        base_dir = task.get("base_dir", "")
        paths = []

        if task.get("image_path"):
            paths.append(task["image_path"])
        if task.get("image_paths"):
            paths.extend(task["image_paths"])
        if task.get("images"):
            for img in task["images"]:
                if isinstance(img, str):
                    paths.append(img)
                elif isinstance(img, dict):
                    # Support both 'path' and 'image_path' keys
                    img_path = img.get("path") or img.get("image_path")
                    if img_path:
                        # Prepend base_dir if path is relative
                        if base_dir and not os.path.isabs(img_path):
                            img_path = os.path.join(base_dir, img_path)
                        paths.append(img_path)

        seen: set = set()
        return [p for p in paths
                if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]

    def _build_user_prompt(self,
                           task: Dict[str, Any],
                           include_images: bool = True) -> str:
        """Build a formatted user prompt from a task dict.

        Args:
            task: Task dict with 'description' and optional data fields.
            include_images: Whether to append image paths to the prompt.

        Returns:
            Formatted prompt string.
        """
        task_copy = {
            k: v
            for k, v in task.items() if k not in ("image_path", "image_paths", "images")
        }
        task_text = json.dumps(task_copy, indent=2, ensure_ascii=False)
        prompt = (f"Task: {task.get('description', 'Process the following data')}\n\n"
                  f"Input Data:\n{task_text}\n")
        if include_images:
            image_paths = self._extract_image_paths(task)
            if image_paths:
                prompt += f"\nImages: {', '.join(image_paths)}\n"

        if self.workspace_dir:
            prompt += f"\nNote: Your workspace directory is located at `{self.workspace_dir}`. Please use this directory for reading from and writing to any intermediate or output files.\n"

        prompt += "\nProcess this task according to your instructions.\n"
        return prompt

    async def shutdown(self) -> None:
        """Clean up resources. Sets status to idle."""
        self.status = STATUS_IDLE
        self.current_task = None

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"{self.__class__.__name__}(id={self.agent_id}, status={self.status})"
