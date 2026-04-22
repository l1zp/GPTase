"""List HETATM residues (name, chain, resSeq) from a PDB file."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def iter_hetatm_residues(pdb_path: Path) -> list[tuple[str, str, str]]:
    """Return unique (chain, resName, resSeq) tuples for HETATM records.

    Parses fixed-column PDB fields per the PDB 3.3 spec:
      cols 18-20 resName, col 22 chainID, cols 23-26 resSeq.
    """
    seen: set[tuple[str, str, str]] = set()
    residues: list[tuple[str, str, str]] = []

    with pdb_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("HETATM"):
                continue
            res_name = line[17:20].strip()
            chain_id = line[21:22].strip() or "_"
            res_seq = line[22:26].strip()
            key = (chain_id, res_name, res_seq)
            if key in seen:
                continue
            seen.add(key)
            residues.append(key)

    return residues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdb", type=Path, help="Path to a .pdb file")
    parser.add_argument(
        "--include-water",
        action="store_true",
        help="Include HOH/WAT residues (excluded by default)",
    )
    args = parser.parse_args(argv)

    if not args.pdb.is_file():
        print(f"[ERROR] file not found: {args.pdb}", file=sys.stderr)
        return 1

    residues = iter_hetatm_residues(args.pdb)
    if not args.include_water:
        residues = [r for r in residues if r[1] not in {"HOH", "WAT"}]

    print(f"{'CHAIN':<6}{'RESNAME':<8}{'RESSEQ':>6}")
    for chain, name, seq in residues:
        print(f"{chain:<6}{name:<8}{seq:>6}")
    print(f"\n[INFO] {len(residues)} HETATM residues", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
