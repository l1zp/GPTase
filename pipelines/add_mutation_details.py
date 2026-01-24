#!/usr/bin/env python3
"""
Pipeline Step 3: Add detailed mutation information from original text.

This script:
1. Reads CSV from Step 2
2. Extracts mutation details from original text/tables
3. Maps enzyme names to their specific mutations
4. Enriches CSV with mutation details

Based on information extracted from the paper:
- Des27.7 mutations: Ile54Val, Phe92His, Ile136Val, Val183Ile, Leu236Val, Ile216Val, plus active site
- Point mutants explicitly mentioned (F113L, F113M, D162A)
- Other variants have mutation counts but not full mutation lists in text

Usage:
    python pipelines/add_mutation_details.py
    python pipelines/add_mutation_details.py -i data/extraction/listov2025_extraction_with_variants.csv
"""

import csv
import argparse
import re
from pathlib import Path
from typing import Dict, Optional, List
import sys


# Known mutations from the paper text
# These are explicitly mentioned in the paper
KNOWN_MUTATIONS = {
    'Des27.7': {
        'mutations': ['Ile54Val', 'Phe92His', 'Ile136Val', 'Val183Ile', 'Leu236Val', 'Ile216Val'],
        'active_site_mutations': 15,  # "grafting the active site from Des27.7 (15 mutations)"
        'total_mutations': 7,
        'description': 'Top performer with FuncLib optimization'
    },
    'Des27.7 F113L': {
        'mutations': ['Phe113Leu'],
        'total_mutations': 1,
        'description': 'Point mutant - aromatic to aliphatic substitution'
    },
    'Des27.7 F113M': {
        'mutations': ['Phe113Met'],
        'total_mutations': 1,
        'description': 'Point mutant - aromatic to aliphatic substitution'
    },
    'Des27.7 D162A': {
        'mutations': ['Asp162Ala'],
        'total_mutations': 1,
        'description': 'Catalytic base mutation - abolishes activity'
    },
    'MA': {
        'mutations': [],
        'total_mutations': 92,  # "with 92 mutations relative to any natural protein"
        'description': 'Modular assembly baseline'
    },
    'MA + PROSS': {
        'mutations': [],
        'total_mutations': 103,  # 92 + 11 PROSS mutations
        'PROSS_mutations': 11,
        'description': 'MA with PROSS stabilization'
    },
    'MA + active site': {
        'mutations': [],
        'active_site_mutations': 15,
        'total_mutations': 107,  # 92 + 15 active site
        'description': 'MA with active site grafting'
    },
    'MA+ PROSS + active site': {
        'mutations': [],
        'active_site_mutations': 15,
        'PROSS_mutations': 11,
        'total_mutations': 118,  # 92 + 11 + 15
        'description': 'Combined design - full Des27.7 equivalent'
    },
}


def parse_mutation_info(enzyme_name: str, variant_info: Dict[str, str]) -> Dict[str, str]:
    """
    Parse mutation information for an enzyme.

    Args:
        enzyme_name: Raw enzyme name
        variant_info: Variant info from Step 2

    Returns:
        Dictionary with mutation details
    """
    mutation_details = {
        'specific_mutations': '',
        'mutation_list': '',
        'total_mutation_count': '',
        'PROSS_mutations': '',
        'active_site_mutations': '',
        'mutation_description': '',
        'key_mutations': '',
    }

    # Check if we have known mutations
    if enzyme_name in KNOWN_MUTATIONS:
        known = KNOWN_MUTATIONS[enzyme_name]
        mutation_details['specific_mutations'] = ', '.join(known.get('mutations', []))
        mutation_details['mutation_list'] = ', '.join(known.get('mutations', []))
        mutation_details['total_mutation_count'] = str(known.get('total_mutations', ''))
        mutation_details['PROSS_mutations'] = str(known.get('PROSS_mutations', ''))
        mutation_details['active_site_mutations'] = str(known.get('active_site_mutations', ''))
        mutation_details['mutation_description'] = known.get('description', '')

        return mutation_details

    # For FuncLib variants, we don't have exact mutations from text
    # but we can infer some information
    variant_type = variant_info.get('variant_type', '')
    mutation_count = variant_info.get('mutation_count', '')

    if variant_type == 'FuncLib_variant' and mutation_count:
        mutation_details['total_mutation_count'] = mutation_count
        mutation_details['mutation_description'] = f'FuncLib optimization with {mutation_count} active-site mutations'
        mutation_details['key_mutations'] = 'See Supplementary Table 1 for full list'

    elif variant_type == 'base_design':
        mutation_details['mutation_description'] = 'Base design from computational workflow'

    elif variant_type == 'component_ablation':
        mutation_details['mutation_description'] = 'Component ablation variant'

    elif variant_type == 'point_mutant':
        mutations = variant_info.get('mutations', '')
        if mutations:
            mutation_details['specific_mutations'] = mutations
            mutation_details['mutation_list'] = mutations
            mutation_details['total_mutation_count'] = '1'
            mutation_details['mutation_description'] = f'Site-directed mutant: {mutations}'

    return mutation_details


def enrich_csv_with_mutations(input_csv: str, output_csv: str) -> None:
    """
    Add detailed mutation information to CSV.

    Args:
        input_csv: Path to input CSV from Step 2
        output_csv: Path to output enriched CSV
    """
    # Read input CSV
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not fieldnames:
        print("❌ Error: Empty CSV file")
        sys.exit(1)

    # Add new mutation detail columns
    new_columns = [
        'specific_mutations',
        'mutation_list',
        'total_mutation_count',
        'PROSS_mutations',
        'active_site_mutations',
        'mutation_description',
        'key_mutations',
    ]

    # Insert new columns after existing mutation-related columns
    # Find the index to insert (after 'mutation_count')
    insert_idx = fieldnames.index('mutation_count') + 1 if 'mutation_count' in fieldnames else len(fieldnames)
    for col in new_columns:
        fieldnames.insert(insert_idx, col)

    # Process each row
    mutation_stats = {
        'with_known_mutations': 0,
        'with_partial_info': 0,
        'total': len(rows)
    }

    for row in rows:
        enzyme_name = row['enzyme_name']

        # Build variant info from existing columns
        variant_info = {
            'variant_type': row.get('variant_type', ''),
            'mutation_count': row.get('mutation_count', ''),
            'mutations': row.get('mutations', ''),
        }

        # Get mutation details
        mutation_details = parse_mutation_info(enzyme_name, variant_info)

        # Track statistics
        if mutation_details['specific_mutations']:
            mutation_stats['with_known_mutations'] += 1
        elif mutation_details['mutation_description']:
            mutation_stats['with_partial_info'] += 1

        # Add mutation details to row
        for col in new_columns:
            row[col] = mutation_details.get(col, '')

    # Write enriched CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Enriched {len(rows)} reactions with mutation details: {output_csv}")

    # Print statistics
    print("\n📊 Mutation Information Statistics:")
    print(f"   Total reactions: {mutation_stats['total']}")
    print(f"   With known mutations: {mutation_stats['with_known_mutations']}")
    print(f"   With partial info: {mutation_stats['with_partial_info']}")
    print(f"   With no mutation data: {mutation_stats['total'] - mutation_stats['with_known_mutations'] - mutation_stats['with_partial_info']}")

    # Show examples
    print("\n🔍 Examples of enzymes with detailed mutation info:")
    for enzyme in ['Des27.7', 'Des27.7 F113L', 'MA+ PROSS + active site']:
        found = False
        for row in rows:
            if row['enzyme_name'] == enzyme and row.get('specific_mutations'):
                print(f"\n   {enzyme}:")
                print(f"      Mutations: {row['specific_mutations']}")
                print(f"      Description: {row['mutation_description']}")
                found = True
                break
        if not found:
            print(f"\n   {enzyme}: Not found or no specific mutations listed")


def main():
    parser = argparse.ArgumentParser(
        description='Add detailed mutation information to CSV'
    )
    parser.add_argument(
        '-i', '--input',
        type=str,
        default='data/extraction/listov2025_extraction_with_variants.csv',
        help='Input CSV file path (from Step 2)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: input_with_mutations.csv)'
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
        stem = input_path.stem
        output_path = str(input_path.parent / f"{stem}_with_mutations.csv")

    print(f"🔄 Adding detailed mutation information to {args.input}...")

    # Enrich CSV
    try:
        enrich_csv_with_mutations(args.input, output_path)
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Pipeline step complete!")
    print("\n⚠️  NOTE: Most FuncLib variants (Des27.X, Des61.X) don't have")
    print("   explicit mutations listed in the main text. For complete")
    print("   mutation lists, refer to Supplementary Table 1 in the paper.")


if __name__ == '__main__':
    main()
