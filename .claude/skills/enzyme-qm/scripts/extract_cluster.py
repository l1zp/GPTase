"""
Extract QM active-site cluster from a PDB file.

Usage:
    python extract_cluster.py <PDB> <CHAIN> <LIGAND_CODE> [CUTOFF]

Arguments:
    PDB          Path to input PDB file
    CHAIN        Chain ID to extract from (e.g. B)
    LIGAND_CODE  3-letter PDB ligand residue name (e.g. 3NY)
    CUTOFF       Distance cutoff in Angstrom (default: 6.0)

Output:
    <PDB_stem>_cluster_chain<CHAIN>.pdb  written to same directory as input
"""
from pathlib import Path
import sys

import numpy as np


def parse_pdb(path: str) -> list[dict]:
    atoms = []
    with open(path) as f:
        for line in f:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            try:
                atoms.append({
                    "line": line,
                    "record": line[0:6].strip(),
                    "serial": int(line[6:11]),
                    "name": line[12:16].strip(),
                    "resname": line[17:20].strip(),
                    "chain": line[21],
                    "resseq": int(line[22:26]),
                    "x": float(line[30:38]),
                    "y": float(line[38:46]),
                    "z": float(line[46:54]),
                })
            except ValueError:
                pass
    return atoms


def extract_cluster(pdb: str, chain: str, ligand: str, cutoff: float = 6.0) -> str:
    atoms = parse_pdb(pdb)

    lig_atoms = [a for a in atoms if a["chain"] == chain and a["resname"] == ligand]
    if not lig_atoms:
        raise ValueError(f"Ligand '{ligand}' not found in chain '{chain}'")
    lig_coords = np.array([[a["x"], a["y"], a["z"]] for a in lig_atoms])

    close = set()
    for a in atoms:
        if a["chain"] != chain or a["record"] != "ATOM" or a["resname"] == "HOH":
            continue
        d = np.linalg.norm(lig_coords - [a["x"], a["y"], a["z"]], axis=1).min()
        if d < cutoff:
            close.add((a["resseq"], a["resname"]))

    cluster = [
        a for a in atoms if a["chain"] == chain and (a["resname"] == ligand or (
            a["record"] == "ATOM" and (a["resseq"], a["resname"]) in close))
    ]

    out = Path(pdb).with_name(Path(pdb).stem + f"_cluster_chain{chain}.pdb")
    with open(out, "w") as f:
        for a in cluster:
            f.write(a["line"])
        f.write("END\n")

    print(f"Ligand atoms   : {len(lig_atoms)}")
    print(f"Residues found : {len(close)}")
    for resseq, resname in sorted(close):
        print(f"  {resname:3s} {resseq}")
    print(f"Total atoms    : {len(cluster)}")
    print(f"Output         : {out}")
    return str(out)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    pdb_path = sys.argv[1]
    chain_id = sys.argv[2]
    lig_code = sys.argv[3]
    cutoff = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0
    extract_cluster(pdb_path, chain_id, lig_code, cutoff)
