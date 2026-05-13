"""YAML-driven reaction specification for autoTS cases.

A case is now fully described by a ``reaction.yaml`` file — no Python needed.
This module parses that YAML into a :class:`Reaction` object whose methods
are drop-in replacements for the usual ``mutate_ts_guess`` /
``compute_case_metrics`` / ``classify_single_imag`` hooks.

Supported DSL blocks:

- ``params``    — one field per reaction coordinate; a frozen dataclass is
                  generated at load time (with free ``from_mapping`` /
                  ``dedupe_key`` via :class:`AutoTSParamsBase`).
- ``residues``  — named residue roles, resolved from ``profile.case_config``
                  and ``profile.chain`` via ``$var`` references.
- ``atoms``     — named atom references (``{residue: <role>, name: <PDB name
                  or $param>}``).
- ``mutations`` — per PDB-atom recipe: ``interpolate`` between a reactant
                  atom and a target (``place_along_bond`` or an atom ref),
                  plus an optional ``perpendicular_bend``.
- ``metrics``   — weighted sums of displacements, normalized by the run's
                  total displacement.
- ``classify_single_imag`` — primary-hotspot check + threshold conditions.

See ``cases/kemp/reaction.yaml`` for a worked example.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import make_dataclass
from pathlib import Path
import random
import re
from typing import Any

from autots_types import AutoTSParamsBase
from autots_types import AutoTSProfile
from autots_types import GeneratedTSGuess
from autots_types import GuessAtom
from autots_types import TSState
from builder import apply_residue_overrides
from builder import format_ts_guess
from geometry import add
from geometry import atom_label
from geometry import cross
from geometry import interpolate_atom
from geometry import length
from geometry import normalize
from geometry import scale
from geometry import vector_between
from pdb_io import find_atom
from pdb_io import parse_pdb_atoms
import yaml

_VAR_RE = re.compile(r"^\$([a-zA-Z_][a-zA-Z_0-9]*)$")
_CMP_RE = re.compile(r"^\s*(>=|<=|>|<|==|!=)\s*(-?\d+(?:\.\d+)?)\s*$")
_BASIC_TYPES: dict[str, type] = {"float": float, "int": int, "str": str, "bool": bool}

# --- Param dataclass generation --------------------------------------------


def _coerce(value: Any, py_type: type) -> Any:
    if value is None:
        return None
    if py_type is float:
        return float(value)
    if py_type is int:
        return int(value)
    if py_type is bool:
        return bool(value)
    return str(value)


def _build_params_cls(class_name: str, spec: dict[str, dict]) -> type:
    """Turn a YAML ``params`` block into a frozen AutoTSParamsBase subclass."""

    fields_spec = []
    for fname, fspec in spec.items():
        py_type = _BASIC_TYPES[str(fspec["type"])]
        default = fspec.get("default")
        fields_spec.append((fname, py_type, field(default=default)))

    def __post_init__(self):
        for fname, fspec in spec.items():
            value = getattr(self, fname)
            py_type = _BASIC_TYPES[str(fspec["type"])]
            if value is not None:
                value = _coerce(value, py_type)
            rng = fspec.get("range")
            if value is not None and py_type is float and rng is not None:
                lo, hi = float(rng[0]), float(rng[1])
                value = max(lo, min(hi, value))
            choices = fspec.get("choices")
            if choices is not None and value is not None and value not in choices:
                raise ValueError(f"{fname}={value!r} is not one of {list(choices)}")
            object.__setattr__(self, fname, value)

    return make_dataclass(
        class_name,
        fields_spec,
        bases=(AutoTSParamsBase, ),
        namespace={"__post_init__": __post_init__},
        frozen=True,
    )


# --- Reference resolution ---------------------------------------------------


def _resolve_var(value: Any, scope: dict[str, Any]) -> Any:
    """Replace ``$name`` strings by ``scope[name]``; pass other values through."""

    if not isinstance(value, str):
        return value
    m = _VAR_RE.match(value)
    if not m:
        return value
    key = m.group(1)
    if key not in scope:
        raise KeyError(f"${key} not found in scope (available: {sorted(scope)})")
    return scope[key]


def _scope_for_profile(profile: AutoTSProfile) -> dict[str, Any]:
    scope = dict(profile.case_config or {})
    scope["chain"] = profile.chain
    return scope


def _resolve_residues(residues_spec: dict[str, dict],
                      profile: AutoTSProfile) -> dict[str, dict[str, Any]]:
    scope = _scope_for_profile(profile)
    resolved: dict[str, dict[str, Any]] = {}
    for role, residue_spec in residues_spec.items():
        resolved[role] = {
            "chain": str(_resolve_var(residue_spec["chain"], scope)),
            "resname": str(_resolve_var(residue_spec["resname"], scope)),
            "resseq": int(_resolve_var(residue_spec["resseq"], scope)),
        }
    return resolved


def _resolve_atoms(
    atoms_spec: dict[str, dict],
    residues: dict[str, dict[str, Any]],
    cluster_atoms: list[dict[str, Any]],
    params: Any,
) -> dict[str, dict[str, Any]]:
    param_scope = {f: getattr(params, f) for f in params.__dataclass_fields__}
    resolved: dict[str, dict[str, Any]] = {}
    for key, spec in atoms_spec.items():
        role = spec["residue"]
        if role not in residues:
            raise KeyError(f"atoms[{key}] references unknown residue role {role!r}")
        residue = residues[role]
        atom_name = str(_resolve_var(spec["name"], param_scope))
        resolved[key] = find_atom(cluster_atoms,
                                  chain=residue["chain"],
                                  resname=residue["resname"],
                                  resseq=residue["resseq"],
                                  name=atom_name)
    return resolved


# --- Target / mutation evaluation ------------------------------------------


def _xyz(atom: dict[str, Any]) -> tuple[float, float, float]:
    return (atom["x"], atom["y"], atom["z"])


def _vec_from_pair(
        pair: list[str],
        resolved_atoms: dict[str, dict[str, Any]]) -> tuple[float, float, float]:
    """Return (to - from) from a [from_key, to_key] list."""

    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError(f"vector spec must be [from, to], got {pair!r}")
    a, b = resolved_atoms[pair[0]], resolved_atoms[pair[1]]
    return vector_between(a, b)


def _eval_target(
        spec: dict[str, Any],
        resolved_atoms: dict[str, dict[str, Any]]) -> tuple[float, float, float]:
    if "place_along_bond" in spec:
        sub = spec["place_along_bond"]
        anchor = resolved_atoms[sub["anchor"]]
        direction = normalize(_vec_from_pair(sub["direction"], resolved_atoms))
        distance = float(sub["distance"])
        return add(_xyz(anchor), scale(direction, distance))
    if "atom" in spec:
        return _xyz(resolved_atoms[spec["atom"]])
    raise ValueError(f"Unknown target spec: {spec!r}")


def _eval_perpendicular_bend(
    base_xyz: tuple[float, float, float],
    spec: dict[str, Any],
    resolved_atoms: dict[str, dict[str, Any]],
    magnitude: float,
) -> tuple[float, float, float]:
    if magnitude == 0.0:
        return base_xyz
    axis = normalize(_vec_from_pair(spec["axis"], resolved_atoms))
    plane_hint = _vec_from_pair(spec["plane_hint"], resolved_atoms)
    normal = cross(axis, plane_hint)
    if length(normal) < 1e-8 and "fallback_plane_hint" in spec:
        plane_hint = _vec_from_pair(spec["fallback_plane_hint"], resolved_atoms)
        normal = cross(axis, plane_hint)
    bend_direction = normalize(cross(normal, axis))
    if length(bend_direction) < 1e-8:
        return base_xyz
    return add(base_xyz, scale(bend_direction, magnitude))


def _apply_mutation(
    spec: dict[str, Any],
    resolved_atoms: dict[str, dict[str, Any]],
    params: Any,
) -> tuple[float, float, float]:
    interp = spec.get("interpolate")
    if not interp:
        raise ValueError(f"mutation must contain `interpolate`: {spec!r}")
    frac = float(
        _resolve_var(interp["fraction"],
                     {f: getattr(params, f)
                      for f in params.__dataclass_fields__}))
    target_xyz = _eval_target(interp["to"], resolved_atoms)
    base_xyz = interpolate_atom(resolved_atoms[interp["from"]], target_xyz, frac)
    bend = spec.get("perpendicular_bend")
    if bend is None:
        return base_xyz
    magnitude = float(
        _resolve_var(bend["magnitude"],
                     {f: getattr(params, f)
                      for f in params.__dataclass_fields__}))
    return _eval_perpendicular_bend(base_xyz, bend, resolved_atoms, magnitude)


# --- Metric evaluation ------------------------------------------------------


def _atom_weight(entry: Any, atom_displacements: dict[str, float]) -> float:
    """Entry is either an atom key (str) or {reduce_op: [keys]}."""

    if isinstance(entry, str):
        return atom_displacements.get(entry, 0.0)
    if isinstance(entry, dict):
        for op in ("max", "sum", "min"):
            if op in entry:
                values = [atom_displacements.get(k, 0.0) for k in entry[op]]
                if not values:
                    return 0.0
                return {"max": max, "min": min, "sum": sum}[op](values)
    raise ValueError(f"metric atom entry must be str or reduce dict: {entry!r}")


# --- Classify evaluation ---------------------------------------------------


def _eval_condition(condition: str, value: float) -> bool:
    m = _CMP_RE.match(str(condition))
    if not m:
        raise ValueError(f"invalid comparison {condition!r} (expected e.g. '>= 0.30')")
    op, threshold = m.group(1), float(m.group(2))
    return {
        ">=": value >= threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        "<": value < threshold,
        "==": value == threshold,
        "!=": value != threshold,
    }[op]


# --- Reaction bundle --------------------------------------------------------


@dataclass(frozen=True)
class Reaction:
    name: str
    description: str
    params_cls: type
    spec: dict[str, Any]

    def mutate_ts_guess(self, profile: AutoTSProfile, params: Any) -> GeneratedTSGuess:
        residues = _resolve_residues(self.spec["residues"], profile)
        atoms = parse_pdb_atoms(profile.cluster_path)
        if profile.include_residues:
            include = set(profile.include_residues)
            atoms = [
                a for a in atoms if (a["chain"], a["resname"], a["resseq"]) in include
            ]
            if not atoms:
                raise ValueError(
                    f"No atoms matched include_residues for {profile.profile_id}")
        resolved_atoms = _resolve_atoms(self.spec["atoms"], residues, atoms, params)

        overrides: dict[str, tuple[float, float, float]] = {}
        for atom_name, mut_spec in self.spec.get("mutations", {}).items():
            overrides[atom_name] = _apply_mutation(mut_spec, resolved_atoms, params)

        # Apply override via builder helper. The ligand residue for overrides
        # is the residue of the first mutated atom's owner in the spec.
        # Assume all mutated atoms live in the same residue; otherwise the
        # case should express them explicitly per-residue (future extension).
        first_mut_name = next(iter(self.spec.get("mutations", {})))
        owning_role = self._owning_role(first_mut_name, resolved_atoms)
        owning_residue = residues[owning_role]

        perturb_seed = getattr(params, "perturb_seed", None)
        perturb_sigma = float(getattr(params, "perturb_sigma", 0.0) or 0.0)
        records = apply_residue_overrides(
            atoms,
            overrides,
            chain=owning_residue["chain"],
            resname=owning_residue["resname"],
            resseq=owning_residue["resseq"],
            perturb_seed=perturb_seed,
            perturb_sigma=perturb_sigma,
        )
        comment = self._comment(profile, params)
        return format_ts_guess(params, records, comment=comment)

    def _owning_role(self, atom_name: str, resolved_atoms: dict[str, dict[str,
                                                                          Any]]) -> str:
        # Find which role the mutated atom name belongs to by looking at
        # `atoms` spec entries whose PDB name matches and returning the role.
        atoms_spec = self.spec["atoms"]
        for key, spec in atoms_spec.items():
            if resolved_atoms.get(key, {}).get("name") == atom_name:
                return str(spec["residue"])
        raise KeyError(f"cannot determine residue role for mutated atom {atom_name!r}")

    def _comment(self, profile: AutoTSProfile, params: Any) -> str:
        kv = " ".join(f"{f}={getattr(params, f)}" for f in params.__dataclass_fields__
                      if not f.startswith("perturb_"))
        return f"autoTS {profile.profile_id} {kv}"

    def compute_case_metrics(
        self,
        profile: AutoTSProfile,
        guess: GeneratedTSGuess,
        displacement_by_label: dict[str, float],
        total_displacement: float,
    ) -> dict[str, float]:
        metrics_spec = self.spec.get("metrics") or {}
        if not metrics_spec:
            return {}

        # Build {atom_key: displacement} by looking up each resolved atom's label.
        residues = _resolve_residues(self.spec["residues"], profile)
        label_lookup = {a.label: a for a in guess.atom_records}
        atom_disp: dict[str, float] = {}
        params_like = guess.params
        atoms = parse_pdb_atoms(profile.cluster_path)
        if profile.include_residues:
            include = set(profile.include_residues)
            atoms = [
                a for a in atoms if (a["chain"], a["resname"], a["resseq"]) in include
            ]
        resolved_atoms = _resolve_atoms(self.spec["atoms"], residues, atoms,
                                        params_like)
        for key, atom in resolved_atoms.items():
            label = atom_label(atom)
            atom_disp[key] = max(atom_disp.get(key, 0.0),
                                 displacement_by_label.get(label, 0.0))

        denom = total_displacement or 1.0
        out: dict[str, float] = {}
        for name, mspec in metrics_spec.items():
            raw = sum(_atom_weight(entry, atom_disp) for entry in mspec["atoms"])
            if mspec.get("normalize_by") == "total_displacement":
                raw = raw / denom
            out[name] = round(raw, 6)
        return out

    def classify_single_imag(
        self,
        top_displacements: tuple[dict[str, Any], ...],
        case_metrics: dict[str, float],
    ) -> TSState:
        cls_spec = self.spec.get("classify_single_imag")
        if not cls_spec:
            return TSState.SINGLE_IMAG_AMBIG
        primary = (top_displacements[0]["atom_name"] if top_displacements else None)
        hotspots = set(cls_spec.get("primary_hotspot_atom_names") or [])
        if hotspots and primary not in hotspots:
            return TSState.SINGLE_IMAG_WRONG
        for metric_name, cond in (cls_spec.get("valid_when") or {}).items():
            if not _eval_condition(cond, case_metrics.get(metric_name, 0.0)):
                return TSState.SINGLE_IMAG_AMBIG
        return TSState.VALID


def load_reaction(yaml_path: str | Path) -> Reaction:
    raw = yaml.safe_load(Path(yaml_path).read_text()) or {}
    params_cls = _build_params_cls(
        class_name=f"{raw.get('name', 'reaction')}Params".replace("-", "_"),
        spec=raw.get("params") or {},
    )
    return Reaction(
        name=str(raw.get("name",
                         Path(yaml_path).stem)),
        description=str(raw.get("description", "")).strip(),
        params_cls=params_cls,
        spec=raw,
    )
