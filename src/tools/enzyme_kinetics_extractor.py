"""Enzyme Kinetics Extractor Tool for extracting enzyme reaction data.

This tool uses LLM to extract structured enzyme reaction data from
scientific literature text and tables.
"""

import json
import logging
import re
from typing import Any, Dict

from src.agents.specialized.enzyme_extraction_utils import create_error_response
from src.agents.specialized.enzyme_extraction_utils import extract_pdb_ids_from_text
from src.agents.specialized.enzyme_extraction_utils import merge_pdb_ids
from src.agents.specialized.enzyme_extraction_utils import sanitize_reaction_list_fields
from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.prompts import ENZYME_KINETICS_EXTRACTION_PROMPT
from src.tools.tracking_mixin import TrackingMixin

logger = logging.getLogger(__name__)

# Document source type
_UNKNOWN_SOURCE_FILE = "inline_text"


class EnzymeKineticsExtractorTool(BaseTool, TrackingMixin):
    """Tool for extracting enzyme kinetics data from scientific text.

    This tool uses LLM to extract structured enzyme reaction data including:
    - Enzyme names and variants
    - Substrates and products
    - Kinetic parameters (kcat, KM, kcat/KM, Tm, Vmax)
    - Experimental conditions
    - Mutations and yields
    - PDB IDs and citations

    The tool returns data in a structured JSON format conforming to the
    ExtractionResult schema.
    """

    def __init__(
        self,
        model_manager=None,
        agent_id=None,
        session_id=None,
        step_id=None,
    ):
        """Initialize EnzymeKineticsExtractorTool.

        Args:
            model_manager: ModelManager instance for LLM operations.
            agent_id: Optional agent ID for session tracking.
            session_id: Optional session ID for session tracking.
            step_id: Optional step ID for workflow step tracking.
        """
        BaseTool.__init__(
            self,
            name="enzyme_kinetics_extractor",
            description="Extract enzyme kinetics data from scientific text using LLM",
            timeout=Timeouts.EXTRACTION,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager

    async def execute(self,
                      text: str,
                      source_file: str = _UNKNOWN_SOURCE_FILE) -> ToolResult:
        """Extract enzyme kinetics data from text.

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
                error_data = create_error_response(
                    "LLM extraction aborted: missing Model",
                    ["Model is required"],
                )
                return ToolResult.error(
                    error_data.get("data", {}).get("error", "Missing model"))

            logger.info(f"Extracting enzyme kinetics from: {source_file}")

            # Build messages
            messages = [
                {
                    "role": "system",
                    "content": ENZYME_KINETICS_EXTRACTION_PROMPT
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
                error_data = create_error_response(
                    "LLM extraction failed: empty response",
                    ["Model returned empty response"],
                )
                return ToolResult.error(
                    error_data.get("data", {}).get("error", "Empty response"))

            # Parse JSON response
            cleaned_content = self._extract_json_from_markdown(resp.content or "{}")
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                error_data = create_error_response(
                    "LLM extraction failed: invalid JSON",
                    [
                        f"JSON parsing error: {e}",
                        f"Response content: {cleaned_content[:500]}"
                    ],
                )
                return ToolResult.error(
                    error_data.get("data", {}).get("error", "Invalid JSON"))

            # Post-process extracted data
            sanitize_reaction_list_fields(data)

            # Extract PDB IDs from text
            pdb_ids = extract_pdb_ids_from_text(text)
            if pdb_ids:
                merge_pdb_ids(data, pdb_ids)

            # Add pipeline metadata
            if "pipeline" not in data:
                data["pipeline"] = {
                    "steps": [],
                    "validations": [],
                    "errors": [],
                }

            data["pipeline"]["steps"].append({
                "name": "llm_extraction",
                "description": "Extract enzyme kinetics using LLM",
                "status": "completed",
            })

            reactions = data.get("reactions", [])
            logger.info(f"Extraction complete: {len(reactions)} reactions extracted")

            return ToolResult.success(data)

        except Exception as e:
            logger.error(f"Enzyme kinetics extraction failed: {e}", exc_info=True)
            error_data = create_error_response("LLM extraction failed", [str(e)])
            return ToolResult.error(error_data.get("data", {}).get("error", str(e)))

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
        return (f"Extract enzyme reaction data from the following text "
                f"(source: {source_file}):\n\n{text}")

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
