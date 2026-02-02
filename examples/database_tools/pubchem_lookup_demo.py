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
import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.external_databases.pubchem import PubChemSMILESLookupTool

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
        description="Look up compound SMILES from PubChem database")
    parser.add_argument("--compound", nargs="+", help="Compound name(s) to search for")
    parser.add_argument("--file",
                        type=str,
                        help="File containing compound names (one per line)")
    parser.add_argument("--props",
                        nargs="+",
                        default=None,
                        help="Additional properties to retrieve")
    parser.add_argument("--output", type=str, help="Output JSON file path (optional)")
    parser.add_argument("--debug",
                        action="store_true",
                        help="Enable debug level logging")
    return parser.parse_args()


async def main():
    """Main function to run PubChem lookup."""
    args = parse_args()
    setup_logging(debug=args.debug)

    compound_names = []
    if args.compound:
        compound_names.extend(args.compound)

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"File not found: {args.file}")
            sys.exit(1)

        with open(file_path, "r") as f:
            file_compounds = [line.strip() for line in f if line.strip()]
            compound_names.extend(file_compounds)

    if not compound_names:
        logger.error("No compounds specified. Use --compound or --file")
        sys.exit(1)

    logger.info(f"Looking up {len(compound_names)} compound(s) in PubChem...")
    compound_preview = ', '.join(compound_names[:5])
    if len(compound_names) > 5:
        compound_preview += "..."
    logger.info(f"Compounds: {compound_preview}")
    logger.info("")

    tool = PubChemSMILESLookupTool()

    try:
        result = await tool.execute(
            compound_names=compound_names,
            properties=args.props,
        )

        if result.status == "success":
            data = result.data
            summary = data["summary"]
            compounds = data["compounds"]

            logger.info(
                f"Results: {summary['found']}/{summary['total_searched']} found")
            logger.info("")

            for i, comp in enumerate(compounds, 1):
                logger.info(f"{i}. {comp['name']}")
                if comp.get("error"):
                    logger.error(f"   Error: {comp['error']}")
                else:
                    logger.info(f"   CID: {comp['cid']}")
                    logger.info(f"   SMILES: {comp['smiles']}")
                    if comp.get("cas"):
                        logger.info(f"   CAS: {comp['cas']}")
                    if comp.get("properties"):
                        props = comp["properties"]
                        if "MolecularFormula" in props:
                            logger.info(f"   Formula: {props['MolecularFormula']}")
                        if "MolecularWeight" in props:
                            logger.info(f"   MW: {props['MolecularWeight']}")
                logger.info("")

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w") as f:
                    json.dump(data, f, indent=2)

                logger.info(f"Results saved to: {args.output}")
                logger.info("")

            logger.info(f"Execution time: {result.execution_time:.2f}s")
            logger.info(f"API requests: ~{summary['total_searched'] * 3} "
                        "(search + properties + synonyms)")

        else:
            logger.error(f"Error: {result.error_message}")
            sys.exit(1)

    finally:
        await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
