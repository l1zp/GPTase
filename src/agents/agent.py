"""Unified Agent interface with dual execution paths.

This module provides a single Agent class that automatically routes to
Claude Agent SDK or a custom LLM loop based on the configured model.

Usage:
    agent = Agent(
        system_prompt="You are a helpful assistant.",
        skills=["skills/academic-pdf-reader/SKILL.md"],
    )
    result = await agent.run("Analyze this paper")
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Claude model prefixes for SDK routing
_CLAUDE_MODEL_PREFIXES = ("claude-", )


class Agent:
    """Unified agent that routes to Claude SDK or custom LLM loop.

    When the configured model is a Claude model, execution is delegated
    to claude_code_sdk.Agent which provides built-in tools (bash,
    text_editor) and manages the agent loop.

    For non-Claude models, a simple LLM loop using Model.generate()
    is used instead.

    Attributes:
        system_prompt: System prompt for the agent.
        skills: List of skill markdown file paths to load.
        model_config: Optional ModelConfig for non-Claude execution.
        model_name: Model name for routing (default from FrameworkConfig).
    """

    def __init__(
        self,
        system_prompt: str,
        skills: Optional[List[str]] = None,
        model_config: Optional[Any] = None,
        model_name: Optional[str] = None,
    ):
        """Initialize agent.

        Args:
            system_prompt: System prompt for the agent.
            skills: Optional list of skill markdown file paths.
            model_config: Optional ModelConfig for LLM execution.
            model_name: Optional model name override for routing.
        """
        self.system_prompt = system_prompt
        self.skills = skills or []
        self.model_config = model_config
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        """Get the effective model name for routing."""
        if self._model_name:
            return self._model_name
        if self.model_config and hasattr(self.model_config, "model_name"):
            return self.model_config.model_name
        # Fall back to FrameworkConfig
        try:
            from src.core.config import FrameworkConfig
            config = FrameworkConfig()
            return config.llm_model
        except Exception:
            return "unknown"

    def is_claude_model(self) -> bool:
        """Check if the configured model is a Claude model."""
        name = self.model_name.lower()
        return any(name.startswith(prefix) for prefix in _CLAUDE_MODEL_PREFIXES)

    async def run(self, task: str) -> Dict[str, Any]:
        """Execute a task using the appropriate execution engine.

        Args:
            task: Task description / user prompt.

        Returns:
            Dictionary with status and result data.
        """
        if self.is_claude_model():
            return await self._run_with_sdk(task)
        else:
            return await self._run_with_llm(task)

    async def _run_with_sdk(self, task: str) -> Dict[str, Any]:
        """Execute via Claude Agent SDK.

        The SDK provides built-in bash and text_editor tools.
        Skills are injected into the system prompt.

        Args:
            task: Task description.

        Returns:
            Result dictionary.
        """
        try:
            from claude_code_sdk import Agent as ClaudeAgent

            full_prompt = self._build_full_prompt()
            agent = ClaudeAgent(
                model=self.model_name,
                system_prompt=full_prompt,
            )
            result = await agent.run(task)

            return {
                "status": "success",
                "data": {
                    "content": result
                },
            }

        except ImportError:
            raise ImportError("Claude Agent SDK not installed. "
                              "Install with: pip install claude-code-sdk") from None
        except Exception as e:
            logger.error(f"SDK execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def _run_with_llm(self, task: str) -> Dict[str, Any]:
        """Execute via custom LLM loop using Model.generate().

        This path is used for non-Claude models (OpenAI, DeepSeek, etc.).

        Args:
            task: Task description.

        Returns:
            Result dictionary.
        """
        try:
            from src.models.model import Model

            model = Model(default_config=self.model_config)
            full_prompt = self._build_full_prompt()

            messages = [
                {
                    "role": "system",
                    "content": full_prompt
                },
                {
                    "role": "user",
                    "content": task
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

    def _build_full_prompt(self) -> str:
        """Build full system prompt by combining base prompt with skills.

        Skills are loaded from markdown files and appended to the
        system prompt.

        Returns:
            Combined system prompt string.
        """
        parts = [self.system_prompt]

        for skill_path in self.skills:
            try:
                path = Path(skill_path)
                if path.exists():
                    content = path.read_text(encoding="utf-8")
                    parts.append(f"\n--- Skill: {path.stem} ---\n{content}")
                else:
                    logger.warning(f"Skill file not found: {skill_path}")
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_path}: {e}")

        return "\n\n".join(parts)
