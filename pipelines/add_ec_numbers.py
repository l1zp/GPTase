#!/usr/bin/env python3
"""
Pipeline Step 4: Add EC numbers from PDB IDs.

This script:
1. Reads CSV with PDB IDs from previous pipeline step
2. Queries RCSB PDB database to retrieve EC numbers
3. Adds EC numbers to the CSV
4. Handles multiple EC numbers per enzyme and errors gracefully

Usage:
    python pipelines/add_ec_numbers.py
    python pipelines/add_ec_numbers.py -i data/extraction/listov2025_extraction_with_mutations.csv
    python pipelines/add_ec_numbers.py -i input.csv -o output.csv
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Dict, Any, Set
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb_sync


def extract_pdb_ids_from_csv(csv_path: str) -> Dict[str, List[str]]:
    """
    Extract all unique PDB IDs from CSV file.

    Returns a dict mapping enzyme_name to list of PDB IDs.
    """
    enzyme_pdb_map = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            enzyme_name = row.get('enzyme_name', '')
            pdb_ids_str = row.get('pdb_ids', '')

            if enzyme_name and pdb_ids_str:
                # Parse PDB IDs (comma-separated in CSV)
                pdb_ids = [pdb.strip() for pdb in pdb_ids_str.split(',') if pdb.strip()]
                if pdb_ids:
                    enzyme_pdb_map[enzyme_name] = pdb_ids

    return enzyme_pdb_map


def lookup_ec_numbers(pdb_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Look up EC numbers for multiple PDB IDs.

    Returns dict mapping PDB ID to lookup result.
    """
    results = {}
    unique_pdbs = set(pdb_ids)

    print(f"🔍 Looking up EC numbers for {len(unique_pdbs)} unique PDB IDs...")

    for i, pdb_id in enumerate(unique_pdbs, 1):
        try:
            result = get_ec_numbers_for_pdb_sync(pdb_id)
            results[pdb_id] = result

            ec_numbers = result.get('ec_numbers', [])
            if ec_numbers:
                print(f"   [{i}/{len(unique_pdbs)}] {pdb_id} → {', '.join(ec_numbers)}")
            else:
                print(f"   [{i}/{len(unique_pdbs)}] {pdb_id} → No EC numbers found")
        except Exception as e:
            print(f"   [{i}/{len(unique_pdbs)}] {pdb_id} → Error: {e}")
            results[pdb_id] = {
                'pdb_id': pdb_id,
                'ec_numbers': [],
                'errors': [str(e)]
            }

    return results


def add_ec_numbers_to_csv(
    input_csv: str,
    output_csv: str,
    pdb_ec_results: Dict[str, Dict[str, Any]]
) -> None:
    """
    Add EC numbers to CSV based on PDB ID lookups.

    Adds new columns:
    - ec_numbers: Pipe-delimited list of EC numbers
    - ec_count: Number of EC numbers found
    """
    with open(input_csv, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames

        # Add new columns
        new_fieldnames = fieldnames + ['ec_numbers', 'ec_count']

        rows = list(reader)

    with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=new_fieldnames)
        writer.writeheader()

        for row in rows:
            pdb_ids_str = row.get('pdb_ids', '')
            ec_numbers_list = []
            errors_list = []

            if pdb_ids_str:
                # Look up EC numbers for each PDB ID
                for pdb_id in pdb_ids_str.split(','):
                    pdb_id = pdb_id.strip()
                    if pdb_id and pdb_id in pdb_ec_results:
                        result = pdb_ec_results[pdb_id]
                        ec_numbers_list.extend(result.get('ec_numbers', []))
                        errors_list.extend(result.get('errors', []))

            # Remove duplicates while preserving order
            seen = set()
            unique_ec = []
            for ec in ec_numbers_list:
                if ec not in seen:
                    seen.add(ec)
                    unique_ec.append(ec)

            # Add new columns
            row['ec_numbers'] = '|'.join(unique_ec) if unique_ec else ''
            row['ec_count'] = len(unique_ec) if unique_ec else ''

            writer.writerow(row)

            if errors_list:
                print(f"⚠️  {row.get('enzyme_name', 'Unknown')}: {len(errors_list)} lookup error(s)")


def main():
    parser = argparse.ArgumentParser(
        description='Add EC numbers to CSV based on PDB IDs'
    )
    parser.add_argument(
        '-i', '--input',
        type=str,
        default='data/extraction/listov2025_extraction_with_mutations.csv',
        help='Input CSV file path (output from Step 3)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: input_with_ec.csv)'
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {args.input}")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.stem) + '_with_ec.csv'

    print(f"🔄 Processing {args.input}...")

    # Extract PDB IDs
    enzyme_pdb_map = extract_pdb_ids_from_csv(args.input)

    if not enzyme_pdb_map:
        print("⚠️  No PDB IDs found in CSV file.")
        print("   Creating output file without EC numbers...")

        # Just copy input to output with empty EC columns
        with open(args.input, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            new_fieldnames = fieldnames + ['ec_numbers', 'ec_count']
            rows = list(reader)

        with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=new_fieldnames)
            writer.writeheader()
            for row in rows:
                row['ec_numbers'] = ''
                row['ec_count'] = ''
                writer.writerow(row)

        print(f"✅ Created {output_path} (no PDB IDs found)")
        return

    # Collect all unique PDB IDs
    all_pdb_ids = []
    for pdb_ids in enzyme_pdb_map.values():
        all_pdb_ids.extend(pdb_ids)

    print(f"📊 Found {len(enzyme_pdb_map)} enzymes with PDB IDs")
    print(f"   Total PDB IDs: {len(all_pdb_ids)}")

    # Look up EC numbers
    pdb_ec_results = lookup_ec_numbers(all_pdb_ids)

    # Count successful lookups
    successful = sum(1 for r in pdb_ec_results.values() if r.get('ec_numbers'))
    print(f"\n📈 Summary: {successful}/{len(pdb_ec_results)} PDB IDs had EC numbers")

    # Add EC numbers to CSV
    add_ec_numbers_to_csv(args.input, output_path, pdb_ec_results)

    print(f"\n✅ Added EC numbers to CSV: {output_path}")
    print("\n✅ Pipeline step complete!")


if __name__ == '__main__':
    main()
