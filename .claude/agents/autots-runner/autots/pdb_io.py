"""Generic PDB record parsing and line-level edits.

Case-agnostic: any reaction case that consumes a cluster PDB can reuse these
helpers. Reaction-specific chemistry (bond lengths, geometry placement) stays
in the owning case module.
"""

from __future__ import annotations

import math
from pathlib import Path


def element_from_line(line: str) -> str:
    raw = line[76:78].strip() if len(line) >= 78 else ""
    if raw:
        return raw
    name = line[12:16].strip().lstrip("0123456789")
    if len(name) > 1 and name[1].islower():
        return name[:2]
    return name[:1].upper()


def parse_pdb_atoms(path: Path) -> list[dict]:
    atoms = []
    for line in path.read_text().splitlines():
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        atoms.append({
            "line": line,
            "record": line[0:6].strip(),
            "serial": int(line[6:11]),
            "name": line[12:16].strip(),
            "resname": line[17:20].strip(),
            "chain": line[21].strip(),
            "resseq": int(line[22:26]),
            "icode": line[26].strip(),
            "x": float(line[30:38]),
            "y": float(line[38:46]),
            "z": float(line[46:54]),
            "element": element_from_line(line),
        })
    return atoms


def distance(left: dict, right: dict) -> float:
    return math.dist((left["x"], left["y"], left["z"]),
                     (right["x"], right["y"], right["z"]))


def find_atom(atoms: list[dict], *, chain: str, resname: str, resseq: int,
              name: str) -> dict:
    for atom in atoms:
        if (atom["chain"] == chain and atom["resname"] == resname
                and atom["resseq"] == resseq and atom["name"] == name):
            return atom
    raise ValueError(f"Atom not found: {chain}:{resseq}:{resname}:{name}")


def replace_atom_line(line: str,
                      *,
                      name: str | None = None,
                      resname: str | None = None,
                      resseq: int | None = None,
                      x: float | None = None,
                      y: float | None = None,
                      z: float | None = None,
                      element: str | None = None) -> str:
    name = line[12:16].strip() if name is None else name
    resname = line[17:20].strip() if resname is None else resname
    chain = line[21]
    resseq = int(line[22:26]) if resseq is None else resseq
    icode = line[26]
    x = float(line[30:38]) if x is None else x
    y = float(line[38:46]) if y is None else y
    z = float(line[46:54]) if z is None else z
    element = element_from_line(line) if element is None else element
    record = line[0:6]
    serial = int(line[6:11])
    if len(name) == 4:
        atom_name = name
    elif len(element.strip()) == 1:
        atom_name = f" {name:<3}"
    else:
        atom_name = f"{name:<4}"
    return (f"{record:<6}{serial:>5d} "
            f"{atom_name:<4}"
            f"{' ':1}"
            f"{resname:>3} "
            f"{chain:1}"
            f"{resseq:>4d}"
            f"{icode or ' ':1}   "
            f"{x:>8.3f}"
            f"{y:>8.3f}"
            f"{z:>8.3f}"
            f"{1.00:>6.2f}"
            f"{0.00:>6.2f}          "
            f"{element:>2}  ")
