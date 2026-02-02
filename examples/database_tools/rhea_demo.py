"""Rhea Biochemical Reaction Database - Complete Demo.

This comprehensive demo demonstrates all features of the RheaReactionLookupTool:
1. Basic reaction queries (by ID, EC number, compound)
2. Mechanism information extraction
3. Cross-references and stereochemistry
4. Convenience functions

Rhea Database: https://www.rhea-db.org/

Usage:
    # Run all demos
    python examples/database_tools/rhea_demo.py

    # Run specific section
    python examples/database_tools/rhea_demo.py --section basic
    python examples/database_tools/rhea_demo.py --section mechanism
    python examples/database_tools/rhea_demo.py --section advanced
"""

import argparse
import asyncio
import json
from pathlib import Path

from src.tools.base import ToolStatus
from src.tools.external_databases.rhea import lookup_rhea_reaction
from src.tools.external_databases.rhea import RheaReactionLookupTool


async def demo_basic_queries():
    """Demonstrate basic Rhea query capabilities."""

    print("=" * 80)
    print("Part 1: Basic Rhea Queries")
    print("=" * 80)
    print()

    tool = RheaReactionLookupTool()

    try:
        # 1.1 Query by Rhea ID
        print("1.1 Query by Rhea ID")
        print("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:15109")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]
            print(f"Rhea ID: {reaction['rhea_id']}")
            print(f"Equation: {reaction['equation']}")
            print(f"EC Numbers: {', '.join(reaction['ec_numbers']) or 'N/A'}")
            print(f"Substrates: {', '.join(reaction['substrates'])}")
            print(f"Products: {', '.join(reaction['products'])}")
            print(f"ChEBI Compounds: {len(reaction['chebi_names'])} compounds")
            print(f"UniProt Enzymes: {reaction['uniprot_count']} proteins")
        print()

        # 1.2 Query by EC number
        print("1.2 Query by EC Number (2.7.1.1 - Hexokinase)")
        print("-" * 80)
        result = await tool.get_reactions_by_ec("2.7.1.1", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation'][:70]}...")
        print()

        # 1.3 Query by compound name
        print("1.3 Query by Compound Name (ATP)")
        print("-" * 80)
        result = await tool.search_reactions_by_compound("ATP", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions involving ATP:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation'][:70]}...")
        print()

        # 1.4 Query by ChEBI ID
        print("1.4 Query by ChEBI ID (CHEBI:30616 - ATP)")
        print("-" * 80)
        result = await tool.search_reactions_by_compound("CHEBI:30616", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions:")
            for reaction in reactions:
                print(f"  {reaction['rhea_id']}: {reaction['equation'][:70]}...")
        print()

    finally:
        await tool.close()


async def demo_mechanism_info():
    """Demonstrate mechanism information extraction."""

    print("=" * 80)
    print("Part 2: Mechanism Information")
    print("=" * 80)
    print()

    tool = RheaReactionLookupTool()

    try:
        # 2.1 Chorismate synthase - radical mechanism example
        print("2.1 Chorismate Synthase - Radical Mechanism")
        print("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:21020")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]
            print(f"Reaction: {reaction['equation']}")
            print(f"EC: {', '.join(reaction['ec_numbers'])}")
            print()

            # Get mechanism links
            links = tool.get_mechanism_links(reaction)

            print("Mechanism Information Sources:")
            print()
            print(f"1. Rhea Web Page:")
            print(f"   {links['rhea_web_url']}")
            print()

            print("2. Mechanistic Studies (PubMed Articles):")
            for article in links["pubmed_articles"][:3]:
                print(f"   - PubMed {article['pubmed_id']}")
                print(f"     {article['url']}")
            if len(links["pubmed_articles"]) > 3:
                print(f"   ... and {len(links['pubmed_articles']) - 3} more")
            print()

            print("3. Stereochemistry (ChEBI):")
            for compound in links["chebi_compounds"][:3]:
                print(f"   - {compound['chebi_id']}: {compound['chebi_name']}")
                print(f"     SMILES at: {compound['url']}")
            print()

            if links["mcsa_links"]:
                print("4. Catalytic Mechanism (M-CSA):")
                for mcsa in links["mcsa_links"]:
                    print(f"   - {mcsa['mcsa_id']}")
                    print(f"     {mcsa['url']}")
            else:
                print("4. Catalytic Mechanism (M-CSA):")
                print("   No M-CSA entries available for this reaction")
        print()

    finally:
        await tool.close()


async def demo_advanced_features():
    """Demonstrate advanced features."""

    print("=" * 80)
    print("Part 3: Advanced Features")
    print("=" * 80)
    print()

    tool = RheaReactionLookupTool()

    try:
        # 3.1 Cross-references
        print("3.1 Cross-References")
        print("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:15109")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]
            print(f"Reaction: {reaction['rhea_id']}")
            print()
            print("Cross-references:")
            for db, ids in reaction['xrefs'].items():
                if ids:
                    print(f"  {db}: {', '.join(ids)}")
                else:
                    print(f"  {db}: (not available)")
        print()

        # 3.2 Convenience function
        print("3.2 Convenience Function")
        print("-" * 80)
        data = await lookup_rhea_reaction("RHEA:10000", query_type="rhea-id")

        if data["reactions"]:
            reaction = data["reactions"][0]
            print(f"Quick lookup: {reaction['rhea_id']}")
            print(f"Equation: {reaction['equation']}")
            print(f"EC: {', '.join(reaction['ec_numbers'])}")
        print()

        # 3.3 Batch queries
        print("3.3 Batch Query Example")
        print("-" * 80)
        ec_numbers = ["2.7.1.1", "1.1.1.1", "4.2.3.5"]
        all_reactions = []

        for ec in ec_numbers:
            result = await tool.get_reactions_by_ec(ec, limit=2)
            if result.status == ToolStatus.SUCCESS:
                all_reactions.extend(result.data["reactions"])

        print(f"Total reactions found: {len(all_reactions)}")
        for reaction in all_reactions[:5]:
            print(f"  {reaction['rhea_id']}: {reaction['equation'][:60]}...")
        if len(all_reactions) > 5:
            print(f"  ... and {len(all_reactions) - 5} more")
        print()

    finally:
        await tool.close()


async def save_results():
    """Save query results to file for later analysis."""

    print("=" * 80)
    print("Part 4: Save Results")
    print("=" * 80)
    print()

    tool = RheaReactionLookupTool()

    try:
        # Collect results from different query types
        results = {
            "by_rhea_id":
            await lookup_rhea_reaction("RHEA:15109"),
            "by_ec":
            await lookup_rhea_reaction("2.7.1.1", query_type="ec", limit=5),
            "by_compound":
            await lookup_rhea_reaction("glucose", query_type="compound", limit=5),
        }

        # Save to JSON file
        output_file = Path("data/rhea_demo_results.json")
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"Results saved to: {output_file}")
        print()

        # Show summary
        total_reactions = sum(len(r.get("reactions", [])) for r in results.values())
        print(f"Summary:")
        print(
            f"  - Rhea ID query: {len(results['by_rhea_id']['reactions'])} reaction(s)")
        print(f"  - EC query: {len(results['by_ec']['reactions'])} reaction(s)")
        print(
            f"  - Compound query: {len(results['by_compound']['reactions'])} reaction(s)"
        )
        print(f"  - Total: {total_reactions} reaction(s)")
        print()

    finally:
        await tool.close()


async def print_summary():
    """Print summary of Rhea database capabilities."""

    print("=" * 80)
    print("Summary: Rhea Database Query Capabilities")
    print("=" * 80)
    print()

    print("Query Types:")
    print("  1. By Rhea ID:      get_reaction_by_id('RHEA:15109')")
    print("  2. By EC number:    get_reactions_by_ec('2.7.1.1', limit=10)")
    print("  3. By compound:     search_reactions_by_compound('ATP')")
    print("  4. By ChEBI ID:     search_reactions_by_compound('CHEBI:30616')")
    print()

    print("Returned Information:")
    print("  - Reaction equation (substrates ↔ products)")
    print("  - EC numbers")
    print("  - ChEBI compound IDs and names")
    print("  - UniProt enzyme count")
    print("  - GO terms")
    print("  - PubMed article IDs")
    print("  - Cross-references (KEGG, MetaCyc, EcoCyc, Reactome, M-CSA)")
    print()

    print("Mechanism Information:")
    print("  - PubMed article links (via get_mechanism_links())")
    print("  - M-CSA catalytic mechanism entries")
    print("  - ChEBI stereochemistry data (SMILES, InChIKey)")
    print("  - Rhea web page with detailed publications")
    print()

    print("Use Cases:")
    print("  - Find reaction equations for metabolic pathways")
    print("  - Get cross-references for other databases")
    print("  - Retrieve mechanistic studies from literature")
    print("  - Access stereochemistry information")
    print("  - Build metabolic network models")
    print()


async def main():
    """Run Rhea demonstrations."""

    parser = argparse.ArgumentParser(
        description="Rhea Biochemical Reaction Database Demo")
    parser.add_argument(
        "--section",
        choices=["basic", "mechanism", "advanced", "save", "all", "summary"],
        default="all",
        help="Which section to run (default: all)",
    )

    args = parser.parse_args()

    if args.section == "summary":
        await print_summary()
        return

    if args.section == "basic":
        await demo_basic_queries()
    elif args.section == "mechanism":
        await demo_mechanism_info()
    elif args.section == "advanced":
        await demo_advanced_features()
    elif args.section == "save":
        await save_results()
    else:  # all
        await demo_basic_queries()
        await demo_mechanism_info()
        await demo_advanced_features()
        await save_results()
        await print_summary()


if __name__ == "__main__":
    asyncio.run(main())
