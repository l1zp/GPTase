"""Rhea Database Lookup Demo.

This script demonstrates how to use the RheaReactionLookupTool to query
biochemical reactions from the Rhea database.

Usage:
    python examples/rhea_lookup_demo.py
"""

import asyncio
import json
from pathlib import Path

from src.tools.external_databases.rhea import (
    RheaReactionLookupTool,
    lookup_rhea_reaction,
)
from src.tools.base import ToolStatus


async def main():
    """Run Rhea lookup demonstrations."""

    print("=" * 80)
    print("Rhea Biochemical Reaction Database Lookup Demo")
    print("=" * 80)
    print()

    # Initialize tool
    tool = RheaReactionLookupTool()

    try:
        # Example 1: Get reaction by Rhea ID
        print("Example 1: Get reaction by Rhea ID")
        print("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:15109")

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            if reactions:
                reaction = reactions[0]
                print(f"Rhea ID: {reaction['rhea_id']}")
                print(f"Equation: {reaction['equation']}")
                print(f"EC Numbers: {', '.join(reaction['ec_numbers']) or 'N/A'}")
                print(f"Substrates: {', '.join(reaction['substrates'])}")
                print(f"Products: {', '.join(reaction['products'])}")
                print(f"ChEBI Compounds: {', '.join(reaction['chebi_names'])}")
                print(f"UniProt Enzymes: {reaction['uniprot_count']}")
                if reaction['xrefs']:
                    print("Cross-references:")
                    for db, ids in reaction['xrefs'].items():
                        if ids:
                            print(f"  {db}: {', '.join(ids)}")
            else:
                print("No reaction found")
        else:
            print(f"Error: {result.error}")
        print()

        # Example 2: Get reactions by EC number
        print("Example 2: Get reactions by EC number (2.7.1.1 - Hexokinase)")
        print("-" * 80)
        result = await tool.get_reactions_by_ec("2.7.1.1", limit=5)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation']}")
                print(f"    Substrates: {', '.join(reaction['substrates'])}")
                print(f"    Products: {', '.join(reaction['products'])}")
        else:
            print(f"Error: {result.error}")
        print()

        # Example 3: Search reactions by compound name
        print("Example 3: Search reactions by compound name (ATP)")
        print("-" * 80)
        result = await tool.search_reactions_by_compound("ATP", limit=5)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions involving ATP:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation']}")
                if reaction['ec_numbers']:
                    print(f"    EC: {', '.join(reaction['ec_numbers'])}")
        else:
            print(f"Error: {result.error}")
        print()

        # Example 4: Search reactions by ChEBI ID
        print("Example 4: Search reactions by ChEBI ID (CHEBI:30616 - ATP)")
        print("-" * 80)
        result = await tool.search_reactions_by_compound("CHEBI:30616", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation']}")
                print(f"    ChEBI IDs: {', '.join(reaction['chebi_ids'])}")
        else:
            print(f"Error: {result.error}")
        print()

        # Example 5: Get reactions with UniProt enzymes
        print("Example 5: Get reactions with UniProt enzyme annotations")
        print("-" * 80)
        result = await tool.execute(query="", query_type="uniprot", limit=5)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions with UniProt annotations:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation']}")
                print(f"    UniProt enzymes: {reaction['uniprot_count']}")
        else:
            print(f"Error: {result.error}")
        print()

        # Example 6: Convenience function usage
        print("Example 6: Using convenience function")
        print("-" * 80)
        data = await lookup_rhea_reaction("RHEA:10000", query_type="rhea-id")

        if data["reactions"]:
            reaction = data["reactions"][0]
            print(f"Quick lookup: {reaction['rhea_id']}")
            print(f"Equation: {reaction['equation']}")
            print(f"EC: {', '.join(reaction['ec_numbers'])}")
        print()

        # Save results to JSON file
        print("Saving results to file...")
        output_file = Path("data/rhea_lookup_results.json")
        output_file.parent.mkdir(exist_ok=True)

        # Collect all results
        all_results = {
            "by_rhea_id": await lookup_rhea_reaction("RHEA:15109"),
            "by_ec": await lookup_rhea_reaction("2.7.1.1", query_type="ec", limit=10),
            "by_compound": await lookup_rhea_reaction("glucose", query_type="compound", limit=10),
        }

        with open(output_file, "w") as f:
            json.dump(all_results, f, indent=2)

        print(f"Results saved to: {output_file}")
        print()

    finally:
        # Clean up
        await tool.close()

    print("=" * 80)
    print("Demo completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
