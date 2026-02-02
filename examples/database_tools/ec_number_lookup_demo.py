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
import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.external_databases.expasy import ExPAsyEnzymeLookupTool

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Configure logging format and level.

    Args:
        debug: Enable DEBUG level logging
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Look up enzyme reaction information from ExPASy database")
    parser.add_argument("--ec", nargs="+", help="EC number(s) to search for")
    parser.add_argument("--file",
                        type=str,
                        help="File containing EC numbers (one per line)")
    parser.add_argument("--extraction",
                        type=str,
                        help="Path to extraction CSV file to extract EC numbers from")
    parser.add_argument("--output", type=str, help="Output JSON file path (optional)")
    parser.add_argument("-v",
                        "--verbose",
                        action="store_true",
                        help="Show detailed output including comments and references")
    parser.add_argument("--debug",
                        action="store_true",
                        help="Enable debug level logging")
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
                    for ec in ec_col.split("|"):
                        ec = ec.strip()
                        if ec and ec not in ("None", "null"):
                            ec_numbers.add(ec)

        return sorted(list(ec_numbers))

    except Exception as e:
        logger.error(f"Error reading CSV file: {e}", exc_info=True)
        sys.exit(1)


async def main():
    """Main function to run EC number lookup."""
    args = parse_args()
    setup_logging(debug=args.debug)

    ec_numbers = []

    if args.ec:
        ec_numbers.extend(args.ec)

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"File not found: {args.file}")
            sys.exit(1)

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    for ec in line.split("|"):
                        ec = ec.strip()
                        if ec:
                            ec_numbers.append(ec)

    if args.extraction:
        if not Path(args.extraction).exists():
            logger.error(f"Extraction file not found: {args.extraction}")
            sys.exit(1)
        ec_numbers.extend(extract_ec_from_csv(args.extraction))

    if not ec_numbers:
        logger.error("No EC numbers specified.")
        logger.info("Use --ec, --file, or --extraction to provide EC numbers.")
        sys.exit(1)

    ec_numbers = sorted(list(set(ec_numbers)))

    ec_preview = ', '.join(ec_numbers[:5])
    if len(ec_numbers) > 5:
        ec_preview += "..."
    logger.info(f"Looking up {len(ec_numbers)} unique EC number(s) in ExPASy...")
    logger.info(f"EC numbers: {ec_preview}")
    logger.info("")

    tool = ExPAsyEnzymeLookupTool()

    try:
        result = await tool.execute(ec_numbers=ec_numbers)

        if result.status == "success":
            data = result.data
            summary = data["summary"]
            enzymes = data["enzymes"]

            logger.info(
                f"Results: {summary['found']}/{summary['total_searched']} found")
            logger.info(f"Not found: {summary['not_found']}")
            logger.info("")

            for i, enzyme in enumerate(enzymes, 1):
                logger.info(f"{i}. EC {enzyme['ec_number']}")

                if enzyme.get("error"):
                    logger.error(f"   Error: {enzyme['error']}")
                else:
                    if enzyme.get("enzyme_name"):
                        logger.info(f"   Name: {enzyme['enzyme_name']}")

                    if enzyme.get("reaction"):
                        reaction = enzyme['reaction']
                        reaction_preview = reaction[:200] + ('...' if len(reaction)
                                                             > 200 else '')
                        logger.info(f"   Reaction: {reaction_preview}")

                    if enzyme.get("reaction_equation"):
                        logger.info(f"   Equation: {enzyme['reaction_equation']}")

                    if enzyme.get("substrates"):
                        logger.info(f"   Substrates: {', '.join(enzyme['substrates'])}")

                    if enzyme.get("products"):
                        logger.info(f"   Products: {', '.join(enzyme['products'])}")

                    if enzyme.get("cofactors"):
                        cofactors = enzyme['cofactors']
                        cof_str = ', '.join(cofactors[:3])
                        if len(cofactors) > 3:
                            cof_str += f" ... ({len(cofactors)} total)"
                        logger.info(f"   Cofactors: {cof_str}")

                    if args.verbose:
                        if enzyme.get("comments"):
                            logger.info("   Comments:")
                            for comment in enzyme['comments'][:3]:
                                comm_preview = comment[:100] + ('...' if len(comment)
                                                                > 100 else '')
                                logger.info(f"     - {comm_preview}")
                            if len(enzyme['comments']) > 3:
                                logger.info(
                                    f"     ... ({len(enzyme['comments'])} comments total)"
                                )

                        if enzyme.get("alternate_names"):
                            alt_names = enzyme['alternate_names']
                            alt_str = ', '.join(alt_names[:2])
                            if len(alt_names) > 2:
                                alt_str += " ..."
                            logger.info(f"   Alternate names: {alt_str}")

                        if enzyme.get("references"):
                            logger.info(
                                f"   References: {len(enzyme['references'])} found")

                    if enzyme.get("source_url"):
                        logger.info(f"   Source: {enzyme['source_url']}")

                logger.info("")

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w") as f:
                    json.dump(data, f, indent=2)

                logger.info(f"Results saved to: {args.output}")
                logger.info("")

            logger.info(f"Execution time: {result.execution_time:.2f}s")
            logger.info(f"API requests: {summary['total_searched']}")

        else:
            logger.error(f"Error: {result.error_message}")
            sys.exit(1)

    finally:
        await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
