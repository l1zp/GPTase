"""Displacement-based diagnostics for a TS optimization result.

Case-agnostic: parses the final geometry, computes per-atom displacements,
classifies CRASHED / NOT_CONVERGED / MULTI_IMAG. When the run has exactly one
imaginary frequency, the caller can pass ``compute_case_metrics`` +
``classify_single_imag`` callbacks to refine SINGLE_IMAG_WRONG / AMBIG / VALID;
otherwise the state stays at the base tier (and the caller can refine later).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

from autots_types import AutoTSProfile
from autots_types import GeneratedTSGuess
from autots_types import TSDiagnostics
from autots_types import TSState
from theozyme import extract_imaginary_freqs
from theozyme import parse_xyz_text

ComputeCaseMetricsFn = Callable[
    [AutoTSProfile, GeneratedTSGuess, dict[str, float], float],
    dict[str, float],
]
ClassifySingleImagFn = Callable[
    [tuple[dict[str, Any], ...], dict[str, float]],
    TSState,
]


def write_ts_guess(path: Path, guess: GeneratedTSGuess) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(guess.xyz_text)


def _base_state(imag_freqs: tuple[float, ...], success: bool,
                converged: bool) -> TSState | None:
    """Return the non-single-imag tier, or None if it's a single imag case."""

    if len(imag_freqs) >= 2:
        return TSState.MULTI_IMAG
    if not success and not converged:
        return TSState.NOT_CONVERGED
    if len(imag_freqs) != 1:
        return TSState.NOT_CONVERGED
    return None  # single imaginary mode — caller refines


def diagnose(
    result_payload: dict[str, Any],
    guess: GeneratedTSGuess,
    profile: AutoTSProfile,
    compute_case_metrics: ComputeCaseMetricsFn | None = None,
    classify_single_imag: ClassifySingleImagFn | None = None,
) -> TSDiagnostics:
    success = bool(result_payload.get("success"))
    data = result_payload.get("data")
    if not isinstance(data, dict):
        return TSDiagnostics(
            state=TSState.CRASHED,
            imag_freqs_cm1=(),
            max_abs_imag_cm1=0.0,
            success=success,
            converged=False,
            energy_hartree=None,
            total_displacement_angstrom=0.0,
            top_displacements=(),
            displacement_by_label={},
            case_metrics={},
            note=str(
                result_payload.get("error") or result_payload.get("message")
                or "missing data"),
        )

    imag_freqs = extract_imaginary_freqs(result_payload)
    max_abs_imag = max((abs(freq) for freq in imag_freqs), default=0.0)
    converged = bool(data.get("converged"))
    energy = data.get("energy_hartree")
    displacement_by_label: dict[str, float] = {}
    top_displacements: tuple[dict[str, Any], ...] = ()
    total_displacement = 0.0
    note: str | None = None

    final_xyz = data.get("final_geometry_xyz")
    if isinstance(final_xyz, str) and final_xyz.strip():
        try:
            final_atoms = parse_xyz_text(final_xyz)
            if len(final_atoms) != len(guess.atom_records):
                raise ValueError("final geometry atom count mismatch")
            annotated = []
            for guess_atom, (_, x, y, z) in zip(guess.atom_records, final_atoms):
                displacement = math.dist((guess_atom.x, guess_atom.y, guess_atom.z),
                                         (x, y, z))
                displacement_by_label[guess_atom.label] = displacement
                annotated.append({
                    "index": guess_atom.index,
                    "label": guess_atom.label,
                    "atom_name": guess_atom.atom_name,
                    "displacement_angstrom": round(displacement, 6),
                })
            total_displacement = sum(item["displacement_angstrom"]
                                     for item in annotated)
            top_displacements = tuple(
                sorted(annotated,
                       key=lambda item: item["displacement_angstrom"],
                       reverse=True)[:3])
        except ValueError as exc:
            note = str(exc)

    case_metrics: dict[str, float] = {}
    if compute_case_metrics is not None:
        case_metrics = compute_case_metrics(profile, guess, displacement_by_label,
                                            total_displacement)

    base = _base_state(imag_freqs, success, converged)
    if base is not None:
        state = base
    elif classify_single_imag is not None:
        state = classify_single_imag(top_displacements, case_metrics)
    else:
        state = TSState.SINGLE_IMAG_AMBIG  # caller didn't refine; default to middle tier

    return TSDiagnostics(
        state=state,
        imag_freqs_cm1=imag_freqs,
        max_abs_imag_cm1=max_abs_imag,
        success=success,
        converged=converged,
        energy_hartree=None if energy is None else float(energy),
        total_displacement_angstrom=round(total_displacement, 6),
        top_displacements=top_displacements,
        displacement_by_label=displacement_by_label,
        case_metrics=case_metrics,
        note=note,
    )
