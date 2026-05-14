"""pre_run hook for enzyme-scaffold-mapper.

Parses the task envelope to obtain ``document_path`` + ``variant_names``,
loads the per-paper scaffold payload via ``payload.py``, and INJECTS the
structured prompt block into ``ctx.prompt``.

Failure modes (all short-circuit before any LLM call):
- ``document_path`` missing.
- Cannot resolve a paper_id (path not under .../papers/markdowns/<paper>/...).
- ``sections.*.json`` artifacts absent (tagger Step 2 has not run).

When the scaffold-tagged-items list ends up empty (e.g. the tagger has
not been re-run with the new prompt yet), we still let the LLM run — it
will gracefully emit `pdb_id_source: registry_hint` or `null` mappings
based purely on variant_names + the registry name index.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from gptase.agents.hooks import HookContext

_MODULE_NAME = "_esm_payload"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME,
                                               Path(__file__).parent / "payload.py")
assert _spec is not None and _spec.loader is not None
_payload_mod = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = _payload_mod
_spec.loader.exec_module(_payload_mod)
resolve_paper_payload = _payload_mod.resolve_paper_payload
render_paper_for_llm = _payload_mod.render_paper_for_llm


def _extract_text(prompt: Union[str, List[Dict[str, Any]]]) -> str:
    if isinstance(prompt, str):
        return prompt
    parts: List[str] = []
    for entry in prompt or []:
        if isinstance(entry, dict) and entry.get("type") == "text":
            parts.append(entry.get("text", ""))
    return "\n".join(parts)


def _parse_balanced_json_at(text: str, start: int) -> Optional[Dict[str, Any]]:
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _get_inputs(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find a dict that carries `document_path` (variant_names optional)."""
    if isinstance(obj.get("document_path"), str):
        return obj
    inputs = obj.get("inputs")
    if isinstance(inputs, dict) and isinstance(inputs.get("document_path"), str):
        return inputs
    desc = obj.get("description")
    if isinstance(desc, str):
        brace = desc.find("{")
        if brace != -1:
            inner = _parse_balanced_json_at(desc, brace)
            if inner is not None:
                return _get_inputs(inner)
    return None


def _extract_envelope(prompt_text: str) -> Optional[Dict[str, Any]]:
    for marker in ("Input Data:", "Task:"):
        idx = prompt_text.rfind(marker)
        if idx == -1:
            continue
        brace = prompt_text.find("{", idx)
        if brace == -1:
            continue
        obj = _parse_balanced_json_at(prompt_text, brace)
        if obj is None:
            continue
        pair = _get_inputs(obj)
        if pair is not None:
            return pair
    last = None
    cursor = 0
    while True:
        brace = prompt_text.find("{", cursor)
        if brace == -1:
            break
        obj = _parse_balanced_json_at(prompt_text, brace)
        if obj is not None:
            pair = _get_inputs(obj)
            if pair is not None:
                last = pair
        cursor = brace + 1
    return last


def _coerce_variant_names(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    seen = set()
    for v in raw:
        if isinstance(v, str):
            s = v.strip()
            if s and s not in seen:
                out.append(s)
                seen.add(s)
        elif isinstance(v, dict):
            for k in ("variant_name", "enzyme_name", "name"):
                cand = v.get(k)
                if isinstance(cand, str) and cand.strip() and cand.strip() not in seen:
                    out.append(cand.strip())
                    seen.add(cand.strip())
                    break
    return out


def _error_result(message: str) -> Dict[str, Any]:
    return {"status": "error", "error": message, "data": {"content": ""}}


def pre_run(ctx: HookContext) -> Optional[Dict[str, Any]]:
    """Resolve payload + inject prompt; never short-circuits with empty data."""
    prompt_text = _extract_text(ctx.prompt)
    envelope = _extract_envelope(prompt_text)
    if envelope is None:
        return _error_result(
            "enzyme-scaffold-mapper pre_run: could not find `document_path` "
            "in the task envelope.")

    doc_path = envelope.get("document_path")
    si_doc_path = envelope.get("si_document_path")
    variant_names = _coerce_variant_names(envelope.get("variant_names"))

    if not isinstance(doc_path, str) or not doc_path.strip():
        return _error_result(
            "enzyme-scaffold-mapper pre_run: `document_path` must be a non-empty "
            "string.")

    payload = resolve_paper_payload(
        document_path=doc_path,
        si_document_path=si_doc_path if isinstance(si_doc_path, str) else None,
        variant_names=variant_names,
    )

    injection = "\n\n" + render_paper_for_llm(payload) + "\n"
    if isinstance(ctx.prompt, str):
        ctx.prompt = ctx.prompt + injection
    else:
        ctx.prompt = list(ctx.prompt) + [{"type": "text", "text": injection}]

    ctx.extras["paper_id"] = payload.paper_id
    ctx.extras["resolved_document_path"] = payload.document_path
    ctx.extras["scaffold_tagged_count"] = len(payload.scaffold_tagged_items)
    ctx.extras["pdb_candidate_count"] = len(payload.pdb_candidates)
    ctx.extras["available_scaffolds_count"] = len(payload.available_scaffolds)
    return None
