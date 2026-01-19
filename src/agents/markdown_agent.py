"""Universal agent that executes tasks based on markdown definitions."""

import json
import logging
import re
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.agents.markdown_parser import AgentDefinition
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.models.model import Model
from src.models.types import ModelRole

logger = logging.getLogger(__name__)


class MarkdownAgent(BaseAgent):
    """Universal agent that executes tasks based on markdown definitions.

  This single class can represent any agent type defined in markdown format.
  It uses LLM generation with system prompts from the markdown definition
  to process tasks flexibly without hardcoded logic.
  """

    def __init__(
        self,
        definition: AgentDefinition,
        memory_manager,
        tool_registry,
        model_manager: Optional[Model] = None,
    ):
        """Initialize MarkdownAgent with parsed definition.

    Args:
        definition: Parsed AgentDefinition from markdown.
        memory_manager: Memory manager instance.
        tool_registry: Tool registry instance.
        model_manager: Optional Model instance (required if requires_model=True).

    Raises:
        ValueError: If requires_model=True but no model_manager provided.
    """
        super().__init__(
            agent_id=definition.agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=definition.capabilities,
        )
        self.definition = definition
        self.model_manager = model_manager

        # Validate model requirement
        if definition.requires_model and model_manager is None:
            raise ValueError(
                f"Agent '{definition.agent_id}' requires model_manager but none provided"
            )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task using LLM-based execution.

    Args:
        task: Task dictionary with task-specific data.

    Returns:
        Dictionary with status and result/error.
    """
        await self.update_status(STATUS_SUCCESS)
        try:
            if not self.definition.requires_model:
                # Non-LLM agent: use simple processing
                return await self._process_simple_task(task)

            # LLM-based agent
            return await self._process_llm_task(task)
        except Exception as e:
            logger.error(f"Task processing failed for {self.agent_id}: {e}")
            return {
                "status": STATUS_ERROR,
                "error": str(e),
                "agent_id": self.agent_id,
            }

    async def _process_llm_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process task using LLM generation.

    Args:
        task: Task to process.

    Returns:
        Result dictionary with status and data.
    """
        # Build messages
        messages = [
            {
                "role":
                "system",
                "content":
                self.definition.system_prompt or self._build_default_system_prompt()
            },
            {
                "role": "user",
                "content": self._build_user_prompt(task)
            },
        ]

        # Get model role
        try:
            model_role = ModelRole(self.definition.model_role)
        except ValueError:
            logger.warning(
                f"Invalid model_role '{self.definition.model_role}', using 'general'")
            model_role = ModelRole.GENERAL

        # Generate response
        response = await self.model_manager.generate(messages, role=model_role)

        # Parse and validate output
        result = self._parse_output(response.content or "")

        return {
            "status": STATUS_SUCCESS,
            "data": result,
            "agent_id": self.agent_id,
        }

    async def _process_simple_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process task without LLM (tool-based execution).

    Args:
        task: Task to process.

    Returns:
        Result dictionary with status and data.
    """
        results = []

        # Execute tools if specified
        if self.definition.tools:
            for tool_name in self.definition.tools:
                # Build parameters from task
                params = self._extract_tool_parameters(task, tool_name)

                # Execute tool
                result = await self.tools.execute_tool(tool_name, params)
                results.append({"tool": tool_name, "result": result.model_dump()})

        return {
            "status": STATUS_SUCCESS,
            "data": {
                "results": results
            },
            "agent_id": self.agent_id,
        }

    def _build_default_system_prompt(self) -> str:
        """Build default system prompt if none specified.

    Returns:
        Default system prompt string.
    """
        return f"""You are {self.agent_id}, an AI agent with capabilities: {', '.join(self.capabilities)}.

{self.definition.description}

Task Processing:
{self.definition.task_processing}

Output Format:
{self.definition.output_format}
"""

    def _build_user_prompt(self, task: Dict[str, Any]) -> str:
        """Build user prompt from task.

    Args:
        task: Task dictionary.

    Returns:
        User prompt string.
    """
        # Format task as readable text
        task_text = json.dumps(task, indent=2)

        prompt = f"""Task: {task.get('description', 'Process the following data')}

Input Data:
{task_text}

Process this task according to your instructions and return the result in the specified format.
"""

        # Add examples if available
        if self.definition.examples:
            prompt += f"\n\nExamples:\n{self.definition.examples}"

        return prompt

    def _parse_output(self, content: str) -> Any:
        """Parse LLM output, handling JSON extraction.

    Args:
        content: Raw LLM response content.

    Returns:
        Parsed output (dict or raw text).
    """
        content = content.strip()

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Return as plain text if not JSON
        return {"response": content}

    def _extract_tool_parameters(self, task: Dict[str, Any],
                                 tool_name: str) -> Dict[str, Any]:
        """Extract parameters for a tool from task.

    Args:
        task: Task dictionary.
        tool_name: Name of the tool.

    Returns:
        Tool parameters dictionary.
    """
        # Simple extraction: use task as-is
        # Can be extended with tool-specific logic
        return task.get("parameters", {})
