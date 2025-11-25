"""LLM-driven Enzyme Reaction Extractor

Uses a Large Language Model via ModelManager to parse literature-style content
and return structured JSON conforming to the ExtractionResult schema defined in
`markdown_enzyme_parser.py`. Includes optimized prompts for context-rich parsing.
"""

import json
import os
from typing import Dict, Any, List, Optional
from src.models.manager import ModelManager
from src.models.types import ModelRole
from .markdown_enzyme_parser import ExtractionResult  # reuse schema for validation
from pydantic import ValidationError


SYSTEM_PROMPT = (
    "You are an expert biochemical text parser. Extract enzyme reaction data "
    "from academic-style text and return STRICT JSON that conforms to the following structure. "
    "No markdown, no commentary, no trailing commas. If a field is unknown, use null or an empty list. "
    "Schema (examples of keys and types, not values): "
    "{\"reactions\": [{\"source_file\": string|null, \"enzyme_name\": string|null, \"substrates\": [string], "
    "\"products\": [string], \"conditions\": {\"temperature\": string|null, \"pH\": string|null, \"buffer\": string|null, \"time\": string|null, \"notes\": string|null}, "
    "\"kinetics\": {\"Km\": number|null, \"Km_unit\": string|null, \"Vmax\": number|null, \"Vmax_unit\": string|null}, \"yield_percent\": number|null, \"citations\": [string], "
    "\"pdb_ids\": [string]}], \"pipeline\": {\"steps\": [{\"name\": string, \"description\": string, \"status\": string}], \"validations\": [string], \"errors\": [string]}}. "
    "Rules: 1) Never hallucinate numbers; only extract if explicitly present. 2) Keep units alongside numeric values in the *_unit fields. "
    "3) Prefer precise biochemical names (IUPAC/common) over generic phrases. 4) When multiple reactions are present, split them. "
    "5) PDB IDs are four-character codes (first is a digit) like 1ABC; include any PDB IDs you find in the \"pdb_ids\" list for the corresponding reaction. "
)


def build_user_prompt(text: str, source_file: str) -> str:
    return (
        "Task: Extract enzyme reaction information from the following content.\n"
        "Required:\n"
        "- Enzyme name (prefer exact names, include isoforms if stated).\n"
        "- Substrates and products (lists).\n"
        "- Conditions: temperature, pH, buffer, time, notes (strings).\n"
        "- Kinetics: Km and Vmax (numbers) with *_unit strings if present.\n"
        "- Yield percent if explicitly stated.\n"
        "- Citations (DOI, PubMed, journal references as strings).\n"
        "- PDB IDs found in the text (four-character alphanumeric codes with first character a digit).\n"
        f"Context: source file = {source_file}.\n"
        "Output: STRICT JSON only, conforming to the described schema.\n\n"
        "Content:\n" + text
    )


def extract_pdb_ids_from_text(text: str) -> List[str]:
    """Extract likely PDB IDs (4-char, first is digit, at least one letter) from text.

    - Pattern: \b[1-9][A-Za-z0-9]{3}\b
    - Filter out all-digit matches to reduce false positives (e.g., years like 2025).
    - Normalize to uppercase and de-duplicate while preserving sorted order.
    """
    import re

    candidates = re.findall(r"\b[1-9][A-Za-z0-9]{3}\b", text)
    filtered = []
    for c in candidates:
        # Require at least one letter in the last 3 characters to avoid all-digit matches
        if any(ch.isalpha() for ch in c[1:]):
            filtered.append(c.upper())
    # Unique, sorted for stability
    return sorted(set(filtered))


async def extract_with_llm(
    text: str,
    source_file: str = "unknown.md",
    manager: ModelManager | None = None,
) -> Dict[str, Any]:
    """Run LLM extraction and return validated JSON dict.

    Falls back to returning an error structure if JSON cannot be parsed or validated.
    """

    # Require an external ModelManager; if missing, return error
    if manager is None:
        return {
            "reactions": [],
            "pipeline": {
                "steps": [{
                    "name": "llm_extract",
                    "description": "LLM extraction aborted: missing ModelManager",
                    "status": "failed"
                }],
                "validations": [],
                "errors": ["ModelManager is required"]
            }
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(text, source_file)},
    ]

    try:
        resp = await manager.generate(messages, role=ModelRole.GENERAL)
        content = resp.content or "{}"
        data = json.loads(content)
        # Attach locally extracted PDB IDs to each reaction for robustness
        pdb_ids = extract_pdb_ids_from_text(text)
        for r in data.get("reactions", []):
            # do not overwrite if LLM provided; merge unique
            existing = [pid.upper() for pid in r.get("pdb_ids", [])]
            r["pdb_ids"] = sorted(set(existing + pdb_ids))
        # Add a validation note
        pipeline = data.setdefault("pipeline", {"steps": [], "validations": [], "errors": []})
        validations = pipeline.get("validations", [])
        validations.append(f"pdb_ids_extracted:{len(pdb_ids)}")
        pipeline["validations"] = validations
        # Validate against schema
        ExtractionResult(**data)  # raises ValidationError if invalid
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        return {
            "reactions": [],
            "pipeline": {
                "steps": [{
                    "name": "llm_extract",
                    "description": "Failed to parse/validate JSON output",
                    "status": "failed"
                }],
                "validations": [],
                "errors": [str(e)]
            }
        }
    except Exception as e:
        return {
            "reactions": [],
            "pipeline": {
                "steps": [{
                    "name": "llm_extract",
                    "description": "LLM call failed",
                    "status": "failed"
                }],
                "validations": [],
                "errors": [str(e)]
            }
        }
