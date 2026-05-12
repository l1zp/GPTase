"""pre_run hook for enzyme-kinetics-figure-extractor.

Validates ``(document_path, item_id)``, resolves the MinerU figure
metadata (caption / parent section / page index / img_path) via
``payload.py``, and INJECTS that metadata block into ``ctx.prompt``.
The actual image bytes are still delivered via the framework's
multimodal pipeline through ``Task.image_paths`` (set by the driver
when invoking the agent programmatically).

Failure modes (all short-circuit before any LLM call):
- ``document_path`` or ``item_id`` missing.
- ``document_path`` does not resolve to a readable .md file.
- No ``*_content_list.json`` sibling.
- ``item_id`` not in outline OR resolves to a non-image kind.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from gptase.agents.hooks import HookContext

# Load sibling payload.py
_MODULE_NAME = "_ekfx_payload"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME,
                                               Path(__file__).parent / "payload.py")
assert _spec is not None and _spec.loader is not None
_payload_mod = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = _payload_mod
_spec.loader.exec_module(_payload_mod)
resolve_figure_payload = _payload_mod.resolve_figure_payload
render_figure_metadata_for_llm = _payload_mod.render_figure_metadata_for_llm


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
    if isinstance(obj.get("document_path"), str) and "item_id" in obj:
        return obj
    inputs = obj.get("inputs")
    if isinstance(inputs, dict):
        if isinstance(inputs.get("document_path"), str) and "item_id" in inputs:
            return inputs
    desc = obj.get("description")
    if isinstance(desc, str):
        brace = desc.find("{")
        if brace != -1:
            inner = _parse_balanced_json_at(desc, brace)
            if inner is not None:
                return _get_inputs(inner)
    return None


def _extract_pair(prompt_text: str) -> Optional[Dict[str, Any]]:
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


def _resolve_doc(path_str: str) -> Optional[Path]:
    p = Path(path_str).expanduser()
    if p.suffix.lower() == ".md" and p.is_file():
        return p
    if p.is_dir():
        for candidate in (p / "main" / "full.md", p / "main" / "main.md", p / "full.md",
                          p / "main.md"):
            if candidate.is_file():
                return candidate
    return None


def _error_result(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": message,
        "data": {
            "content": ""
        },
    }


def pre_run(ctx: HookContext) -> Optional[Dict[str, Any]]:
    """Validate inputs, resolve figure payload, inject metadata into prompt."""
    prompt_text = _extract_text(ctx.prompt)
    pair = _extract_pair(prompt_text)
    if pair is None:
        return _error_result(
            "enzyme-kinetics-figure-extractor pre_run: could not find both "
            "`document_path` and `item_id` in the input.")

    doc_path = pair["document_path"]
    item_id = pair["item_id"]
    if not isinstance(item_id, int):
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return _error_result(
                f"enzyme-kinetics-figure-extractor pre_run: item_id {item_id!r} "
                "is not an integer.")

    resolved = _resolve_doc(doc_path)
    if resolved is None:
        return _error_result(f"enzyme-kinetics-figure-extractor pre_run: document_path "
                             f"'{doc_path}' does not resolve to a readable .md file.")

    try:
        payload = resolve_figure_payload(str(resolved), item_id)
    except (FileNotFoundError, IndexError, ValueError) as exc:
        return _error_result(
            f"enzyme-kinetics-figure-extractor pre_run: {type(exc).__name__}: {exc}")

    if payload.img_path_abs is None:
        return _error_result(
            f"enzyme-kinetics-figure-extractor pre_run: image file not found at "
            f"{payload.img_path_rel!r} relative to {resolved.parent}")

    injection = "\n\n" + render_figure_metadata_for_llm(payload) + "\n"
    if isinstance(ctx.prompt, str):
        ctx.prompt = ctx.prompt + injection
    else:
        ctx.prompt = list(ctx.prompt) + [{"type": "text", "text": injection}]

    ctx.extras["resolved_document_path"] = str(resolved)
    ctx.extras["item_id"] = item_id
    ctx.extras["caption"] = payload.caption
    ctx.extras["img_path_abs"] = str(payload.img_path_abs)
    return None
