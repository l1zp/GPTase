"""pre_run hook for enzyme-variant-normalizer.

Replaces the previous deterministic dispatch path: the hook intercepts
the run, parses the JSON task inputs out of the prompt, expands any
upstream-artifact path references, folds the optional SI payload into
the text extraction list, and calls ``normalize_variant_payload``
directly. The LLM never participates.

The artifact-path expansion helpers below are inlined rather than
imported from ``gptase.tools.handlers`` to keep this hook
self-contained. If a second hook ever needs the same logic, promote
them to a shared utility under ``gptase/agents/`` (see plan: Step 5
deferred-promotion note).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from gptase.agents.hooks import HookContext

# Load the sibling normalizer.py module under a synthetic name. tools.py
# previously used the same pattern (Path-based importlib spec) because
# hooks.py / tools.py are themselves loaded under synthetic module names
# with no parent package, so relative imports don't work.
_spec = importlib.util.spec_from_file_location(
    "_enzyme_variant_normalizer_impl",
    Path(__file__).parent / "normalizer.py",
)
assert _spec is not None and _spec.loader is not None
_normalizer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_normalizer)
normalize_variant_payload = _normalizer.normalize_variant_payload

# ---------------------------------------------------------------------------
# Artifact-path expansion (mirror of handlers._maybe_load_artifacts chain).
# ---------------------------------------------------------------------------


def _try_parse_json_object(text: Any) -> Optional[Dict[str, Any]]:
    """Return the first balanced top-level JSON object inside *text*.

    Mirrors ``gptase.tools.handlers._try_parse_json_object``. Returns
    None when no valid object can be recovered.
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    start = stripped.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(stripped)):
            c = stripped[i]
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
                        obj = json.loads(stripped[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    return obj if isinstance(obj, dict) else None
        start = stripped.find("{", start + 1)
    return None


def _try_load_artifact(candidate: str) -> Optional[Any]:
    """Load a worker-artifact JSON envelope and return its unwrapped content."""
    if not candidate or len(candidate) > 2048:
        return None
    path = Path(candidate)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not (isinstance(envelope, dict) and "agent_id" in envelope
            and "content" in envelope):
        return None
    content = envelope.get("content", "")
    parsed = (_try_parse_json_object(content) if isinstance(content, str) else content)
    return parsed if parsed is not None else content


def _maybe_load_artifacts(value: Any) -> Any:
    if isinstance(value, list):
        return [_maybe_load_artifacts(v) for v in value]
    if isinstance(value, str):
        loaded = _try_load_artifact(value)
        if loaded is not None:
            return loaded
    return value


def _resolve_path_inputs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _maybe_load_artifacts(value) for key, value in kwargs.items()}


# ---------------------------------------------------------------------------
# Prompt parsing.
# ---------------------------------------------------------------------------


def _extract_text(prompt: Union[str, List[Dict[str, Any]]]) -> str:
    if isinstance(prompt, str):
        return prompt
    parts: List[str] = []
    for entry in prompt or []:
        if isinstance(entry, dict) and entry.get("type") == "text":
            parts.append(entry.get("text", ""))
    return "\n".join(parts)


def _parse_inputs_from_prompt(prompt_text: str) -> Optional[Dict[str, Any]]:
    """Recover the structured inputs dict from the agent's prompt envelope.

    ``Agent._build_user_prompt`` formats prompts as::

        Task: <description>

        Input Data:
        { ...JSON-encoded task dict, including "inputs"... }

    We parse that JSON and prefer its ``inputs`` field. When the envelope
    can't be located, we fall back to treating the whole parsed object
    as the inputs payload (the legacy ``_execute_deterministic`` path).
    """
    obj = _try_parse_json_object(prompt_text)
    if obj is None:
        return None
    inputs = obj.get("inputs")
    if isinstance(inputs, dict) and inputs:
        return inputs
    return obj


# ---------------------------------------------------------------------------
# Hook entry point.
# ---------------------------------------------------------------------------


def _error_result(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": message,
        "data": {
            "content": ""
        },
    }


def pre_run(ctx: HookContext) -> Dict[str, Any]:
    """Short-circuit the LLM: normalize variants directly."""
    prompt_text = _extract_text(ctx.prompt)
    inputs = _parse_inputs_from_prompt(prompt_text)
    if inputs is None:
        return _error_result(
            "enzyme-variant-normalizer hook could not recover JSON inputs "
            "from the prompt envelope.")

    try:
        resolved = _resolve_path_inputs(inputs)
    except Exception as exc:
        return _error_result(f"Artifact-path expansion failed: {exc}")

    # The pre-migration tool folded si_extraction_data into
    # text_extraction_data before calling the normalizer. Preserve that
    # behavior so the hook is a drop-in replacement.
    text_data = list(resolved.get("text_extraction_data") or [])
    si_data = resolved.get("si_extraction_data")
    if si_data:
        text_data.append(si_data)

    normalizer_inputs: Dict[str, Any] = {
        "text_extraction_data": text_data,
        "vision_extraction_data": resolved.get("vision_extraction_data") or [],
        "document_path": resolved.get("document_path", ""),
    }
    si_path = resolved.get("si_document_path")
    if si_path:
        normalizer_inputs["si_document_path"] = si_path

    try:
        output = normalize_variant_payload(normalizer_inputs)
    except Exception as exc:
        return _error_result(f"normalize_variant_payload raised: {exc}")

    return {
        "status": "success",
        "data": {
            "content": json.dumps(output, ensure_ascii=False),
        },
        "trace": {
            "steps": [{
                "type": "hook",
                "note": "pre_run short-circuit",
            }],
            "total_duration_ms": 0,
        },
    }
