#!/usr/bin/env python3
"""
Pipeline Step: Extract PDB information to separate CSV.

This script creates a separate CSV file for PDB-related information:
- Extracts unique enzyme-PDB relationships
- Generates enzyme_to_pdb.csv (many-to-many relationship table)
- Generates pdb_info.csv (PDB metadata with EC numbers)

Usage:
    python pipelines/extract_pdb_info.py
    python pipelines/extract_pdb_info.py -i data/extraction/listov2025_extraction.json
    python pipelines/extract_pdb_info.py -i input.json -o output_directory
"""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb_sync


def extract_pdb_relationships(
        json_path: str) -> tuple[Dict[str, Set[str]], Set[str], Dict[str, List[bool]]]:
    """
    Extract enzyme-PDB relationships from extraction JSON.

    Returns:
        Tuple of (enzyme_to_pdbs dict, all_unique_pdbs set, enzyme_pdb_is_new dict)
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    reactions = data.get('reactions', [])
    enzyme_to_pdbs = {}
    enzyme_pdb_is_new = {}  # Maps enzyme_name to list of pdb_is_new booleans
    all_pdbs = set()

    for reaction in reactions:
        enzyme_name = reaction.get('enzyme_name', '')
        pdb_ids = reaction.get('pdb_ids', [])
        pdb_is_new = reaction.get('pdb_is_new', [])

        if enzyme_name and pdb_ids:
            enzyme_to_pdbs[enzyme_name] = set(pdb_ids)
            # Store pdb_is_new if available (ensure same length as pdb_ids)
            if pdb_is_new and len(pdb_is_new) == len(pdb_ids):
                enzyme_pdb_is_new[enzyme_name] = pdb_is_new
            else:
                # Default all to False (previous work) if not provided or mismatched
                enzyme_pdb_is_new[enzyme_name] = [False] * len(pdb_ids)
            all_pdbs.update(pdb_ids)

    return enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new


def create_enzyme_pdb_csv(enzyme_to_pdbs: Dict[str, Set[str]],
                          enzyme_pdb_is_new: Dict[str, List[bool]],
                          output_path: str) -> None:
    """
    Create enzyme_to_pdb.csv with many-to-many relationships.

    Columns:
    - enzyme_name
    - pdb_id
    - pdb_is_new (true/false boolean)
    """
    rows = []
    for enzyme_name in sorted(enzyme_to_pdbs):
        sorted_pdbs = sorted(enzyme_to_pdbs[enzyme_name])
        is_new_flags = enzyme_pdb_is_new.get(enzyme_name, [])

        for i, pdb_id in enumerate(sorted_pdbs):
            is_new = is_new_flags[i] if i < len(is_new_flags) else False
            rows.append({
                'enzyme_name': enzyme_name,
                'pdb_id': pdb_id,
                'pdb_is_new':
                str(is_new).lower()  # Convert boolean to "true" or "false"
            })

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['enzyme_name', 'pdb_id', 'pdb_is_new'])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created enzyme_to_pdb.csv: {len(rows)} relationships")


def create_pdb_info_csv(pdb_ids: Set[str], output_path: str) -> None:
    """
    Create pdb_info.csv with PDB metadata and EC numbers.

    Columns:
    - pdb_id
    - ec_numbers (pipe-delimited)
    - ec_count
    - title (PDB structure title)
    """
    print(f"Looking up EC numbers for {len(pdb_ids)} PDB IDs...")
    total = len(pdb_ids)

    rows = []
    for i, pdb_id in enumerate(sorted(pdb_ids), 1):
        try:
            result = get_ec_numbers_for_pdb_sync(pdb_id)
            ec_numbers = result.get('ec_numbers', [])

            ec_str = ', '.join(ec_numbers) if ec_numbers else 'None found'
            print(f"[{i}/{total}] {pdb_id}: {ec_str}")

            rows.append({
                'pdb_id': pdb_id,
                'ec_numbers': '|'.join(ec_numbers),
                'ec_count': len(ec_numbers),
                'title': result.get('title', '')
            })
        except Exception as e:
            print(f"[{i}/{total}] {pdb_id}: Error - {e}")
            rows.append({
                'pdb_id': pdb_id,
                'ec_numbers': '',
                'ec_count': '',
                'title': ''
            })

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f, fieldnames=['pdb_id', 'ec_numbers', 'ec_count', 'title'])
        writer.writeheader()
        writer.writerows(rows)

    successful = sum(1 for r in rows if r['ec_count'])
    print(f"\nSummary: {successful}/{total} PDB IDs have EC numbers")
    print(f"Created pdb_info.csv: {len(rows)} entries")


def main():
    parser = argparse.ArgumentParser(
        description='Extract PDB information to separate CSV files')
    parser.add_argument('-i',
                        '--input',
                        type=str,
                        default='data/extraction/listov2025_extraction.json',
                        help='Input extraction JSON file path')
    parser.add_argument(
        '-o',
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for CSV files (default: same as input file directory)')

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing {args.input}...")

    # Extract PDB relationships
    enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(args.input)

    if not enzyme_to_pdbs:
        print("No PDB IDs found in extraction JSON.")
        return

    print(f"Found {len(enzyme_to_pdbs)} enzymes with PDB IDs")
    print(f"Total unique PDB IDs: {len(all_pdbs)}\n")

    # Create CSV files
    enzyme_pdb_csv = output_dir / 'enzyme_to_pdb.csv'
    pdb_info_csv = output_dir / 'pdb_info.csv'

    create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, str(enzyme_pdb_csv))
    print()
    create_pdb_info_csv(all_pdbs, str(pdb_info_csv))

    print(f"\nPDB information extraction complete!")
    print(f"Output files:")
    print(f"  - {enzyme_pdb_csv}")
    print(f"  - {pdb_info_csv}")


if __name__ == '__main__':
    main()
