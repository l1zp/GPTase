"""Generic LLM proposer + deterministic fallback for autoTS.

Caller supplies the params dataclass; this module handles message assembly,
JSON extraction, dedupe, and ±step fallback scanning by introspecting the
dataclass fields. No case concept — just pure utilities.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import fields
import json
import random
import re
from typing import Any

from autots_types import AutoTSProfile
from autots_types import EvaluationRecord
from autots_types import TSState

from gptase.models.model import Model

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)


def _record_sort_key(record: EvaluationRecord) -> tuple[Any, ...]:
    imag_count = len(record.metrics.imag_freqs_cm1)
    max_abs_imag = record.metrics.max_abs_imag_cm1 if imag_count else float("inf")
    energy = (record.metrics.energy_hartree
              if record.metrics.energy_hartree is not None else float("inf"))
    if record.state == TSState.MULTI_IMAG:
        return (-int(record.state), max_abs_imag, imag_count, energy,
                record.round_index, record.phase)
    return (-int(record.state), energy, imag_count, max_abs_imag, record.round_index,
            record.phase)


def extract_json_object(text: str) -> dict[str, Any]:
    for pattern in (_JSON_BLOCK_RE, _JSON_OBJECT_RE):
        match = pattern.search(text)
        if not match:
            continue
        candidate = match.group(1)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Model response did not contain a JSON object")


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return repr(value) if isinstance(value, str) else str(value)


def render_history_table(history: list[EvaluationRecord]) -> str:
    if not history:
        return "(empty)"
    param_fields = tuple(f.name for f in fields(history[0].params))
    header = [
        "idx", "round", "phase", "state", "imags", "max_abs_imag", "energy", "hotspot"
    ] + list(param_fields)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |"
    ]
    for idx, record in enumerate(history):
        hotspot = (record.metrics.top_displacements[0]["label"]
                   if record.metrics.top_displacements else "-")
        imags = ", ".join(f"{value:.2f}"
                          for value in record.metrics.imag_freqs_cm1) or "-"
        energy = (f"{record.metrics.energy_hartree:.6f}"
                  if record.metrics.energy_hartree is not None else "-")
        param_dict = asdict(record.params)
        row = [
            str(idx),
            str(record.round_index), record.phase, record.state.name, imags,
            f"{record.metrics.max_abs_imag_cm1:.2f}", energy, hotspot
        ]
        row.extend(_format_value(param_dict.get(name)) for name in param_fields)
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _params_schema(params_cls: type) -> str:
    lines = ["{"]
    field_list = fields(params_cls)
    for i, f in enumerate(field_list):
        type_name = getattr(f.type, "__name__", str(f.type))
        comma = "," if i < len(field_list) - 1 else ""
        lines.append(f'  "{f.name}": {type_name}{comma}')
    lines.append("}")
    return "\n".join(lines)


def _best_record(history: list[EvaluationRecord]) -> EvaluationRecord:
    return sorted(history, key=_record_sort_key)[0]


def _perturbation_candidates(best_params: Any, step: float,
                             history_len: int) -> list[dict[str, Any]]:
    """Generate ordered candidate param dicts by ±step on float fields.

    Ignores str/enum fields; cases that want to cycle those can call
    ``generic_fallback`` and then merge additional candidates themselves.
    """

    base = asdict(best_params)
    candidates: list[dict[str, Any]] = []
    float_fields = [
        f.name for f in fields(best_params) if f.type in ("float", ) or f.type is float
    ]
    for name in float_fields:
        current = base.get(name)
        if not isinstance(current, (int, float)):
            continue
        for delta in (step, -step):
            bumped = dict(base)
            bumped[name] = float(current) + delta
            candidates.append(bumped)
    # Final seeded Gaussian perturbation to guarantee novelty.
    jittered = dict(base)
    jittered["perturb_seed"] = history_len
    jittered["perturb_sigma"] = max(0.02, min(0.05, step / 2))
    candidates.append(jittered)
    return candidates


def generic_fallback(history: list[EvaluationRecord], profile: AutoTSProfile,
                     params_cls: type) -> Any:
    """Deterministic next-params generator based on float-field ±step scan."""

    if not history:
        return profile.initial_guess
    best = _best_record(history).params
    seen = {record.params.dedupe_key() for record in history}
    step = profile.fallback_step
    for candidate in _perturbation_candidates(best, step, len(history)):
        try:
            proposal = params_cls.from_mapping(candidate)
        except (ValueError, TypeError, KeyError):
            continue
        if proposal.dedupe_key() not in seen:
            return proposal
    # Last resort: re-seed with Python's RNG.
    rng = random.Random(len(history) * 7919)
    base = asdict(best)
    for f in fields(best):
        if f.type is float or f.type == "float":
            base[f.name] = float(base.get(f.name, 0.0)) + rng.gauss(0.0, step)
    base["perturb_seed"] = len(history) + 1
    base["perturb_sigma"] = step
    return params_cls.from_mapping(base)


def _build_messages(history: list[EvaluationRecord], brief_text: str,
                    profile: AutoTSProfile, params_cls: type) -> list[dict[str, str]]:
    user = (
        "You are steering an automated TS-guess search.\n"
        "Choose exactly one next geometry in JSON.\n"
        "Constraints:\n"
        "- Only modify the params fields listed below.\n"
        "- Prefer unseen candidates.\n"
        "- Same state favors lower energy.\n"
        "- Consult the system prompt (brief) for reaction-specific scoring rules.\n\n"
        "Return JSON only with this schema:\n"
        f"{_params_schema(params_cls)}\n\n"
        f"Profile: {profile.profile_id}\n"
        f"History:\n{render_history_table(history)}")
    return [
        {
            "role": "system",
            "content": brief_text.strip()
        },
        {
            "role": "user",
            "content": user
        },
    ]


async def propose_via_llm(
    history: list[EvaluationRecord],
    brief_text: str,
    profile: AutoTSProfile,
    params_cls: type,
) -> tuple[Any, str]:
    """Ask the LLM for the next params; fall back to deterministic scan on any error."""

    try:
        model = Model()
        config = None
        if profile.proposal_model_name:
            config = model.default_config.model_copy(
                update={"model_name": profile.proposal_model_name})
        messages = _build_messages(history, brief_text, profile, params_cls)
        response = await model.generate(messages, config=config)
        candidate = params_cls.from_mapping(extract_json_object(response.content))
        seen = {record.params.dedupe_key() for record in history}
        if candidate.dedupe_key() in seen:
            raise ValueError("model proposed a duplicate parameter set")
        return candidate, "llm"
    except Exception:
        return generic_fallback(history, profile, params_cls), "fallback"
