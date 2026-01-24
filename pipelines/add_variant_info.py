#!/usr/bin/env python3
"""
Pipeline Step 2: Add variant information to enzyme extraction CSV.

This script:
1. Reads CSV file from Step 1
2. Parses enzyme names to extract variant information
3. Maps variants to their design components (mutations, design method)
4. Enriches CSV with variant metadata

Enzyme naming conventions from the paper:
- Des27, Des61: Base designs from modular assembly
- Des27.X, Des61.X: FuncLib variants with X mutations (X = 1-13)
- R2.Des39.X: RoseTTAFold-based designs with mutations
- MA: Modular Assembly only
- MA + PROSS: MA with stabilization
- MA + active site: MA with active site mutations
- MA+ PROSS + active site: Combined design
- Des27.7 F113L/M: Specific point mutants

Usage:
    python pipelines/add_variant_info.py
    python pipelines/add_variant_info.py -i data/extraction/listov2025_extraction.csv
"""

import csv
import argparse
import re
from pathlib import Path
from typing import Dict, Optional, List
import sys


def parse_enzyme_name(enzyme_name: str) -> Dict[str, str]:
    """
    Parse enzyme name to extract variant information.

    Args:
        enzyme_name: Raw enzyme name from extraction

    Returns:
        Dictionary with variant metadata
    """
    variant_info = {
        'base_design': '',
        'design_method': '',
        'optimization': '',
        'mutations': '',
        'mutation_count': '',
        'variant_type': '',
    }

    # Handle point mutants (e.g., "Des27.7 F113L")
    point_mutant_match = re.match(r'(\w+\.\d+)\s+([A-Z]\d+[A-Z])', enzyme_name)
    if point_mutant_match:
        base = point_mutant_match.group(1)
        mutation = point_mutant_match.group(2)

        variant_info['base_design'] = base
        variant_info['variant_type'] = 'point_mutant'
        variant_info['mutations'] = mutation
        variant_info['optimization'] = 'site-directed_mutagenesis'

        # Parse base design for method
        if 'R2.' in base:
            variant_info['design_method'] = 'RoseTTAFold'
        elif 'Des' in base:
            variant_info['design_method'] = 'modular_assembly'

        return variant_info

    # Handle MA-based designs
    if enzyme_name.startswith('MA'):
        variant_info['base_design'] = 'MA'
        variant_info['design_method'] = 'modular_assembly'
        variant_info['variant_type'] = 'component_ablation'

        if 'PROSS' in enzyme_name and 'active site' in enzyme_name:
            variant_info['optimization'] = 'PROSS + active_site'
        elif 'PROSS' in enzyme_name:
            variant_info['optimization'] = 'PROSS'
        elif 'active site' in enzyme_name:
            variant_info['optimization'] = 'active_site'
        else:
            variant_info['optimization'] = 'none'

        return variant_info

    # Handle Des27.X and Des61.X variants
    des_match = re.match(r'(Des\d+)(?:\.(\d+))?', enzyme_name)
    if des_match:
        base = des_match.group(1)
        variant_num = des_match.group(2)

        variant_info['base_design'] = base
        variant_info['design_method'] = 'modular_assembly'

        if variant_num:
            variant_info['variant_type'] = 'FuncLib_variant'
            variant_info['mutation_count'] = variant_num
            variant_info['optimization'] = f'FuncLib ({variant_num} mutations)'
        else:
            variant_info['variant_type'] = 'base_design'
            variant_info['optimization'] = 'none'

        return variant_info

    # Handle R2.Des39.X variants
    r2_match = re.match(r'(R2\.\w+)(?:\.([\d.]+))?', enzyme_name)
    if r2_match:
        base = r2_match.group(1)
        variant_num = r2_match.group(2)

        variant_info['base_design'] = base
        variant_info['design_method'] = 'RoseTTAFold'

        if variant_num:
            variant_info['variant_type'] = 'FuncLib_variant'
            # Count the dots to estimate mutation rounds
            dot_count = variant_num.count('.')
            if dot_count == 0:
                variant_info['mutation_count'] = variant_num
            else:
                parts = variant_num.split('.')
                variant_info['mutation_count'] = parts[0] if parts else ''
            variant_info['optimization'] = f'FuncLib optimization'
        else:
            variant_info['variant_type'] = 'base_design'
            variant_info['optimization'] = 'none'

        return variant_info

    # Default: unknown format
    variant_info['variant_type'] = 'unknown'
    return variant_info


def enrich_csv_with_variants(input_csv: str, output_csv: str) -> None:
    """
    Add variant information columns to CSV.

    Args:
        input_csv: Path to input CSV from Step 1
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

    # Add new columns
    new_columns = [
        'base_design',
        'design_method',
        'optimization',
        'mutations',
        'mutation_count',
        'variant_type'
    ]

    # Insert new columns after enzyme_name
    enzyme_idx = fieldnames.index('enzyme_name')
    for col in new_columns:
        fieldnames.insert(enzyme_idx + 1, col)

    # Process each row
    for row in rows:
        enzyme_name = row['enzyme_name']
        variant_info = parse_enzyme_name(enzyme_name)

        # Add variant info to row
        for col in new_columns:
            row[col] = variant_info.get(col, '')

    # Write enriched CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Enriched {len(rows)} reactions with variant information: {output_csv}")

    # Print statistics
    print_variant_statistics(rows, new_columns)


def print_variant_statistics(rows: List[Dict], columns: List[str]) -> None:
    """Print statistics about variant types."""
    print("\n📊 Variant Statistics:")

    # Count design methods
    design_methods = {}
    for row in rows:
        method = row.get('design_method', 'unknown')
        design_methods[method] = design_methods.get(method, 0) + 1

    print(f"\n   Design Methods:")
    for method, count in sorted(design_methods.items()):
        print(f"      {method}: {count}")

    # Count variant types
    variant_types = {}
    for row in rows:
        vtype = row.get('variant_type', 'unknown')
        variant_types[vtype] = variant_types.get(vtype, 0) + 1

    print(f"\n   Variant Types:")
    for vtype, count in sorted(variant_types.items()):
        print(f"      {vtype}: {count}")

    # Count base designs
    base_designs = {}
    for row in rows:
        base = row.get('base_design', 'unknown')
        base_designs[base] = base_designs.get(base, 0) + 1

    print(f"\n   Base Designs:")
    for base, count in sorted(base_designs.items(), key=lambda x: x[1], reverse=True):
        print(f"      {base}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description='Add variant information to enzyme extraction CSV'
    )
    parser.add_argument(
        '-i', '--input',
        type=str,
        default='data/extraction/listov2025_extraction.csv',
        help='Input CSV file path (from Step 1)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: input_with_variants.csv)'
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
        output_path = str(input_path.parent / f"{stem}_with_variants.csv")

    print(f"🔄 Adding variant information to {args.input}...")

    # Enrich CSV
    try:
        enrich_csv_with_variants(args.input, output_path)
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        sys.exit(1)

    print("\n✅ Pipeline step complete!")


if __name__ == '__main__':
    main()
