"""
Add H link-atom caps to a QM cluster PDB.

Caps truncated backbone bonds so the cluster is chemically complete
before QM submission. Cap H positions are approximate — QM geometry
optimization relaxes them to correct values.

Strategy:
  N-cap: prev residue absent → H at N + normalize(N - CA) * 1.01 Å
  C-cap: next residue absent → H at C - bisect(CA→C, O→C) * 1.09 Å
         (bisect preserves sp2 geometry of peptide carbonyl)

Usage:
    python cap_cluster.py <CLUSTER_PDB> <CHAIN>

Output:
    <stem>_capped.pdb  written to same directory as input
"""
from pathlib import Path
import sys

import numpy as np


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v


def parse_pdb(path: str) -> list[dict]:
    atoms = []
    with open(path) as f:
        for line in f:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            try:
                atoms.append({
                    "line":
                    line.rstrip(),
                    "record":
                    line[0:6].strip(),
                    "serial":
                    int(line[6:11]),
                    "name":
                    line[12:16].strip(),
                    "resname":
                    line[17:20].strip(),
                    "chain":
                    line[21],
                    "resseq":
                    int(line[22:26]),
                    "icode":
                    line[26].strip(),
                    "x":
                    float(line[30:38]),
                    "y":
                    float(line[38:46]),
                    "z":
                    float(line[46:54]),
                    "element":
                    (line[76:78].strip()
                     or line[12:16].strip().lstrip("0123456789")[:1]).upper(),
                })
            except ValueError:
                pass
    return atoms


def get_bb(resseq: int, icode: str, name: str, atoms: list[dict], chain: str):
    for a in atoms:
        if (a["chain"] == chain and a["resseq"] == resseq and a["icode"] == icode
                and a["name"] == name):
            return np.array([a["x"], a["y"], a["z"]])
    return None


def make_h_line(serial: int,
                name: str,
                chain: str,
                resseq: int,
                xyz: np.ndarray,
                icode: str = "") -> str:
    return (f"HETATM{serial:5d}  {name:<3s} CAP {chain}{resseq:4d}{icode or ' '}   "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00           H  ")


def cap_cluster(cluster_pdb: str, chain: str) -> str:
    atoms = parse_pdb(cluster_pdb)
    protein_atoms = [
        a for a in atoms
        if a["record"] == "ATOM" and a["chain"] == chain and a["resname"] != "CAP"
    ]
    protein_heavy = [a for a in protein_atoms if a["element"] != "H"]
    present_set = {(a["resseq"], a["icode"]) for a in protein_heavy}
    existing_caps = {(a["chain"], a["resseq"], a["icode"], a["name"])
                     for a in atoms if a["resname"] == "CAP" and a["element"] == "H"}
    serial = max((a["serial"] for a in atoms), default=9000) + 1
    caps = []

    for resseq, icode in sorted(present_set):
        N = get_bb(resseq, icode, "N", protein_heavy, chain)
        CA = get_bb(resseq, icode, "CA", protein_heavy, chain)
        C = get_bb(resseq, icode, "C", protein_heavy, chain)
        O = get_bb(resseq, icode, "O", protein_heavy, chain)
        if N is None or CA is None or C is None:
            continue

        # N-cap: previous residue missing
        if (resseq - 1, "") not in present_set and (chain, resseq, icode,
                                                    "HN") not in existing_caps:
            h = N + normalize(N - CA) * 1.01
            caps.append(make_h_line(serial, "HN", chain, resseq, h, icode))
            serial += 1
            print(f"  N-cap {resseq}{icode} (prev {resseq-1} absent)")

        # C-cap: next residue missing
        if (resseq + 1, "") not in present_set and (chain, resseq, icode,
                                                    "HC") not in existing_caps:
            if O is not None:
                # bisect CA and O directions from C, then place H on opposite side
                h_dir = normalize(normalize(CA - C) + normalize(O - C))
                h = C - h_dir * 1.09
            else:
                h = C + normalize(C - CA) * 1.09
            caps.append(make_h_line(serial, "HC", chain, resseq, h, icode))
            serial += 1
            print(f"  C-cap {resseq}{icode} (next {resseq+1} absent)")

    out = Path(cluster_pdb).with_name(Path(cluster_pdb).stem + "_capped.pdb")
    with open(out, "w") as f:
        for a in atoms:
            f.write(a["line"] + "\n")
        for cap in caps:
            f.write(cap + "\n")
        f.write("END\n")

    print(f"\n{len(caps)} cap H atoms added")
    print(f"Total atoms : {len(atoms) + len(caps)}")
    print(f"Output      : {out}")
    return str(out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cap_cluster(sys.argv[1], sys.argv[2])
