"""Enzyme Kinetics Data Refinement Tool.

This tool provides post-processing for raw extraction results, including:
- Field sanitization (None to empty list)
- PDB ID extraction and mapping
- Pipeline metadata updates
"""

import logging
from typing import Any, Dict, List

from src.agents.specialized.enzyme_extraction_utils import extract_pdb_ids_from_text
from src.agents.specialized.enzyme_extraction_utils import merge_pdb_ids
from src.agents.specialized.enzyme_extraction_utils import sanitize_reaction_list_fields
from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


class EnzymeKineticsTool(BaseTool):
    """Tool for refining raw enzyme kinetics JSON data."""

    def __init__(self):
        super().__init__(
            name="enzyme_kinetics_tool",
            description=
            "Sanitize and refine enzyme reaction data, including PDB ID mapping.",
        )

    async def execute(self,
                      data: Dict[str, Any],
                      raw_text: str = "",
                      **kwargs) -> ToolResult:
        """Refine the extraction data."""
        try:
            # 1. Sanitize fields
            sanitize_reaction_list_fields(data)

            # 2. Extract and merge PDB IDs
            if raw_text:
                pdb_ids = extract_pdb_ids_from_text(raw_text)
                if pdb_ids:
                    merge_pdb_ids(data, pdb_ids)

            # 3. Add refinement step to pipeline
            if "pipeline" not in data:
                data["pipeline"] = {"steps": [], "validations": [], "errors": []}

            data["pipeline"]["steps"].append({
                "name": "data_refinement",
                "description": "Post-extraction sanitization and PDB mapping",
                "status": "completed",
            })

            return ToolResult.success(data)
        except Exception as e:
            logger.error(f"Data refinement failed: {e}")
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Raw JSON data to refine"
                },
                "raw_text": {
                    "type": "string",
                    "description": "Original text for PDB mapping"
                }
            },
            "required": ["data"]
        }
