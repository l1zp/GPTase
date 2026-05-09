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
                    "line":
                    line,
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


def extract_cluster(pdb: str,
                    chain: str,
                    ligand: str,
                    cutoff: float = 6.0,
                    protein_chain: str | None = None) -> str:
    """Extract active-site cluster around a ligand.

    Args:
        pdb: Path to input PDB.
        chain: Chain containing the ligand.
        ligand: 3-letter residue name of the ligand.
        cutoff: Distance cutoff in Angstrom.
        protein_chain: Chain containing the protein (default: same as ligand).
    """
    atoms = parse_pdb(pdb)
    prot_chain = protein_chain or chain

    lig_atoms = [
        a for a in atoms
        if a["chain"] == chain and a["resname"] == ligand and a["element"] != "H"
    ]
    if not lig_atoms:
        raise ValueError(f"Ligand '{ligand}' not found in chain '{chain}'")
    lig_coords = np.array([[a["x"], a["y"], a["z"]] for a in lig_atoms])

    close = set()
    for a in atoms:
        if (a["chain"] != prot_chain or a["record"] != "ATOM" or a["resname"] == "HOH"
                or a["element"] == "H"):
            continue
        d = np.linalg.norm(lig_coords - [a["x"], a["y"], a["z"]], axis=1).min()
        if d < cutoff:
            close.add((a["chain"], a["resseq"], a["icode"], a["resname"]))

    cluster = [
        a for a in atoms if (a["chain"] == chain and a["resname"] == ligand) or (
            a["record"] == "ATOM" and a["chain"] == prot_chain and
            (a["chain"], a["resseq"], a["icode"], a["resname"]) in close)
    ]

    out = Path(pdb).with_name(Path(pdb).stem + f"_cluster_chain{chain}.pdb")
    with open(out, "w") as f:
        for a in cluster:
            f.write(a["line"])
        f.write("END\n")

    print(f"Ligand atoms   : {len(lig_atoms)}")
    print(f"Residues found : {len(close)}")
    for ch, resseq, icode, resname in sorted(close):
        print(f"  {ch}:{resname:3s} {resseq}{icode}")
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
    prot_chain = sys.argv[5] if len(sys.argv) > 5 else None
    extract_cluster(pdb_path, chain_id, lig_code, cutoff, prot_chain)
