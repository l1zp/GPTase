"""Enzyme Kinetics Extractor Agent for extracting enzyme reaction data.

This agent uses LLM to extract structured enzyme reaction data from
scientific literature text and tables.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.specialized.enzyme_extraction_utils import create_error_response
from src.agents.specialized.enzyme_extraction_utils import extract_pdb_ids_from_text
from src.agents.specialized.enzyme_extraction_utils import merge_pdb_ids
from src.agents.specialized.enzyme_extraction_utils import sanitize_reaction_list_fields
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS

logger = logging.getLogger(__name__)

# Document source types
_SOURCE_TYPE_TEXT = "text"
_SOURCE_TYPE_FILE = "file"
_SOURCE_TYPE_URL = "url"
_UNKNOWN_SOURCE_FILE = "inline_text"

# System prompt for LLM extraction
SYSTEM_PROMPT = (
    "You are an expert biochemical text parser. Extract enzyme reaction data "
    "from academic-style text and return STRICT JSON that conforms to the following structure. "
    "No markdown, no commentary, no trailing commas. If a field is unknown, use null or an empty list. "
    "Schema (examples of keys and types, not values): "
    '{"reactions": [{"source_file": string|null, "enzyme_name": string|null, "substrates": [string], '
    '"products": [string], "conditions": {"temperature": string|null, "pH": string|null, "buffer": string|null, "time": string|null, "notes": string|null}, '
    '"kinetics": {"Km": number|null, "Km_unit": string|null, "Vmax": number|null, "Vmax_unit": string|null, '
    '"kcat": number|null, "kcat_unit": string|null, "kcat_over_KM": number|null, "kcat_over_KM_unit": string|null, '
    '"Tm": number|null, "Tm_unit": string|null}, "mutations": [string], "yield_percent": number|null, "citations": [string], '
    '"pdb_ids": [string]}], "pipeline": {"steps": [{"name": string, "description": string, "status": string}], "validations": [string], "errors": [string]}}. '
    "CRITICAL RULES: "
    "0) EXTRACTION PRINCIPLE: ONLY extract information that is EXPLICITLY STATED in the input text. "
    "   - Do NOT infer, deduce, or use external biochemical knowledge "
    "   - Do NOT fill in missing values based on assumptions "
    "   - If information is not mentioned, use null or empty array [] "
    "   - Every extracted value must be traceable to specific text in the input "
    "1) COMPREHENSIVE EXTRACTION: Extract EVERY enzyme variant from tables, not just 'important' ones. "
    "If a table has N rows, you MUST extract all N variants. Each row is a separate reaction entry. "
    "DO NOT stop after extracting only the first few variants - you must extract ALL of them. "
    "2) Never hallucinate numbers; only extract if explicitly present. "
    "3) Keep units alongside numeric values in the *_unit fields. "
    "4) Prefer precise biochemical names (IUPAC/common) over generic phrases. "
    "5) When multiple reactions are present, split them into separate entries. "
    "6) Extract ALL kinetics parameters from table columns: "
    "   - kcat (turnover number, typically s^-1) → kinetics.kcat and kinetics.kcat_unit "
    "   - KM (Michaelis constant, typically mM) → kinetics.Km and kinetics.Km_unit "
    "   - kcat/KM (catalytic efficiency, typically M^-1s^-1) → kinetics.kcat_over_KM and kinetics.kcat_over_KM_unit "
    "   - Tm (melting temperature, typically °C) → kinetics.Tm and kinetics.Tm_unit "
    "   For 'n.c.' (not calculable), 'n.d.' (not detected), 'n.m.' (not measured), use null for the value "
    "   For values with ± (uncertainty), extract the mean value (e.g., '0.07 ± 0.02' → 0.07) "
    "7) Extract yield_percent ONLY when explicitly mentioned as a percentage yield. "
    "8) For PDB IDs: only include 4-character codes starting with a digit (e.g., 1ABC, 8XYZ). "
    "9) For mutations: extract from tables or text as a list (e.g., ['L12A', 'F45Y']). "
    "10) Return valid JSON only; no explanation, no markdown code blocks.")


def _extract_json_from_markdown(content: str) -> str:
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


def _build_user_prompt(text: str, source_file: str) -> str:
    """Build user prompt for LLM extraction.

    Args:
        text: Content to extract from.
        source_file: Source file identifier.

    Returns:
        Formatted prompt string.
    """
    return (f"Extract enzyme reaction data from the following text "
            f"(source: {source_file}):\n\n{text}")


class EnzymeKineticsExtractorAgent(BaseAgent):
    """Agent for extracting enzyme kinetics data from scientific text.

    This agent uses LLM to extract structured enzyme reaction data including:
    - Enzyme names and variants
    - Substrates and products
    - Kinetic parameters (kcat, KM, kcat/KM, Tm, Vmax)
    - Experimental conditions
    - Mutations and yields
    - PDB IDs and citations

    The agent returns data in a structured JSON format conforming to the
    ExtractionResult schema.
    """

    AGENT_NAME = "enzyme_kinetics_extractor"

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
    ):
        """Initialize EnzymeKineticsExtractorAgent.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: MemoryManager instance.
            tool_registry: ToolRegistry instance.
            model_manager: ModelManager instance for LLM operations.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=[
                "extract_enzyme_kinetics",
                "extract_kinetic_parameters",
                "parse_reaction_data",
                "extract_mutations",
            ],
        )
        self.model_manager = model_manager

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process enzyme kinetics extraction task.

        Args:
            task: Task dictionary containing:
                - text: Text content to extract from (required)
                - source_file: Optional source file path
            session_id: Extraction session ID for tracking.
            agent_id: Agent ID for tracking.
            step_id: Session step ID for tracking.

        Returns:
            Dictionary with:
                - status: STATUS_SUCCESS or STATUS_ERROR
                - data: Extraction results with reactions and pipeline metadata
        """
        try:
            # Extract task parameters
            text = task.get("text", "")
            source_file = task.get("source_file", _UNKNOWN_SOURCE_FILE)

            if not text:
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": "No text provided for extraction"
                    },
                }

            if not self.model_manager:
                return create_error_response("LLM extraction aborted: missing Model",
                                             ["Model is required"])

            logger.info(f"Extracting enzyme kinetics from: {source_file}")

            # Build messages
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": _build_user_prompt(text, source_file)
                },
            ]

            # Call LLM
            resp = await self.model_manager.generate(
                messages,
                agent_id=agent_id or self.agent_id,
                agent_name=self.AGENT_NAME,
                session_id=session_id,
                step_id=step_id,
            )

            if not resp.content:
                return create_error_response(
                    "LLM extraction failed: empty response",
                    ["Model returned empty response"],
                )

            # Parse JSON response
            cleaned_content = _extract_json_from_markdown(resp.content or "{}")
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                return create_error_response(
                    "LLM extraction failed: invalid JSON",
                    [
                        f"JSON parsing error: {e}",
                        f"Response content: {cleaned_content[:500]}"
                    ],
                )

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

            return {
                "status": STATUS_SUCCESS,
                "data": data,
            }

        except Exception as e:
            logger.error(f"Enzyme kinetics extraction failed: {e}", exc_info=True)
            return create_error_response("LLM extraction failed", [str(e)])
