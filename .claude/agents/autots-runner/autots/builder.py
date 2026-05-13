"""High-level guess-building helpers.

A case's ``mutate_ts_guess`` usually ends in the same boilerplate: walk the
cluster, override a handful of atoms' coordinates, optionally perturb them,
then format the XYZ text. These two helpers absorb that so the case module
only has to compute the new coordinates.
"""

from __future__ import annotations

import random
from typing import Any

from autots_types import GeneratedTSGuess
from autots_types import GuessAtom
from geometry import atom_label


def apply_residue_overrides(
    atoms: list[dict[str, Any]],
    overrides: dict[str, tuple[float, float, float]],
    *,
    chain: str,
    resname: str,
    resseq: int,
    perturb_seed: int | None = None,
    perturb_sigma: float = 0.0,
) -> list[GuessAtom]:
    """Replace coords of atoms matching (chain, resname, resseq).

    ``overrides`` maps PDB atom name -> new (x, y, z). Atoms not in the map
    keep their cluster coords. If ``perturb_sigma > 0`` and ``perturb_seed``
    is given, the overridden atoms get an additional Gaussian jitter.
    """

    effective = dict(overrides)
    if perturb_sigma > 0.0 and perturb_seed is not None:
        rng = random.Random(perturb_seed)
        effective = {
            name: tuple(c + rng.gauss(0.0, perturb_sigma) for c in xyz)
            for name, xyz in effective.items()
        }

    records: list[GuessAtom] = []
    for index, atom in enumerate(atoms):
        is_target = (atom["chain"] == chain and atom["resname"] == resname
                     and atom["resseq"] == resseq and atom["name"] in effective)
        coords = effective[atom["name"]] if is_target else (atom["x"], atom["y"],
                                                            atom["z"])
        records.append(
            GuessAtom(index=index,
                      element=atom["element"],
                      x=float(coords[0]),
                      y=float(coords[1]),
                      z=float(coords[2]),
                      atom_name=str(atom["name"]),
                      label=atom_label(atom)))
    return records


def format_ts_guess(
    params: Any,
    atom_records: list[GuessAtom],
    *,
    comment: str,
    extra: dict[str, Any] | None = None,
) -> GeneratedTSGuess:
    """Assemble a ``GeneratedTSGuess`` from records with a standard XYZ layout."""

    lines = [str(len(atom_records)), comment]
    lines.extend(f"{r.element:<2s} {r.x: .8f} {r.y: .8f} {r.z: .8f}"
                 for r in atom_records)
    return GeneratedTSGuess(
        params=params,
        xyz_text="\n".join(lines) + "\n",
        atom_records=tuple(atom_records),
        extra=dict(extra or {}),
    )
