"""LLM-driven Enzyme Reaction Extractor

Uses a Large Language Model via Model to parse literature-style content
and return structured JSON conforming to the ExtractionResult schema defined in
`markdown_enzyme_parser.py`. Includes optimized prompts for context-rich parsing.
"""

import json
from typing import Any, Dict, List

from pydantic import ValidationError

from src.agents.base import BaseAgent
from src.models.model import Model
from src.models.types import ModelRole
from src.tools.markdown_enzyme_parser import ExtractionResult

SYSTEM_PROMPT = (
    "You are an expert biochemical text parser. Extract enzyme reaction data "
    "from academic-style text and return STRICT JSON that conforms to the following structure. "
    "No markdown, no commentary, no trailing commas. If a field is unknown, use null or an empty list. "
    "Schema (examples of keys and types, not values): "
    '{"reactions": [{"source_file": string|null, "enzyme_name": string|null, "substrates": [string], '
    '"products": [string], "conditions": {"temperature": string|null, "pH": string|null, "buffer": string|null, "time": string|null, "notes": string|null}, '
    '"kinetics": {"Km": number|null, "Km_unit": string|null, "Vmax": number|null, "Vmax_unit": string|null}, "yield_percent": number|null, "citations": [string], '
    '"pdb_ids": [string]}], "pipeline": {"steps": [{"name": string, "description": string, "status": string}], "validations": [string], "errors": [string]}}. '
    "Rules: 1) Never hallucinate numbers; only extract if explicitly present. 2) Keep units alongside numeric values in the *_unit fields. "
    "3) Prefer precise biochemical names (IUPAC/common) over generic phrases. 4) When multiple reactions are present, split them. "
    '5) PDB IDs are four-character codes (first is a digit) like 1ABC; include any PDB IDs you find in the "pdb_ids" list for the corresponding reaction. '
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
    import re

    candidates = re.findall(r"\b[1-9][A-Za-z0-9]{3}\b", text)
    filtered = []
    for c in candidates:
        if any(ch.isalpha() for ch in c[1:]):
            filtered.append(c.upper())
    return sorted(set(filtered))


async def extract_with_llm(
    text: str,
    source_file: str = "unknown.md",
    manager: Model | None = None,
) -> Dict[str, Any]:
    if manager is None:
        return {
            "reactions": [],
            "pipeline": {
                "steps": [
                    {
                        "name": "llm_extract",
                        "description": "LLM extraction aborted: missing Model",
                        "status": "failed",
                    }
                ],
                "validations": [],
                "errors": ["Model is required"],
            },
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(text, source_file)},
    ]

    try:
        resp = await manager.generate(messages, role=ModelRole.GENERAL)
        content = resp.content or "{}"
        data = json.loads(content)
        pdb_ids = extract_pdb_ids_from_text(text)
        for r in data.get("reactions", []):
            existing = [pid.upper() for pid in r.get("pdb_ids", [])]
            r["pdb_ids"] = sorted(set(existing + pdb_ids))
        pipeline = data.setdefault(
            "pipeline", {"steps": [], "validations": [], "errors": []}
        )
        validations = pipeline.get("validations", [])
        validations.append(f"pdb_ids_extracted:{len(pdb_ids)}")
        pipeline["validations"] = validations
        ExtractionResult(**data)
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        return {
            "reactions": [],
            "pipeline": {
                "steps": [
                    {
                        "name": "llm_extract",
                        "description": "Failed to parse/validate JSON output",
                        "status": "failed",
                    }
                ],
                "validations": [],
                "errors": [str(e)],
            },
        }
    except Exception as e:
        return {
            "reactions": [],
            "pipeline": {
                "steps": [
                    {
                        "name": "llm_extract",
                        "description": "LLM call failed",
                        "status": "failed",
                    }
                ],
                "validations": [],
                "errors": [str(e)],
            },
        }


class LLMEnzymeExtractorAgent(BaseAgent):
    def __init__(
        self, agent_id: str, memory_manager, tool_registry, model_manager: Model
    ):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["llm_enzyme_extraction"],
        )
        self.model_manager = model_manager

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        doc = task.get("document") or {}
        source_type = (doc.get("source_type") or "text").lower()
        content = doc.get("content")
        path = doc.get("path")
        url = doc.get("url")

        text = ""
        source_file = "unknown.md"

        if source_type == "text":
            if not content:
                return {"status": "error", "error": "Missing text content"}
            text = str(content)
            source_file = "inline_text.md"
        elif source_type == "file":
            if not path:
                return {"status": "error", "error": "Missing file path"}
            source_file = str(path)
            loaded = await self.tools.execute_tool(
                "document_loader", {"source_type": "file", "path": str(path)}
            )
            if loaded.status.value != "success":
                return {"status": "error", "error": loaded.error or "load_failed"}
            text = loaded.data.get("text", "")
        elif source_type == "url":
            if not url:
                return {"status": "error", "error": "Missing URL"}
            source_file = str(url)
            loaded = await self.tools.execute_tool(
                "document_loader", {"source_type": "url", "url": str(url)}
            )
            if loaded.status.value != "success":
                return {"status": "error", "error": loaded.error or "load_failed"}
            text = loaded.data.get("text", "")
        else:
            return {"status": "error", "error": "Unsupported source_type"}

        data = await extract_with_llm(
            text=text,
            source_file=source_file,
            manager=self.model_manager,
        )

        return {"status": "success", "data": {"extraction": data}}
