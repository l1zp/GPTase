#!/usr/bin/env python3
"""
Pipeline Step: Combine reaction, mutation, and PDB data into a comprehensive CSV.

This script combines:
1. Reaction data from extraction JSON/CSV (kinetics, conditions)
2. Mutation data from image analysis CSV (position-specific mutations)
3. PDB information (PDB IDs, sequences, EC numbers)

Usage:
    python pipelines/combine_datasets.py
    python pipelines/combine_datasets.py -i data/extraction/listov2025_extraction.json
    python pipelines/combine_datasets.py --mutations data/image_analysis_extracted_tables.csv
"""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set


def parse_mutations_from_image_csv(csv_path: str) -> Dict[str, Dict[str, str]]:
    """
    Parse mutation data from image analysis CSV.

    The CSV format has columns like:
    - Variant (enzyme name, e.g., Des27.2)
    - Position54, Position84, Position86, etc. (mutation at that position)

    Args:
        csv_path: Path to image analysis CSV file

    Returns:
        Dictionary mapping enzyme_name -> {position: amino_acid}
    """
    mutations_data = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        # Skip comment lines (starting with #)
        lines = []
        for line in f:
            if not line.strip().startswith('#'):
                lines.append(line)

        # Parse the remaining as CSV
        reader = csv.DictReader(lines)
        for row in reader:
            variant = row.get('Variant', '')
            if not variant or variant.startswith('#'):
                continue

            # Extract enzyme name (handle formats like "Des27.2")
            enzyme_name = variant.strip()

            # Extract position mutations
            position_muts = {}
            for key, value in row.items():
                if key.startswith('Position') and value:
                    # Extract position number (e.g., "Position54" -> 54)
                    match = re.search(r'Position(\d+)', key)
                    if match:
                        position = match.group(1)
                        position_muts[position] = value.strip()

            if position_muts:
                mutations_data[enzyme_name] = position_muts

    return mutations_data


def load_pdb_info(pdb_info_csv: str) -> Dict[str, Dict[str, Any]]:
    """
    Load PDB information from CSV.

    Args:
        pdb_info_csv: Path to pdb_info.csv

    Returns:
        Dictionary mapping pdb_id -> info dict
    """
    pdb_info = {}

    with open(pdb_info_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdb_id = row.get('pdb_id', '')
            if pdb_id:
                pdb_info[pdb_id] = {
                    'ec_numbers': row.get('ec_numbers', ''),
                    'ec_count': row.get('ec_count', ''),
                    'sequence': row.get('sequence', ''),
                    'sequence_length': row.get('sequence_length', ''),
                }

    return pdb_info


def load_enzyme_to_pdb(enzyme_pdb_csv: str) -> Dict[str, List[str]]:
    """
    Load enzyme to PDB mappings.

    Args:
        enzyme_pdb_csv: Path to enzyme_to_pdb.csv

    Returns:
        Dictionary mapping enzyme_name -> list of pdb_ids
    """
    enzyme_to_pdbs = defaultdict(list)

    with open(enzyme_pdb_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            enzyme_name = row.get('enzyme_name', '')
            pdb_id = row.get('pdb_id', '')
            if enzyme_name and pdb_id:
                enzyme_to_pdbs[enzyme_name].append(pdb_id)

    # Sort PDB IDs for each enzyme
    for enzyme_name in enzyme_to_pdbs:
        enzyme_to_pdbs[enzyme_name].sort()

    return dict(enzyme_to_pdbs)


def format_mutations_string(mutations: Dict[str, str],
                            format_type: str = 'standard') -> str:
    """
    Format mutations dict into a string.

    Args:
        mutations: Dict of {position: amino_acid}
        format_type: 'standard' for "A54V" style, 'list' for "A54V,B86Y"

    Returns:
        Formatted mutations string
    """
    if not mutations:
        return ''

    # Sort by position number
    sorted_items = sorted(mutations.items(), key=lambda x: int(x[0]))

    if format_type == 'standard':
        # Format as "A54V,B86Y" (wild_type + position + mutant)
        # Since we only have the mutant amino acid from image analysis,
        # we'll format as "54A,86B" (position + mutant)
        return ','.join(f'{pos}{aa}' for pos, aa in sorted_items)
    else:
        return ','.join(f'{pos}{aa}' for pos, aa in sorted_items)


def combine_data(extraction_json: str,
                 mutations_data: Dict[str, Dict[str, str]],
                 enzyme_to_pdbs: Dict[str, List[str]],
                 pdb_info: Dict[str, Dict[str, Any]],
                 include_sequence: bool = False) -> List[Dict[str, Any]]:
    """
    Combine all data sources into comprehensive records.

    Args:
        extraction_json: Path to extraction JSON file
        mutations_data: Enzyme mutations from image analysis
        enzyme_to_pdbs: Enzyme to PDB mappings
        pdb_info: PDB information
        include_sequence: Whether to include full sequence in output

    Returns:
        List of combined records
    """
    with open(extraction_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    reactions = data.get('reactions', [])
    combined = []

    for reaction in reactions:
        enzyme_name = reaction.get('enzyme_name', '')
        record = {
            'enzyme_name': enzyme_name,
            'substrates': ', '.join(reaction.get('substrates', [])),
            'products': ', '.join(reaction.get('products', [])),
            'citations': ', '.join(reaction.get('citations', [])),
        }

        # Add conditions
        conditions = reaction.get('conditions', {})
        record.update({
            'temperature': conditions.get('temperature') or '',
            'pH': conditions.get('pH') or '',
            'buffer': conditions.get('buffer') or '',
            'time': conditions.get('time') or '',
            'notes': conditions.get('notes') or '',
        })

        # Add kinetics
        kinetics = reaction.get('kinetics', {})
        record.update({
            'Km': kinetics.get('Km') or '',
            'Km_unit': kinetics.get('Km_unit', ''),
            'Vmax': kinetics.get('Vmax') or '',
            'Vmax_unit': kinetics.get('Vmax_unit', ''),
            'kcat': kinetics.get('kcat') or '',
            'kcat_unit': kinetics.get('kcat_unit', ''),
            'kcat_over_KM': kinetics.get('kcat_over_KM') or '',
            'kcat_over_KM_unit': kinetics.get('kcat_over_KM_unit', ''),
            'Tm': kinetics.get('Tm') or '',
            'Tm_unit': kinetics.get('Tm_unit', ''),
            'yield_percent': reaction.get('yield_percent') or '',
        })

        # Add mutation data from image analysis
        if enzyme_name in mutations_data:
            record['mutations'] = format_mutations_string(mutations_data[enzyme_name])
            # Count number of mutations
            record['mutation_count'] = len(mutations_data[enzyme_name])
        else:
            record['mutations'] = ''
            record['mutation_count'] = 0

        # Add PDB IDs
        if enzyme_name in enzyme_to_pdbs:
            pdb_ids = enzyme_to_pdbs[enzyme_name]
            record['pdb_ids'] = ', '.join(pdb_ids)

            # Add EC numbers (pipe-delimited from all PDBs)
            all_ec = set()
            for pdb_id in pdb_ids:
                if pdb_id in pdb_info:
                    ec_str = pdb_info[pdb_id].get('ec_numbers', '')
                    if ec_str:
                        all_ec.update(ec_str.split('|'))
            record['ec_numbers'] = '|'.join(sorted(all_ec))

            # Add sequence if requested (use first PDB's sequence)
            if include_sequence and pdb_ids:
                first_pdb = pdb_ids[0]
                if first_pdb in pdb_info:
                    record['sequence'] = pdb_info[first_pdb].get('sequence', '')
                    record['sequence_length'] = pdb_info[first_pdb].get(
                        'sequence_length', '')
        else:
            record['pdb_ids'] = ''
            record['ec_numbers'] = ''
            if include_sequence:
                record['sequence'] = ''
                record['sequence_length'] = ''

        combined.append(record)

    return combined


def main():
    parser = argparse.ArgumentParser(
        description='Combine reaction, mutation, and PDB data',
        epilog='Example:\n'
        '  python pipelines/combine_datasets.py\n'
        '  python pipelines/combine_datasets.py --include-sequence',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i',
                        '--input',
                        type=str,
                        default='data/extraction/listov2025_extraction.json',
                        help='Input extraction JSON file path')
    parser.add_argument('--mutations',
                        type=str,
                        default='data/image_analysis_extracted_tables.csv',
                        help='Image analysis mutations CSV file path')
    parser.add_argument('--pdb-info',
                        type=str,
                        default='data/extraction/pdb_info.csv',
                        help='PDB info CSV file path')
    parser.add_argument('--enzyme-pdb',
                        type=str,
                        default='data/extraction/enzyme_to_pdb.csv',
                        help='Enzyme to PDB mapping CSV file path')
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: data/extraction/combined_data.csv)')
    parser.add_argument('--include-sequence',
                        action='store_true',
                        help='Include full protein sequence in output')

    args = parser.parse_args()

    # Validate input files
    for path, name in [(args.input, 'extraction JSON'),
                       (args.mutations, 'mutations CSV'),
                       (args.pdb_info, 'PDB info CSV'),
                       (args.enzyme_pdb, 'enzyme PDB CSV')]:
        if not Path(path).exists():
            print(f"Error: {name} not found: {path}")
            sys.exit(1)

    print("[INFO] Loading data files...")
    print(f"  - Extraction: {args.input}")
    print(f"  - Mutations: {args.mutations}")
    print(f"  - PDB info: {args.pdb_info}")
    print(f"  - Enzyme-PDB: {args.enzyme_pdb}")

    # Load data
    mutations_data = parse_mutations_from_image_csv(args.mutations)
    print(f"[OK] Loaded mutations for {len(mutations_data)} variants")

    enzyme_to_pdbs = load_enzyme_to_pdb(args.enzyme_pdb)
    print(f"[OK] Loaded PDB mappings for {len(enzyme_to_pdbs)} enzymes")

    pdb_info = load_pdb_info(args.pdb_info)
    print(f"[OK] Loaded info for {len(pdb_info)} PDB IDs")

    # Combine data
    print("[INFO] Combining data...")
    combined = combine_data(args.input,
                            mutations_data,
                            enzyme_to_pdbs,
                            pdb_info,
                            include_sequence=args.include_sequence)
    print(f"[OK] Combined {len(combined)} records")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = 'data/extraction/combined_data.csv'

    # Write CSV
    if combined:
        fieldnames = list(combined[0].keys())

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(combined)

        print(f"[OK] Wrote combined data to: {output_path}")

        # Print summary
        enzymes_with_mutations = sum(1 for r in combined if r['mutations'])
        enzymes_with_pdb = sum(1 for r in combined if r['pdb_ids'])

        print("\n[STATS] Summary:")
        print(f"  Total records: {len(combined)}")
        print(f"  Records with mutations: {enzymes_with_mutations}")
        print(f"  Records with PDB IDs: {enzymes_with_pdb}")
        if args.include_sequence:
            with_seq = sum(1 for r in combined if r.get('sequence'))
            print(f"  Records with sequences: {with_seq}")
    else:
        print("[WARNING] No data to write")


if __name__ == '__main__':
    main()
