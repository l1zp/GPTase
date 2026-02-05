"""Enzyme Kinetics Data Refinement Tool.

This tool provides post-processing for raw extraction results, including:
- Field sanitization (None to empty list)
- PDB ID extraction and mapping
- Pipeline metadata updates
"""

import logging
import re
from typing import Any, Dict, List

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# Constants for internal processing
_LIST_FIELDS_TO_SANITIZE = ["substrates", "products", "citations", "pdb_ids"]
_PDB_ID_PATTERN = r"\b[1-9][A-Za-z0-9]{3}\b"


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
            self._sanitize_reaction_list_fields(data)

            # 2. Extract and merge PDB IDs
            if raw_text:
                pdb_ids = self._extract_pdb_ids_from_text(raw_text)
                if pdb_ids:
                    self._merge_pdb_ids(data, pdb_ids)

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

    def _extract_pdb_ids_from_text(self, text: str) -> List[str]:
        """Extract PDB IDs from text.

        PDB IDs are four-character codes starting with a digit (e.g., 1ABC).
        """
        candidates = re.findall(_PDB_ID_PATTERN, text)
        filtered = [c.upper() for c in candidates if any(ch.isalpha() for ch in c[1:])]
        return sorted(set(filtered))

    def _sanitize_reaction_list_fields(self, data: Dict[str, Any]) -> None:
        """Convert None values in list fields to empty lists."""
        for reaction in data.get("reactions", []):
            for field in _LIST_FIELDS_TO_SANITIZE:
                if reaction.get(field) is None:
                    reaction[field] = []

    def _merge_pdb_ids(self, data: Dict[str, Any], pdb_ids: List[str]) -> None:
        """Merge extracted PDB IDs into reaction data."""
        for reaction in data.get("reactions", []):
            existing = [pid.upper() for pid in reaction.get("pdb_ids", [])]
            reaction["pdb_ids"] = sorted(set(existing + pdb_ids))

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
