"""Enzyme Design Workflow Extractor Tool for extracting enzyme design processes.

This tool uses LLM to extract structured enzyme design workflow data from
scientific literature, including design objectives, methodology steps,
key parameters, validation approaches, and results.
"""

import json
import logging
import re
from typing import Any, Dict

from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.prompts import ENZYME_DESIGN_EXTRACTION_PROMPT
from src.tools.tracking_mixin import TrackingMixin

logger = logging.getLogger(__name__)

# Document source type
_UNKNOWN_SOURCE_FILE = "inline_text"


class EnzymeDesignExtractorTool(BaseTool, TrackingMixin):
    """Tool for extracting enzyme design workflow data from scientific text.

    This tool uses LLM to extract structured enzyme design information including:
    - Design objectives and goals
    - Design methodology steps (Planning, Design, Construction, Expression, Assay, Optimization)
    - Techniques and parameters used
    - Key constraints and requirements
    - Optimization cycles and improvements
    - Validation approaches and experimental conditions
    - Results and performance metrics

    The tool returns data in a structured JSON format with Chinese annotations.
    """

    def __init__(
        self,
        model_manager=None,
        agent_id=None,
        session_id=None,
        step_id=None,
    ):
        """Initialize EnzymeDesignExtractorTool.

        Args:
            model_manager: ModelManager instance for LLM operations.
            agent_id: Optional agent ID for session tracking.
            session_id: Optional session ID for session tracking.
            step_id: Optional step ID for workflow step tracking.
        """
        BaseTool.__init__(
            self,
            name="enzyme_design_extractor",
            description=
            "Extract enzyme design workflow data from scientific text using LLM",
            timeout=Timeouts.EXTRACTION,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager

    async def execute(self,
                      text: str,
                      source_file: str = _UNKNOWN_SOURCE_FILE) -> ToolResult:
        """Extract enzyme design workflow data from text.

        Args:
            text: Text content to extract from.
            source_file: Optional source file path for logging.

        Returns:
            ToolResult with extraction data or error information.
        """
        try:
            if not text:
                return ToolResult.error("No text provided for extraction")

            if not self.model_manager:
                error_msg = "LLM extraction aborted: missing Model"
                return ToolResult.error(error_msg)

            logger.info(f"Extracting enzyme design workflow from: {source_file}")

            # Build messages
            messages = [
                {
                    "role": "system",
                    "content": ENZYME_DESIGN_EXTRACTION_PROMPT
                },
                {
                    "role": "user",
                    "content": self._build_user_prompt(text, source_file)
                },
            ]

            # Call LLM
            resp = await self.model_manager.generate(
                messages,
                **self.get_tracking_params(),
            )

            if not resp.content:
                error_msg = "LLM extraction failed: empty response"
                return ToolResult.error(error_msg)

            # Parse JSON response
            cleaned_content = self._extract_json_from_markdown(resp.content or "{}")
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                error_msg = (f"LLM extraction failed: invalid JSON - {e}. "
                             f"Response: {cleaned_content[:500]}")
                return ToolResult.error(error_msg)

            # Validate and post-process extracted data
            data = self._post_process_data(data)

            design_steps = data.get("design_steps", [])
            logger.info(
                f"Design extraction complete: {len(design_steps)} steps extracted")

            return ToolResult.success(data)

        except Exception as e:
            logger.error(f"Enzyme design extraction failed: {e}", exc_info=True)
            error_msg = f"LLM extraction failed: {str(e)}"
            return ToolResult.error(error_msg)

    def _extract_json_from_markdown(self, content: str) -> str:
        """Extract JSON content from markdown code blocks if present.

        Args:
            content: String that may contain markdown-wrapped JSON.

        Returns:
            Cleaned JSON string. If content is not wrapped in markdown,
            returns it as-is.
        """
        if not content:
            return content

        # Try to match ```json ... ``` pattern
        pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            return matches[0]

        # Try to match ``` ... ``` pattern (no language specified)
        pattern = r'```\s*\n(.*?)\n```'
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            return matches[0]

        return content

    def _build_user_prompt(self, text: str, source_file: str) -> str:
        """Build user prompt for LLM extraction.

        Args:
            text: Content to extract from.
            source_file: Source file identifier.

        Returns:
            Formatted prompt string.
        """
        return (f"Extract enzyme design workflow data from the following text "
                f"(source: {source_file}):\n\n{text}")

    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process and validate extracted data.

        Args:
            data: Raw extracted data dictionary.

        Returns:
            Validated and sanitized data dictionary.
        """
        # Default values for top-level fields
        _TOP_LEVEL_DEFAULTS = {
            "task": {
                "type": "enzyme_design_workflow_extraction",
                "query": "Extract enzyme design workflow from scientific literature",
            },
            "chain_of_thought": [],
            "design_objectives": [],
            "design_steps": [],
            "key_decisions": [],
            "key_constraints": [],
            "optimization_cycles": [],
            "experimental_conditions": {},
            "results": {},
            "final_answer": {
                "summary": "",
                "success_metrics": {},
                "key_innovations": []
            },
        }

        # Field defaults for chain_of_thought entries
        _COT_ENTRY_DEFAULTS = {
            "step": 0,
            "phase": None,
            "thought": "",
            "action": "",
            "observation": "",
            "reasoning": "",
        }

        # Field defaults for design_steps entries
        _DESIGN_STEP_DEFAULTS = {
            "step_id": "unknown",
            "category": None,
            "description": "",
            "techniques": [],
            "parameters": {},
            "duration": None,
            "outcomes": [],
        }

        # Field defaults for key_decisions entries
        _DECISION_DEFAULTS = {
            "decision": "",
            "alternatives": [],
            "rationale": "",
            "outcome": "",
        }

        # Field defaults for optimization_cycles entries
        _CYCLE_DEFAULTS = {
            "cycle_id": "unknown",
            "method": "",
            "rounds": None,
            "improvements": [],
        }

        # Set top-level defaults
        for key, default_value in _TOP_LEVEL_DEFAULTS.items():
            data.setdefault(key, default_value)

        # Sanitize nested list entries
        self._sanitize_list_entries(data.get("chain_of_thought", []),
                                    _COT_ENTRY_DEFAULTS)
        self._sanitize_list_entries(data.get("design_steps", []), _DESIGN_STEP_DEFAULTS)
        self._sanitize_list_entries(data.get("key_decisions", []), _DECISION_DEFAULTS)
        self._sanitize_list_entries(data.get("optimization_cycles", []),
                                    _CYCLE_DEFAULTS)

        # Ensure final_answer nested fields exist
        final_answer = data.get("final_answer", {})
        final_answer.setdefault("success_metrics", {})
        final_answer.setdefault("key_innovations", [])

        return data

    def _sanitize_list_entries(self, entries: list, field_defaults: Dict[str,
                                                                         Any]) -> None:
        """Sanitize a list of dictionaries by setting missing fields to defaults.

        Args:
            entries: List of dictionaries to sanitize.
            field_defaults: Default values for each field.
        """
        for entry in entries:
            for field, default_value in field_defaults.items():
                entry.setdefault(field, default_value)

    def get_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Document text to extract from"
                },
                "source_file": {
                    "type": "string",
                    "description": "Source file path (optional)"
                }
            },
            "required": ["text"]
        }
