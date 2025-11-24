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
    "from academic-style content. Return ONLY valid JSON matching the schema: "
    "{\"reactions\": [{\"source_file\": str, \"enzyme_name\": str|null, \"substrates\": [str], "
    "\"products\": [str], \"conditions\": {\"temperature\": str|null, \"pH\": str|null, \"buffer\": str|null, \"time\": str|null, \"notes\": str|null}, "
    "\"kinetics\": {\"Km\": number|null, \"Km_unit\": str|null, \"Vmax\": number|null, \"Vmax_unit\": str|null}, \"yield_percent\": number|null, \"citations\": [str]}], "
    "\"pipeline\": {\"steps\": [{\"name\": str, \"description\": str, \"status\": str}], \"validations\": [str], \"errors\": [str]}}. "
    "Do not include extra commentary."
)


def build_user_prompt(text: str, source_file: str) -> str:
    return (
        "Task: Extract enzyme reaction information from the following literature-style content.\n"
        "- Identify enzyme names, substrates, products.\n"
        "- Capture reaction conditions (temperature, pH, buffer, time).\n"
        "- Extract kinetic parameters (Km, Vmax) with units if available.\n"
        "- Extract reaction yield percentage if mentioned.\n"
        "- Include citations if recognizable.\n"
        f"- Treat the content as coming from: {source_file}.\n"
        "Return ONLY JSON.\n\n"
        "Content:\n" + text
    )


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
