"""pre_run hook for enzyme-kinetics-screener.

Validates that the supplied ``document_path`` resolves to a readable
markdown file **before** the LLM is invoked. Fail-fast on missing /
typo'd inputs instead of letting the LLM waste turns exploring the
filesystem and burning ``max_iterations``.

The hook does NOT short-circuit the LLM on success — it only blocks
when the path is invalid. When the file exists, ``pre_run`` returns
``None`` and the agent runs normally.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from gptase.agents.hooks import HookContext


def _extract_text(prompt: Union[str, List[Dict[str, Any]]]) -> str:
    if isinstance(prompt, str):
        return prompt
    parts: List[str] = []
    for entry in prompt or []:
        if isinstance(entry, dict) and entry.get("type") == "text":
            parts.append(entry.get("text", ""))
    return "\n".join(parts)


def _parse_balanced_json_at(text: str, start: int) -> Optional[Dict[str, Any]]:
    """Parse a balanced JSON object beginning at index *start*, or None."""
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


def _extract_document_path(prompt_text: str) -> Optional[str]:
    """Pull document_path from the CURRENT task envelope.

    The prompt may carry a memory-context prefix that mentions prior
    document_path values from previous screener runs. We must anchor on
    the current task's envelope:

    - ``_build_user_prompt`` always renders ``Input Data:\\n{...}`` —
      the JSON immediately after that marker is authoritative.
    - For direct CLI ``-d '{"document_path": "..."}'``, the task
      description IS the JSON; it shows up after ``Task: `` too.

    Strategy: scan for either anchor (``Input Data:`` first, then
    ``Task: ``) and parse the JSON that follows. As a last-resort
    fallback, take the LAST balanced JSON object in the prompt (current
    task always comes after memory context).
    """
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
        dp = _get_document_path(obj)
        if dp is not None:
            return dp

    # Fallback: scan all balanced JSON objects, return LAST one's doc path.
    last_dp: Optional[str] = None
    cursor = 0
    while True:
        brace = prompt_text.find("{", cursor)
        if brace == -1:
            break
        obj = _parse_balanced_json_at(prompt_text, brace)
        if obj is not None:
            dp = _get_document_path(obj)
            if dp is not None:
                last_dp = dp
        cursor = brace + 1
    return last_dp


def _get_document_path(obj: Dict[str, Any]) -> Optional[str]:
    """Pull document_path out of a single dict, walking the wrapper layers."""
    if isinstance(obj.get("document_path"), str):
        return obj["document_path"]
    inputs = obj.get("inputs")
    if isinstance(inputs, dict) and isinstance(inputs.get("document_path"), str):
        return inputs["document_path"]
    desc = obj.get("description")
    if isinstance(desc, str):
        brace = desc.find("{")
        if brace != -1:
            inner = _parse_balanced_json_at(desc, brace)
            if inner is not None:
                return _get_document_path(inner)
    return None


def _resolve_doc(path_str: str) -> Optional[Path]:
    """Resolve a user-supplied path to an existing .md file (or None).

    Some MinerU-produced paper directories store the body as
    ``<paper>/main/full.md`` and others as ``<paper>/main/main.md`` —
    both layouts are present in the corpus, so try both.
    """
    p = Path(path_str).expanduser()
    if p.suffix.lower() == ".md" and p.is_file():
        return p
    if p.is_dir():
        candidates = (
            p / "main" / "full.md",
            p / "main" / "main.md",
            p / "full.md",
            p / "main.md",
        )
        for candidate in candidates:
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
    """Short-circuit with an error result if document_path doesn't resolve.

    Returns ``None`` (lets the LLM run normally) when the file exists.
    """
    prompt_text = _extract_text(ctx.prompt)
    doc_path = _extract_document_path(prompt_text)
    if doc_path is None:
        return _error_result(
            "enzyme-kinetics-screener pre_run: could not find a "
            "`document_path` value in the input. Pass it via "
            '`-d \'{"document_path": "..."}\'` for direct CLI or as '
            "`task_inputs={\"document_path\": \"...\"}` for DelegateTask.")
    resolved = _resolve_doc(doc_path)
    if resolved is None:
        return _error_result(f"enzyme-kinetics-screener pre_run: document_path "
                             f"'{doc_path}' does not resolve to a readable .md file. "
                             f"Tried the path directly and, if it is a directory, "
                             f"`main/full.md`, `full.md`, and `main.md` under it.")
    return None  # file exists — let the LLM proceed
