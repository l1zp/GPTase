"""Agent-local tool for enzyme-variant-normalizer.

Wraps the deterministic ``normalize_variant_payload`` function in the
sibling ``normalizer.py`` so the LLM-driven agent can invoke it through
the standard tool-call protocol.

This module is auto-discovered by ``Agent.from_markdown`` when the
agent definition lives at ``.claude/agents/enzyme-variant-normalizer/``.
The tool is registered with ``allowed_agents=["enzyme-variant-normalizer"]``
so other agents cannot call it.

The sibling normalizer.py is loaded via importlib because tools.py
itself is imported by ``Agent._register_agent_local_tools`` under a
synthetic module name with no parent package — relative imports won't
work, and the agent dir isn't on sys.path.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from gptase.tools.base import BaseTool

# Load the sibling normalizer.py module.
_normalizer_spec = importlib.util.spec_from_file_location(
    "_enzyme_variant_normalizer_impl",
    Path(__file__).parent / "normalizer.py",
)
_normalizer = importlib.util.module_from_spec(_normalizer_spec)
_normalizer_spec.loader.exec_module(_normalizer)
normalize_variant_payload = _normalizer.normalize_variant_payload

_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "text_extraction_data": {
            "type":
            "array",
            "description": ("List of replica payloads from enzyme-kinetics-extractor. "
                            "Each replica is a dict with a 'reactions' list."),
            "items": {
                "type": "object"
            },
        },
        "vision_extraction_data": {
            "type":
            "array",
            "description": ("List of replica payloads from vision-image-analyzer "
                            "(typically the .extracted_tables field of each replica)."),
            "items": {
                "type": "object"
            },
        },
        "si_extraction_data": {
            "type":
            "object",
            "description":
            ("Optional supplementary-information extraction payload from a "
             "single enzyme-kinetics-extractor run on the SI document."),
        },
        "document_path": {
            "type": "string",
            "description": "Absolute path to the original paper markdown file.",
        },
        "si_document_path": {
            "type":
            "string",
            "description":
            ("Optional absolute path to the supplementary-information markdown "
             "file, when one was extracted in step 3s."),
        },
    },
    "required": [
        "text_extraction_data",
        "vision_extraction_data",
        "document_path",
    ],
}


class NormalizeEnzymeVariantsTool(BaseTool):
    """Reconcile replicated enzyme extraction results into canonical variants.

    Performs deduplication, mutation merging, kinetics aggregation, and
    sequence augmentation against any PDB IDs surfaced in the inputs.
    The full implementation lives in the sibling ``normalizer.py``;
    this tool is a thin JSON adapter so the LLM agent can call it via
    tool-use.
    """

    name = "NormalizeEnzymeVariants"
    description = ("Reconcile replicated enzyme extraction results into deduplicated, "
                   "canonically named variant records with merged kinetics. Returns "
                   "JSON with 'normalized_variants' and 'normalization_summary' keys.")

    def get_schema(self) -> Dict[str, Any]:
        return _SCHEMA

    async def execute(
        self,
        text_extraction_data: List[Dict[str, Any]],
        vision_extraction_data: List[Dict[str, Any]],
        document_path: str,
        si_extraction_data: Optional[Dict[str, Any]] = None,
        si_document_path: Optional[str] = None,
    ) -> str:
        # The underlying normalizer expects a single ``inputs`` dict.
        # ``si_extraction_data`` is folded into ``text_extraction_data``
        # so it joins the same row-collection pass.
        merged_text = list(text_extraction_data or [])
        if si_extraction_data:
            merged_text.append(si_extraction_data)

        inputs: Dict[str, Any] = {
            "text_extraction_data": merged_text,
            "vision_extraction_data": vision_extraction_data or [],
            "document_path": document_path,
        }
        if si_document_path:
            inputs["si_document_path"] = si_document_path

        result = normalize_variant_payload(inputs)
        return json.dumps(result, ensure_ascii=False)
