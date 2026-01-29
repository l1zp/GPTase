#!/usr/bin/env python3
"""
Pipeline Step 1: Convert enzyme extraction JSON results to CSV format.

This script:
1. Loads JSON extraction results from data/extraction/
2. Flattens nested structures (conditions, kinetics)
3. Converts to CSV format
4. Handles null values and special characters
5. Outputs analysis-ready CSV file

Usage:
    python pipelines/json_to_csv.py
    python pipelines/json_to_csv.py -i data/extraction/my_extraction.json -o output.csv
    python pipelines/json_to_csv.py --stats
"""

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional


def load_json(json_path: str) -> Dict[str, Any]:
    """Load JSON extraction results."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def flatten_reaction(reaction: Dict[str, Any],
                     include_pdb_ids: bool = False) -> Dict[str, Any]:
    """
    Flatten a single reaction entry into a flat dictionary.

    Converts nested structures (conditions, kinetics) into flat key-value pairs.
    Handles null values and special characters.

    Args:
        reaction: Reaction dictionary from extraction JSON
        include_pdb_ids: Whether to include pdb_ids column (default: False)

    Uses pipe (|) delimiter for list fields to avoid CSV parsing issues with commas.
    """
    flat = {
        'enzyme_name':
        reaction.get('enzyme_name', ''),
        'substrates':
        ', '.join(reaction.get('substrates', [])),
        'products':
        ', '.join(reaction.get('products', [])),
        'mutations':
        '|'.join(reaction.get('mutations', []))
        if reaction.get('mutations') else '',  # Use pipe delimiter, handle None
        'yield_percent':
        reaction.get('yield_percent')
        if reaction.get('yield_percent') is not None else '',
        'citations':
        ', '.join(reaction.get('citations', [])),
    }

    # Only include pdb_ids if explicitly requested
    if include_pdb_ids:
        pdb_ids = reaction.get('pdb_ids', [])
        pdb_is_new = reaction.get('pdb_is_new', [])
        flat['pdb_ids'] = ', '.join(pdb_ids)
        # Add pdb_is_new as parallel field (pipe-delimited, "true" or "false")
        flat['pdb_is_new'] = '|'.join(str(v).lower()
                                      for v in pdb_is_new) if pdb_is_new else ''

    # Flatten conditions
    conditions = reaction.get('conditions', {})
    flat.update({
        'temperature':
        conditions.get('temperature')
        if conditions.get('temperature') is not None else '',
        'pH':
        conditions.get('pH') if conditions.get('pH') is not None else '',
        'buffer':
        conditions.get('buffer') if conditions.get('buffer') is not None else '',
        'time':
        conditions.get('time') if conditions.get('time') is not None else '',
        'notes':
        conditions.get('notes') if conditions.get('notes') is not None else '',
    })

    # Flatten kinetics
    kinetics = reaction.get('kinetics', {})
    flat.update({
        'Km':
        kinetics.get('Km') if kinetics.get('Km') is not None else '',
        'Km_unit':
        kinetics.get('Km_unit', ''),
        'Vmax':
        kinetics.get('Vmax') if kinetics.get('Vmax') is not None else '',
        'Vmax_unit':
        kinetics.get('Vmax_unit', ''),
        'kcat':
        kinetics.get('kcat') if kinetics.get('kcat') is not None else '',
        'kcat_unit':
        kinetics.get('kcat_unit', ''),
        'kcat_over_KM':
        kinetics.get('kcat_over_KM')
        if kinetics.get('kcat_over_KM') is not None else '',
        'kcat_over_KM_unit':
        kinetics.get('kcat_over_KM_unit', ''),
        'Tm':
        kinetics.get('Tm') if kinetics.get('Tm') is not None else '',
        'Tm_unit':
        kinetics.get('Tm_unit', ''),
    })

    return flat


def validate_and_clean(
        reactions: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate and clean reaction data before CSV export.

    Args:
        reactions: List of flattened reaction dictionaries

    Returns:
        Tuple of (cleaned_reactions, warnings)
    """
    cleaned = []
    warnings = []

    for rxn in reactions:
        cleaned_rxn = rxn.copy()

        # Validate numeric fields
        for field in ['Km', 'Vmax', 'kcat', 'kcat_over_KM', 'Tm', 'yield_percent']:
            value = cleaned_rxn.get(field, '')

            # Handle both string and numeric values
            if value is None or value == '':
                continue

            # Convert to string for processing
            value_str = str(value) if not isinstance(value, str) else value

            if value_str and value_str.strip():
                try:
                    # Handle special values
                    if value_str.lower() in ['n.c.', 'n.d.', 'n.m.', '']:
                        cleaned_rxn[field] = ''
                    else:
                        num = float(value_str)
                        # Check for impossible values
                        if field == 'Tm' and (num < 0 or num > 150):
                            warnings.append(
                                f"{rxn.get('enzyme_name', 'Unknown')}: {field}={num}°C (unrealistic)"
                            )
                        elif field in ['kcat', 'kcat_over_KM', 'Km', 'Vmax'
                                       ] and num < 0:
                            warnings.append(
                                f"{rxn.get('enzyme_name', 'Unknown')}: {field}={num} (negative value)"
                            )
                        elif field == 'yield_percent' and (num < 0 or num > 100):
                            warnings.append(
                                f"{rxn.get('enzyme_name', 'Unknown')}: yield={num}% (should be 0-100)"
                            )
                except ValueError:
                    warnings.append(
                        f"{rxn.get('enzyme_name', 'Unknown')}: {field}='{value_str}' (invalid number)"
                    )

        # Validate units consistency
        if cleaned_rxn.get('kcat') and not cleaned_rxn.get('kcat_unit'):
            warnings.append(
                f"{rxn.get('enzyme_name', 'Unknown')}: kcat has value but no unit")
        if cleaned_rxn.get('Km') and not cleaned_rxn.get('Km_unit'):
            warnings.append(
                f"{rxn.get('enzyme_name', 'Unknown')}: Km has value but no unit")

        # Clean mutations (already using pipe delimiter, just validate format)
        mutations = cleaned_rxn.get('mutations', '')
        if mutations:
            mutation_list = [m.strip() for m in mutations.split('|') if m.strip()]
            cleaned_rxn['mutations'] = '|'.join(mutation_list)

        cleaned.append(cleaned_rxn)

    return cleaned, warnings


def convert_to_csv(reactions: List[Dict[str, Any]],
                   output_path: str,
                   validate: bool = False,
                   include_pdb_ids: bool = False) -> None:
    """
    Convert flattened reactions to CSV.

    Args:
        reactions: List of reaction dictionaries
        output_path: Path for output CSV file
        validate: Whether to apply validation before export
        include_pdb_ids: Whether to include pdb_ids column (default: False)
    """
    if not reactions:
        print("⚠️  No reactions to convert!")
        return

    # Flatten all reactions
    flattened_data = [
        flatten_reaction(r, include_pdb_ids=include_pdb_ids) for r in reactions
    ]

    # Apply validation if requested
    if validate:
        flattened_data, warnings = validate_and_clean(flattened_data)
        if warnings:
            print(f"⚠️  Validation warnings: {len(warnings)}")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"   - {warning}")
            if len(warnings) > 5:
                print(f"   ... and {len(warnings) - 5} more warnings")

    # Get column headers from first reaction
    fieldnames = list(flattened_data[0].keys())

    # Write CSV with proper quoting for fields with special characters
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            delimiter=',',
            quotechar='"',
            quoting=csv.
            QUOTE_MINIMAL  # Quote fields with special characters (commas, quotes, newlines)
        )

        writer.writeheader()
        writer.writerows(flattened_data)

    print(f"✅ Converted {len(reactions)} reactions to CSV: {output_path}")


def print_statistics(reactions: List[Dict[str, Any]]) -> None:
    """Print basic statistics about the reactions."""
    print(f"\n📊 Statistics:")
    print(f"   Total reactions: {len(reactions)}")

    # Count reactions with different kinetic parameters
    has_kcat = sum(1 for r in reactions
                   if r.get('kinetics', {}).get('kcat') is not None)
    has_km = sum(1 for r in reactions if r.get('kinetics', {}).get('Km') is not None)
    has_tm = sum(1 for r in reactions if r.get('kinetics', {}).get('Tm') is not None)

    print(f"   Reactions with kcat: {has_kcat}")
    print(f"   Reactions with Km: {has_km}")
    print(f"   Reactions with Tm: {has_tm}")

    # Calculate basic statistics
    kcat_values = [
        r['kinetics']['kcat'] for r in reactions
        if r.get('kinetics', {}).get('kcat') is not None
    ]
    if kcat_values:
        print(f"\n   kcat statistics:")
        print(f"      Min: {min(kcat_values):.2f} s⁻¹")
        print(f"      Max: {max(kcat_values):.2f} s⁻¹")
        print(f"      Mean: {sum(kcat_values)/len(kcat_values):.2f} s⁻¹")


def main():
    parser = argparse.ArgumentParser(
        description='Convert enzyme extraction JSON to CSV format')
    parser.add_argument('-i',
                        '--input',
                        type=str,
                        default='data/extraction/listov2025_extraction.json',
                        help='Input JSON file path')
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: same as input with .csv extension)')
    parser.add_argument('--stats',
                        action='store_true',
                        help='Print statistics about the reactions')
    parser.add_argument('--validate',
                        action='store_true',
                        help='Enable data validation before export')
    parser.add_argument(
        '--include-pdb-ids',
        action='store_true',
        help=
        'Include pdb_ids column in CSV (default: False, use separate PDB files instead)'
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
        output_path = str(input_path.with_suffix('.csv'))

    print(f"🔄 Converting {args.input} to CSV...")

    # Load JSON
    try:
        data = load_json(args.input)
        reactions = data.get('reactions', [])
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        sys.exit(1)

    # Convert to CSV
    convert_to_csv(reactions,
                   output_path,
                   validate=args.validate,
                   include_pdb_ids=args.include_pdb_ids)

    # Print statistics if requested
    if args.stats:
        print_statistics(reactions)

    print("\n✅ Pipeline step complete!")


if __name__ == '__main__':
    main()
