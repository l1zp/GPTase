"""Enzyme Design Data Refinement Tool.

This tool provides post-processing for enzyme design workflow extraction results,
ensuring data integrity and adding default values for missing fields.
"""

import logging
from typing import Any, Dict

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


class EnzymeDesignTool(BaseTool):
    """Tool for refining and validating enzyme design workflow JSON data."""

    def __init__(self):
        super().__init__(
            name="enzyme_design_tool",
            description=
            "Sanitize and validate enzyme design workflow data with Chain-of-Thought integrity.",
        )

    async def execute(self, data: Dict[str, Any], **kwargs) -> ToolResult:
        """Refine the design extraction data."""
        try:
            refined_data = self._post_process_data(data)
            return ToolResult.success(refined_data)
        except Exception as e:
            logger.error(f"Design data refinement failed: {e}")
            return ToolResult.error(str(e))

    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process and validate extracted data."""
        _TOP_LEVEL_DEFAULTS = {
            "task": {
                "type": "enzyme_design_workflow_extraction",
                "query": "Expert extraction"
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

        for key, default_value in _TOP_LEVEL_DEFAULTS.items():
            data.setdefault(key, default_value)

        # Sanitize nested entries
        for step in data.get("design_steps", []):
            step.setdefault("step_id", "unknown")
            step.setdefault("techniques", [])
            step.setdefault("outcomes", [])

        for cycle in data.get("optimization_cycles", []):
            cycle.setdefault("cycle_id", "unknown")
            cycle.setdefault("improvements", [])

        return data

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Raw design JSON to refine"
                }
            },
            "required": ["data"]
        }
