#!/usr/bin/env python3
"""PubChem SMILES Lookup Demo.

This script demonstrates how to use the PubChemSMILESLookupTool to retrieve
SMILES strings and compound properties from PubChem database.

Example Usage:
    # Look up single compound
    python examples/pubchem_lookup_demo.py --compound "acetone"

    # Look up multiple compounds
    python examples/pubchem_lookup_demo.py --compound acetone ethanol glucose

    # Read compounds from file
    python examples/pubchem_lookup_demo.py --file compounds.txt

    # Include additional properties
    python examples/pubchem_lookup_demo.py --compound acetone --props MolecularFormula MolecularWeight
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.pubchem_smiles_lookup import PubChemSMILESLookupTool


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Look up compound SMILES from PubChem database"
    )
    parser.add_argument(
        "--compound",
        nargs="+",
        help="Compound name(s) to search for",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="File containing compound names (one per line)",
    )
    parser.add_argument(
        "--props",
        nargs="+",
        default=None,
        help="Additional properties to retrieve (default: IsomericSMILES, MolecularFormula, MolecularWeight)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (optional)",
    )
    return parser.parse_args()


async def main():
    """Main function to run PubChem lookup."""
    args = parse_args()

    # Get compound names
    compound_names = []
    if args.compound:
        compound_names.extend(args.compound)

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)

        with open(file_path, "r") as f:
            file_compounds = [line.strip() for line in f if line.strip()]
            compound_names.extend(file_compounds)

    if not compound_names:
        print("Error: No compounds specified. Use --compound or --file")
        sys.exit(1)

    print(f"Looking up {len(compound_names)} compound(s) in PubChem...")
    print(f"Compounds: {', '.join(compound_names[:5])}" + ("..." if len(compound_names) > 5 else ""))
    print()

    # Create tool
    tool = PubChemSMILESLookupTool()

    try:
        # Execute lookup
        result = await tool.execute(
            compound_names=compound_names,
            properties=args.props,
        )

        # Check results
        if result.status == "success":
            data = result.data
            summary = data["summary"]
            compounds = data["compounds"]

            print(f"Results: {summary['found']}/{summary['total_searched']} found")
            print()

            # Display results
            for i, comp in enumerate(compounds, 1):
                print(f"{i}. {comp['name']}")
                if comp.get("error"):
                    print(f"   Error: {comp['error']}")
                else:
                    print(f"   CID: {comp['cid']}")
                    print(f"   SMILES: {comp['smiles']}")
                    if comp.get("cas"):
                        print(f"   CAS: {comp['cas']}")
                    if comp.get("properties"):
                        props = comp["properties"]
                        if "MolecularFormula" in props:
                            print(f"   Formula: {props['MolecularFormula']}")
                        if "MolecularWeight" in props:
                            print(f"   MW: {props['MolecularWeight']}")
                print()

            # Save to file if requested
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w") as f:
                    json.dump(data, f, indent=2)

                print(f"Results saved to: {args.output}")
                print()

            # Summary
            print(f"Execution time: {result.execution_time:.2f}s")
            print(f"API requests: ~{summary['total_searched'] * 3} (search + properties + synonyms)")

        else:
            print(f"Error: {result.error_message}")
            sys.exit(1)

    finally:
        # Cleanup
        await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
