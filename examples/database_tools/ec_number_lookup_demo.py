#!/usr/bin/env python3
"""ExPASy Enzyme Database Lookup Demo.

This script demonstrates how to use the ExPAsyEnzymeLookupTool to retrieve
enzyme reaction information from the ExPASy enzyme database.

Example Usage:
    # Look up single EC number
    python examples/ec_number_lookup_demo.py --ec "1.1.1.1"

    # Look up multiple EC numbers
    python examples/ec_number_lookup_demo.py --ec 1.1.1.1 2.7.1.1 4.1.1.48

    # Read EC numbers from file
    python examples/ec_number_lookup_demo.py --file ec_numbers.txt

    # Save results to JSON
    python examples/ec_number_lookup_demo.py --ec "1.1.1.1" --output enzyme_data.json

    # Extract EC numbers from existing extraction results
    python examples/ec_number_lookup_demo.py --extraction data/output/listov2025/extraction/combined_data.csv
"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.external_databases.expasy import ExPAsyEnzymeLookupTool


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Look up enzyme reaction information from ExPASy database")
    parser.add_argument(
        "--ec",
        nargs="+",
        help="EC number(s) to search for (e.g., 1.1.1.1 or 1.1.1.1 2.7.1.1)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="File containing EC numbers (one per line or pipe-separated in CSV)",
    )
    parser.add_argument(
        "--extraction",
        type=str,
        help="Path to extraction CSV file to extract EC numbers from",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (optional)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including comments and references",
    )
    return parser.parse_args()


def extract_ec_from_csv(csv_path: str) -> list:
    """Extract EC numbers from extraction CSV file.

    Args:
        csv_path: Path to CSV file with ec_numbers column

    Returns:
        List of unique EC numbers
    """
    ec_numbers = set()

    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ec_col = row.get("ec_numbers", "")
                if ec_col:
                    # Split by pipe separator (multiple ECs per enzyme)
                    for ec in ec_col.split("|"):
                        ec = ec.strip()
                        if ec and ec != "None" and ec != "null":
                            ec_numbers.add(ec)

        return sorted(list(ec_numbers))

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)


async def main():
    """Main function to run EC number lookup."""
    args = parse_args()

    # Get EC numbers
    ec_numbers = []

    if args.ec:
        ec_numbers.extend(args.ec)

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Handle pipe-separated ECs
                    for ec in line.split("|"):
                        ec = ec.strip()
                        if ec:
                            ec_numbers.append(ec)

    if args.extraction:
        if not Path(args.extraction).exists():
            print(f"Error: Extraction file not found: {args.extraction}")
            sys.exit(1)
        ec_numbers.extend(extract_ec_from_csv(args.extraction))

    if not ec_numbers:
        print("Error: No EC numbers specified.")
        print("Use --ec, --file, or --extraction to provide EC numbers.")
        sys.exit(1)

    # Deduplicate
    ec_numbers = sorted(list(set(ec_numbers)))

    print(f"Looking up {len(ec_numbers)} unique EC number(s) in ExPASy...")
    print(f"EC numbers: {', '.join(ec_numbers[:5])}"
          + ("..." if len(ec_numbers) > 5 else ""))
    print()

    # Create tool
    tool = ExPAsyEnzymeLookupTool()

    try:
        # Execute lookup
        result = await tool.execute(ec_numbers=ec_numbers)

        # Check results
        if result.status == "success":
            data = result.data
            summary = data["summary"]
            enzymes = data["enzymes"]

            print(f"Results: {summary['found']}/{summary['total_searched']} found")
            print(f"Not found: {summary['not_found']}")
            print()

            # Display results
            for i, enzyme in enumerate(enzymes, 1):
                print(f"{i}. EC {enzyme['ec_number']}")

                if enzyme.get("error"):
                    print(f"   Error: {enzyme['error']}")
                else:
                    if enzyme.get("enzyme_name"):
                        print(f"   Name: {enzyme['enzyme_name']}")

                    if enzyme.get("reaction"):
                        print(
                            f"   Reaction: {enzyme['reaction'][:200]}{'...' if len(enzyme['reaction']) > 200 else ''}"
                        )

                    if enzyme.get("reaction_equation"):
                        print(f"   Equation: {enzyme['reaction_equation']}")

                    if enzyme.get("substrates"):
                        print(f"   Substrates: {', '.join(enzyme['substrates'])}")

                    if enzyme.get("products"):
                        print(f"   Products: {', '.join(enzyme['products'])}")

                    if enzyme.get("cofactors"):
                        print(f"   Cofactors: {', '.join(enzyme['cofactors'][:3])}"
                              + (f" ... ({len(enzyme['cofactors'])} total)"
                                 if len(enzyme['cofactors']) > 3 else ""))

                    if args.verbose:
                        if enzyme.get("comments"):
                            print(f"   Comments:")
                            for comment in enzyme['comments'][:3]:
                                print(
                                    f"     - {comment[:100]}{'...' if len(comment) > 100 else ''}"
                                )
                            if len(enzyme['comments']) > 3:
                                print(
                                    f"     ... ({len(enzyme['comments'])} comments total)"
                                )

                        if enzyme.get("alternate_names"):
                            print(
                                f"   Alternate names: {', '.join(enzyme['alternate_names'][:2])}"
                                +
                                (f" ..." if len(enzyme['alternate_names']) > 2 else ""))

                        if enzyme.get("references"):
                            print(f"   References: {len(enzyme['references'])} found")

                    if enzyme.get("source_url"):
                        print(f"   Source: {enzyme['source_url']}")

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
            print(f"API requests: {summary['total_searched']}")

        else:
            print(f"Error: {result.error_message}")
            sys.exit(1)

    finally:
        # Cleanup
        await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
