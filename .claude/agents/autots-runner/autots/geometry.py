"""Pure 3D-geometry helpers shared by autoTS harness and case plugins."""

from __future__ import annotations

import math
from typing import Any

Vec3 = tuple[float, float, float]


def atom_xyz(atom: dict[str, Any] | Vec3) -> Vec3:
    if isinstance(atom, dict):
        return (atom["x"], atom["y"], atom["z"])
    return atom


def atom_label(atom: dict[str, Any]) -> str:
    return f"{atom['chain']}:{atom['resseq']}:{atom['resname']}:{atom['name']}"


def interpolate_atom(
    reactant_atom: dict[str, Any],
    target_xyz: Vec3,
    frac: float,
) -> Vec3:
    return (
        reactant_atom["x"] + (target_xyz[0] - reactant_atom["x"]) * frac,
        reactant_atom["y"] + (target_xyz[1] - reactant_atom["y"]) * frac,
        reactant_atom["z"] + (target_xyz[2] - reactant_atom["z"]) * frac,
    )


def vector_between(left: dict[str, Any] | Vec3, right: dict[str, Any] | Vec3) -> Vec3:
    lx, ly, lz = atom_xyz(left)
    rx, ry, rz = atom_xyz(right)
    return (rx - lx, ry - ly, rz - lz)


def cross(left: Vec3, right: Vec3) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def length(vector: Vec3) -> float:
    return math.sqrt(sum(c * c for c in vector))


def normalize(vector: Vec3) -> Vec3:
    norm = length(vector)
    if norm == 0.0:
        return (0.0, 0.0, 0.0)
    return (vector[0] / norm, vector[1] / norm, vector[2] / norm)


def add(left: Vec3, right: Vec3) -> Vec3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def scale(vector: Vec3, factor: float) -> Vec3:
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)
