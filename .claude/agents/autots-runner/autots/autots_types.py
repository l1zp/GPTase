"""Case-agnostic dataclasses for autoTS.

The harness exposes utilities (profile loader, QM subprocess, base diagnose,
LLM proposer) as plain functions. Cases import and compose them in their own
``run.py``; the harness never discovers or invokes cases.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from enum import IntEnum
from pathlib import Path
from typing import Any


class TSState(IntEnum):
    CRASHED = 0
    NOT_CONVERGED = 1
    MULTI_IMAG = 2
    SINGLE_IMAG_WRONG = 3
    SINGLE_IMAG_AMBIG = 4
    VALID = 5


class AutoTSParamsBase:
    """Mixin for case parameter dataclasses.

    Provides a generic ``from_mapping`` (uses dataclass defaults, coerces
    empty-string/None into None) and ``dedupe_key`` (rounds floats to 4 digits).
    Subclasses may override either if they need reaction-specific coercion.
    """

    @classmethod
    def from_mapping(cls, data: dict[str, Any]):
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if value in (None, ""):
                kwargs[f.name] = None
                continue
            kwargs[f.name] = value
        return cls(**kwargs)

    def dedupe_key(self) -> tuple[Any, ...]:
        values: list[Any] = []
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, float):
                v = round(v, 4)
            values.append(v)
        return tuple(values)


@dataclass(frozen=True)
class TheozymeMode:
    label: str
    method: str
    basis: str
    max_cycles: int
    timeout_seconds: int
    xc: str | None = None
    use_gpu: bool = True
    pal: int = 8
    algo: str = "rsprfo"
    hessian_init: str = "lindh"
    hessian_recalc: int = 0
    coord_type: str = "redund"

    @classmethod
    def from_mapping(cls, label: str, data: dict[str, Any]) -> "TheozymeMode":
        xc_value = data.get("xc")
        return cls(
            label=label,
            method=str(data["method"]),
            basis=str(data["basis"]),
            max_cycles=int(data["max_cycles"]),
            timeout_seconds=int(data.get("timeout_seconds", 180)),
            xc=str(xc_value) if xc_value is not None else None,
            use_gpu=bool(data.get("use_gpu", True)),
            pal=int(data.get("pal", 8)),
            algo=str(data.get("algo", "rsprfo")),
            hessian_init=str(data.get("hessian_init", "lindh")),
            hessian_recalc=int(data.get("hessian_recalc", 0)),
            coord_type=str(data.get("coord_type", "redund")),
        )


@dataclass(frozen=True)
class AutoTSProfile:
    profile_id: str
    cluster_path: Path
    output_root: Path
    chain: str
    charge: int
    mult: int
    cheap_mode: TheozymeMode
    full_mode: TheozymeMode
    initial_guess: Any
    theozyme_server: str
    theozyme_pythonpath: Path
    include_residues: tuple[tuple[str, str, int], ...] = ()
    fallback_step: float = 0.10
    proposal_model_name: str | None = None
    case_config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GuessAtom:
    index: int
    element: str
    x: float
    y: float
    z: float
    atom_name: str
    label: str


@dataclass(frozen=True)
class GeneratedTSGuess:
    params: Any
    xyz_text: str
    atom_records: tuple[GuessAtom, ...]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TSDiagnostics:
    state: TSState
    imag_freqs_cm1: tuple[float, ...]
    max_abs_imag_cm1: float
    success: bool
    converged: bool
    energy_hartree: float | None
    total_displacement_angstrom: float
    top_displacements: tuple[dict[str, Any], ...]
    displacement_by_label: dict[str, float]
    case_metrics: dict[str, float] = field(default_factory=dict)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.name
        return payload


@dataclass(frozen=True)
class EvaluationRecord:
    round_index: int
    phase: str
    params: Any
    guess_path: Path
    result_path: Path
    state: TSState
    metrics: TSDiagnostics
    proposal_source: str
