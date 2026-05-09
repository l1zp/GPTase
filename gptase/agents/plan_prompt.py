"""Expand a YAML plan definition into a Coordinator prompt.

Replaces the deterministic ``PlanManager`` execution path with a single
prompt that the Coordinator main agent reads as a structured to-do list.
The Coordinator is then responsible for issuing the appropriate
``DelegateTask`` calls in order; replicate fan-out becomes "issue N
parallel tool calls in one assistant message" and step-to-step data
flow becomes natural message-history threading.

Public API
----------
``expand_plan_to_prompt(plan_id, **vars)``
    Load ``config/plans/<plan_id>.yaml`` and render it as a prompt string.

Both the legacy schema (``workflow:`` blocks with ``replicate``,
``parallel:`` groups, ``action`` and ``retry_count``) and the simplified
schema (``steps:`` list with ``replicas`` and ``parallel_with``) are
supported. Slice 5 will migrate the YAML to the simplified schema; the
expander handles both so Slice 1 lands additively.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set

import yaml

from gptase.utils.paths import get_paths

logger = logging.getLogger(__name__)

_DEFAULT_PLAN_SUBDIR = "config/plans"
_DEFAULT_AGENTS_SUBDIR = ".claude/agents"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Subdirectory name patterns that typically hold a paper's supplementary
# information markdown (MinerU's output layout). Matched as a regex against
# the directory's basename, case-insensitive.
_SI_SUBDIR_PATTERNS: List[str] = [
    r"^SI(_|$)",
    r"^MOESM\d+",
    r"^supplementary",
    r"^supplemental",
    r"_SI($|_)",
]


def detect_supplementary_path(document_path: str) -> Optional[str]:
    """Best-effort discovery of a paper's supplementary-information markdown.

    Resolution order:
      1. Sibling file ``<stem>_si.<suffix>`` next to ``document_path``.
      2. First subdirectory in the document's parent that matches one of
         ``_SI_SUBDIR_PATTERNS`` (case-insensitive, alphabetical) AND contains
         a ``main.md`` (MinerU's output convention).

    Returns the absolute path to the SI markdown, or None when nothing
    plausible is found.

    The single-path return is intentional: the legacy normalizer
    (``enzyme_variant_normalizer.py``) reads one ``si_document_path`` and
    walks its sibling ``content_list.json`` for HTML tables. Picking the
    alphabetically-first match (e.g. MOESM1 over MOESM2) usually selects
    the most data-rich SI for biochemistry papers.
    """
    if not document_path:
        return None
    doc = Path(document_path)
    if not doc.exists():
        return None

    # 1) Sibling _si file
    if doc.is_file():
        sibling = doc.with_name(doc.stem + "_si" + doc.suffix)
        if sibling.exists():
            return str(sibling)

    # 2) Subdirectory containing main.md
    parent = doc.parent if doc.is_file() else doc
    if not parent.is_dir():
        return None

    si_dirs: List[Path] = []
    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        for pattern in _SI_SUBDIR_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                main_md = child / "main.md"
                if main_md.exists():
                    si_dirs.append(main_md)
                break

    return str(si_dirs[0]) if si_dirs else None


class PlanPromptError(Exception):
    """Raised when a plan YAML cannot be loaded or expanded."""


def expand_plan_to_prompt(
    plan_id: str,
    document_path: Optional[str] = None,
    si_document_path: Optional[str] = None,
    workspace_dir: Optional[str] = None,
    plan_dir: Optional[Path] = None,
    deterministic_agents: Optional[Set[str]] = None,
    auto_resolve_agents: Optional[Set[str]] = None,
    agents_dir: Optional[Path] = None,
    **extra_vars: str,
) -> str:
    """Render a plan YAML as a structured Coordinator prompt.

    Args:
        plan_id: Plan identifier (filename stem under ``config/plans/``).
        document_path: Path to the primary input document.
        si_document_path: Optional path to a supplementary-information doc.
        workspace_dir: Optional workspace directory for output artifacts.
        plan_dir: Optional override for the plan-config directory.
        **extra_vars: Additional template variables that may appear as
            ``{{name}}`` in any input string.

    Returns:
        A multi-line prompt string ready to be fed to the Coordinator.

    Raises:
        PlanPromptError: If the plan YAML cannot be loaded.
    """
    plan_data = _load_plan_yaml(plan_id, plan_dir)

    template_vars: Dict[str, str] = {
        "document_path": document_path or "",
        "si_document_path": si_document_path or "",
        "workspace_dir": workspace_dir or "",
    }
    for key, value in extra_vars.items():
        template_vars[key] = "" if value is None else str(value)

    if deterministic_agents is None:
        deterministic_agents = _scan_deterministic_agents(agents_dir)
    if auto_resolve_agents is None:
        auto_resolve_agents = _scan_auto_resolve_agents(agents_dir)

    steps = _extract_steps(plan_data)
    if not steps:
        raise PlanPromptError(
            f"Plan '{plan_id}' has no executable steps under 'workflow' or 'steps'.")

    name = plan_data.get("name") or plan_id
    description = plan_data.get("description") or ""

    lines: List[str] = []
    lines.append(f"Goal: {name}")
    if description.strip():
        lines.append("")
        lines.append(description.strip())
    if document_path:
        lines.append("")
        lines.append(f"Document: {document_path}")
    if si_document_path:
        lines.append(f"Supplementary information: {si_document_path}")
    if workspace_dir:
        lines.append(f"Workspace: {workspace_dir}")

    lines.extend([
        "",
        "Execute these steps IN ORDER. Each step must complete before issuing",
        "the next step's DelegateTask call(s). Use the DelegateTask tool to",
        "invoke each agent.",
        "",
        "Within a step, multiple replicas are issued as parallel DelegateTask",
        "calls in the SAME assistant message — do NOT serialize them.",
        "",
        "Each DelegateTask call returns a compact reference object",
        "    {\"agent_id\": ..., \"status\": ..., \"output_path\": \"<file>\",",
        "     \"content_chars\": N, \"content_preview\": \"<first 1500 chars>\"}",
        "The full worker output is written to that output_path file. When a",
        "downstream step needs upstream results, pass the upstream",
        "output_path string(s) directly — DO NOT re-emit the full content.",
        "Deterministic agents (see step rendering) auto-load these paths.",
        "",
        "─" * 60,
    ])

    parallel_groups = _group_parallel_steps(steps)
    for group in parallel_groups:
        lines.append("")
        for step in group:
            lines.extend(
                _render_step(step, template_vars, deterministic_agents,
                             auto_resolve_agents))
            lines.append("")

    lines.append("─" * 60)
    lines.append("")
    lines.append(
        "After the final step completes, return its output as your final answer.")

    return "\n".join(lines)


def _load_plan_yaml(plan_id: str, plan_dir: Optional[Path]) -> Dict[str, Any]:
    """Load and parse the plan YAML file."""
    if plan_dir is None:
        plan_dir = get_paths().project_root / _DEFAULT_PLAN_SUBDIR

    for ext in (".yaml", ".yml"):
        path = plan_dir / f"{plan_id}{ext}"
        if path.exists():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise PlanPromptError(
                    f"Failed to parse plan '{plan_id}' from {path}: {exc}") from exc
            if not isinstance(data, dict):
                raise PlanPromptError(
                    f"Plan '{plan_id}' YAML must be a mapping at the top level.")
            return data

    raise PlanPromptError(f"Plan '{plan_id}' not found under {plan_dir} (.yaml/.yml).")


def _extract_steps(plan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the plan's step list into a single ordered list of step dicts.

    Both schema variants are normalized:
      - legacy ``workflow:`` with possible ``parallel: [...]`` blocks
      - simplified ``steps:`` flat list

    Each returned step has fields:
        id, agent, description, inputs, replicas, optional, skip_if,
        parallel_with
    """
    raw_steps: List[Dict[str, Any]] = []

    if "steps" in plan_data and isinstance(plan_data["steps"], list):
        for entry in plan_data["steps"]:
            if isinstance(entry, dict):
                raw_steps.append(_normalize_step(entry))
    elif "workflow" in plan_data and isinstance(plan_data["workflow"], list):
        for entry in plan_data["workflow"]:
            if not isinstance(entry, dict):
                continue
            if "parallel" in entry and isinstance(entry["parallel"], list):
                # Mark each child with parallel_with referencing siblings.
                sibling_ids = [
                    str(child.get("step_id") or child.get("id") or "")
                    for child in entry["parallel"] if isinstance(child, dict)
                ]
                for child in entry["parallel"]:
                    if not isinstance(child, dict):
                        continue
                    normalized = _normalize_step(child)
                    own_id = normalized["id"]
                    normalized["parallel_with"] = [
                        sid for sid in sibling_ids if sid and sid != own_id
                    ]
                    raw_steps.append(normalized)
            else:
                raw_steps.append(_normalize_step(entry))

    return raw_steps


def _normalize_step(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a raw step dict from either schema into a uniform shape."""
    step_id = str(entry.get("id") or entry.get("step_id") or "").strip()
    agent_id = _normalize_agent_id(entry.get("agent") or "")
    replicas = entry.get("replicas")
    if replicas is None:
        replicas = entry.get("replicate")
    try:
        replicas = int(replicas) if replicas is not None else 1
    except (TypeError, ValueError):
        replicas = 1
    if replicas < 1:
        replicas = 1

    return {
        "id": step_id,
        "agent": agent_id,
        "description": str(entry.get("description") or "").strip(),
        "inputs": entry.get("inputs") or {},
        "replicas": replicas,
        "optional": bool(entry.get("optional", False)),
        "skip_if": entry.get("skip_if"),
        "parallel_with": list(entry.get("parallel_with") or []),
    }


def _normalize_agent_id(value: str) -> str:
    """Normalize agent IDs to dash form (matches .claude/agents/<name>/)."""
    return str(value).strip().replace("_", "-")


def _group_parallel_steps(steps: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group steps that explicitly declare they run in parallel.

    Each group is rendered as a single block in the prompt. Steps without
    ``parallel_with`` form singleton groups.
    """
    groups: List[List[Dict[str, Any]]] = []
    consumed: set = set()
    by_id = {step["id"]: step for step in steps if step.get("id")}

    for step in steps:
        sid = step.get("id")
        if sid in consumed:
            continue
        partners = [pid for pid in step.get("parallel_with", []) if pid in by_id]
        if partners:
            group = [step] + [by_id[pid] for pid in partners if pid not in consumed]
            for member in group:
                consumed.add(member["id"])
            groups.append(group)
        else:
            consumed.add(sid)
            groups.append([step])
    return groups


def _render_step(
    step: Dict[str, Any],
    template_vars: Dict[str, str],
    deterministic_agents: Set[str],
    auto_resolve_agents: Optional[Set[str]] = None,
) -> List[str]:
    """Render a single step block as prompt text."""
    lines: List[str] = []
    sid = step["id"]
    agent_id = step["agent"]
    description = step["description"]
    replicas = step["replicas"]
    is_deterministic = agent_id in deterministic_agents
    is_auto_resolve = (auto_resolve_agents is not None
                       and agent_id in auto_resolve_agents)

    header = f"Step {sid} — {description}" if description else f"Step {sid}"
    lines.append(header)

    if step["optional"]:
        skip_if = _substitute(str(step.get("skip_if") or ""), template_vars)
        if skip_if:
            lines.append(
                f"  IF the condition `{skip_if}` evaluates true, SKIP this step.")
        else:
            lines.append(
                "  This step is OPTIONAL — skip if its inputs are unavailable.")

    if replicas > 1:
        lines.append(
            f"  Issue EXACTLY {replicas} parallel DelegateTask calls in ONE assistant message:"
        )
    else:
        lines.append("  Issue ONE DelegateTask call:")

    rendered_inputs = _render_inputs(step.get("inputs") or {}, template_vars)

    if is_deterministic:
        # Deterministic agents bypass the LLM entirely. Coordinator passes
        # task_inputs (a JSON object); fields whose value is an upstream
        # output_path string (or list of output_path strings) are
        # auto-loaded by DelegateTask before invoking the underlying
        # tool. This makes fan-in steps O(N paths) in prompt size
        # instead of O(N×content).
        lines.append("  This agent is DETERMINISTIC — DelegateTask will call its tool")
        lines.append("  directly. Pass arguments via task_inputs.")
        lines.append("  For fields whose data lives in upstream worker outputs,")
        lines.append("  use the upstream output_path STRING (or list of strings)")
        lines.append("  — DelegateTask reads and parses each artifact for you.")
        lines.append("  Plain string fields (e.g. document_path) are pass-through.")
        lines.append("    DelegateTask(")
        lines.append(f'      agent_id="{agent_id}",')
        lines.append(f'      task_description="{description or sid}",')
        lines.append("      task_inputs={")
        for key, value in rendered_inputs.items():
            lines.append(f'        "{key}": <{value}>,')
        lines.append("      }")
        lines.append("    )")
    elif is_auto_resolve:
        # Auto-resolve agents are LLM-driven workers (so they keep their own
        # tool loop) but DelegateTask walks task_inputs values for upstream
        # artifact paths and mines `images[].image_path` from parsed
        # payloads, populating Task.image_paths so Agent.run() embeds the
        # actual image bytes as multimodal content. This bridges the gap
        # left when PlanTaskDispatcher (Slice 3) stopped pre-loading images
        # for vision workers.
        lines.append(
            "  This agent has AUTO_RESOLVE_ARTIFACTS — pass arguments via task_inputs.")
        lines.append(
            "  For upstream worker outputs, use the upstream output_path STRING")
        lines.append("  (e.g. analyzer's artifact path); DelegateTask will mine the")
        lines.append("  payload for `images[].image_path` and embed those images as")
        lines.append("  multimodal content. Plain strings are pass-through.")
        lines.append("    DelegateTask(")
        lines.append(f'      agent_id="{agent_id}",')
        lines.append(f'      task_description="{description or sid}",')
        lines.append("      task_inputs={")
        for key, value in rendered_inputs.items():
            lines.append(f'        "{key}": <{value}>,')
        lines.append("      }")
        lines.append("    )")
    else:
        inputs_block = _format_task_description(description, rendered_inputs)
        lines.append("    DelegateTask(")
        lines.append(f'      agent_id="{agent_id}",')
        lines.append("      task_description="
                     + _format_multiline(inputs_block, indent=8))
        lines.append("    )")

    if replicas > 1:
        lines.append(
            f"  Repeat the above call {replicas} times in the SAME assistant message.")

    return lines


def _scan_agents_with_flag(flag: str, agents_dir: Optional[Path] = None) -> Set[str]:
    """Scan agent .md frontmatters and return names where ``flag`` is true.

    Reads frontmatter only — does not import tools.py or trigger any
    side effects. Supports both flat and directory layouts.
    """
    if agents_dir is None:
        agents_dir = get_paths().project_root / _DEFAULT_AGENTS_SUBDIR
    found: Set[str] = set()
    if not agents_dir.exists():
        return found

    candidates: List[Path] = list(agents_dir.glob("*.md"))
    for child in agents_dir.iterdir():
        if child.is_dir():
            nested = child / f"{child.name}.md"
            if nested.exists():
                candidates.append(nested)

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        match = _FRONTMATTER_RE.match(text)
        if not match:
            continue
        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and bool(data.get(flag, False)):
            name = data.get("name") or path.stem
            found.add(_normalize_agent_id(str(name)))
    return found


def _scan_deterministic_agents(agents_dir: Optional[Path] = None) -> Set[str]:
    return _scan_agents_with_flag("deterministic", agents_dir)


def _scan_auto_resolve_agents(agents_dir: Optional[Path] = None) -> Set[str]:
    return _scan_agents_with_flag("auto_resolve_artifacts", agents_dir)


def _render_inputs(inputs: Dict[str, Any], template_vars: Dict[str,
                                                               str]) -> Dict[str, Any]:
    """Substitute ``{{var}}`` placeholders inside string values.

    Non-string values (lists, dicts, numbers) are passed through unchanged
    so the LLM can see structured upstream references like
    ``"(from step 1)"`` or full nested dicts.
    """
    rendered: Dict[str, Any] = {}
    for key, value in inputs.items():
        if isinstance(value, str):
            rendered[key] = _substitute(value, template_vars)
        else:
            rendered[key] = value
    return rendered


def _substitute(template: str, template_vars: Dict[str, str]) -> str:
    """Replace ``{{name}}`` placeholders with provided template variables.

    Unknown placeholders are left intact so the LLM can still see the
    intended upstream reference (e.g. ``{{step1.sections}}``).
    """
    if not template:
        return template
    result = template
    for key, value in template_vars.items():
        token = "{{" + key + "}}"
        if token in result:
            result = result.replace(token, value)
    return result


def _format_task_description(description: str, inputs: Dict[str, Any]) -> str:
    """Build the textual task_description payload for a DelegateTask call."""
    parts: List[str] = []
    if description:
        parts.append(description.strip())
    if inputs:
        parts.append("Inputs:")
        for key, value in inputs.items():
            parts.append(f"  - {key}: {value}")
    return "\n".join(parts) if parts else ""


def _format_multiline(text: str, indent: int = 0) -> str:
    """Format a possibly multi-line string as a Python-style triple-quoted block."""
    pad = " " * indent
    if "\n" not in text:
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    indented = "\n".join(f"{pad}{line}" for line in text.splitlines())
    return f'"""\n{indented}\n{pad[:max(indent - 2, 0)]}"""'
