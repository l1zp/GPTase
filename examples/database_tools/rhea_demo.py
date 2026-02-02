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
import logging
from pathlib import Path

from src.tools.base import ToolStatus
from src.tools.external_databases.rhea import lookup_rhea_reaction
from src.tools.external_databases.rhea import RheaReactionLookupTool

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging format and level.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def demo_basic_queries():
    """Demonstrate basic Rhea query capabilities."""

    logger.info("=" * 80)
    logger.info("Part 1: Basic Rhea Queries")
    logger.info("=" * 80)
    logger.info("")

    tool = RheaReactionLookupTool()

    try:
        # 1.1 Query by Rhea ID
        logger.info("1.1 Query by Rhea ID")
        logger.info("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:15109")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]
            logger.info(f"Rhea ID: {reaction['rhea_id']}")
            logger.info(f"Equation: {reaction['equation']}")
            logger.info(f"EC Numbers: {', '.join(reaction['ec_numbers']) or 'N/A'}")
            logger.info(f"Substrates: {', '.join(reaction['substrates'])}")
            logger.info(f"Products: {', '.join(reaction['products'])}")
            logger.info(f"ChEBI Compounds: {len(reaction['chebi_names'])} compounds")
            logger.info(f"UniProt Enzymes: {reaction['uniprot_count']} proteins")
        logger.info("")

        # 1.2 Query by EC number
        logger.info("1.2 Query by EC Number (2.7.1.1 - Hexokinase)")
        logger.info("-" * 80)
        result = await tool.get_reactions_by_ec("2.7.1.1", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            logger.info(f"Found {len(reactions)} reactions:")
            for reaction in reactions:
                logger.info(f"  {reaction['rhea_id']}: {reaction['equation'][:70]}...")
        logger.info("")

        # 1.3 Query by compound name
        logger.info("1.3 Query by Compound Name (ATP)")
        logger.info("-" * 80)
        result = await tool.search_reactions_by_compound("ATP", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            logger.info(f"Found {len(reactions)} reactions involving ATP:")
            for reaction in reactions:
                logger.info(f"  {reaction['rhea_id']}: {reaction['equation'][:70]}...")
        logger.info("")

        # 1.4 Query by ChEBI ID
        logger.info("1.4 Query by ChEBI ID (CHEBI:30616 - ATP)")
        logger.info("-" * 80)
        result = await tool.search_reactions_by_compound("CHEBI:30616", limit=3)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            logger.info(f"Found {len(reactions)} reactions:")
            for reaction in reactions:
                logger.info(f"  {reaction['rhea_id']}: {reaction['equation'][:70]}...")
        logger.info("")

    finally:
        await tool.close()


async def demo_mechanism_info():
    """Demonstrate mechanism information extraction."""

    logger.info("=" * 80)
    logger.info("Part 2: Mechanism Information")
    logger.info("=" * 80)
    logger.info("")

    tool = RheaReactionLookupTool()

    try:
        # 2.1 Chorismate synthase - radical mechanism example
        logger.info("2.1 Chorismate Synthase - Radical Mechanism")
        logger.info("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:21020")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]
            logger.info(f"Reaction: {reaction['equation']}")
            logger.info(f"EC: {', '.join(reaction['ec_numbers'])}")
            logger.info("")

            # Get mechanism links
            links = tool.get_mechanism_links(reaction)

            logger.info("Mechanism Information Sources:")
            logger.info("")
            logger.info("1. Rhea Web Page:")
            logger.info(f"   {links['rhea_web_url']}")
            logger.info("")

            logger.info("2. Mechanistic Studies (PubMed Articles):")
            for article in links["pubmed_articles"][:3]:
                logger.info(f"   - PubMed {article['pubmed_id']}")
                logger.info(f"     {article['url']}")
            if len(links["pubmed_articles"]) > 3:
                logger.info(f"   ... and {len(links['pubmed_articles']) - 3} more")
            logger.info("")

            logger.info("3. Stereochemistry (ChEBI):")
            for compound in links["chebi_compounds"][:3]:
                logger.info(f"   - {compound['chebi_id']}: {compound['chebi_name']}")
                logger.info(f"     SMILES at: {compound['url']}")
            logger.info("")

            if links["mcsa_links"]:
                logger.info("4. Catalytic Mechanism (M-CSA):")
                for mcsa in links["mcsa_links"]:
                    logger.info(f"   - {mcsa['mcsa_id']}")
                    logger.info(f"     {mcsa['url']}")
            else:
                logger.info("4. Catalytic Mechanism (M-CSA):")
                logger.info("   No M-CSA entries available for this reaction")
        logger.info("")

    finally:
        await tool.close()


async def demo_advanced_features():
    """Demonstrate advanced features."""

    logger.info("=" * 80)
    logger.info("Part 3: Advanced Features")
    logger.info("=" * 80)
    logger.info("")

    tool = RheaReactionLookupTool()

    try:
        # 3.1 Cross-references
        logger.info("3.1 Cross-References")
        logger.info("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:15109")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]
            logger.info(f"Reaction: {reaction['rhea_id']}")
            logger.info("")
            logger.info("Cross-references:")
            for db, ids in reaction['xrefs'].items():
                if ids:
                    logger.info(f"  {db}: {', '.join(ids)}")
                else:
                    logger.info(f"  {db}: (not available)")
        logger.info("")

        # 3.2 Convenience function
        logger.info("3.2 Convenience Function")
        logger.info("-" * 80)
        data = await lookup_rhea_reaction("RHEA:10000", query_type="rhea-id")

        if data["reactions"]:
            reaction = data["reactions"][0]
            logger.info(f"Quick lookup: {reaction['rhea_id']}")
            logger.info(f"Equation: {reaction['equation']}")
            logger.info(f"EC: {', '.join(reaction['ec_numbers'])}")
        logger.info("")

        # 3.3 Batch queries
        logger.info("3.3 Batch Query Example")
        logger.info("-" * 80)
        ec_numbers = ["2.7.1.1", "1.1.1.1", "4.2.3.5"]
        all_reactions = []

        for ec in ec_numbers:
            result = await tool.get_reactions_by_ec(ec, limit=2)
            if result.status == ToolStatus.SUCCESS:
                all_reactions.extend(result.data["reactions"])

        logger.info(f"Total reactions found: {len(all_reactions)}")
        for reaction in all_reactions[:5]:
            logger.info(f"  {reaction['rhea_id']}: {reaction['equation'][:60]}...")
        if len(all_reactions) > 5:
            logger.info(f"  ... and {len(all_reactions) - 5} more")
        logger.info("")

    finally:
        await tool.close()


async def save_results():
    """Save query results to file for later analysis."""

    logger.info("=" * 80)
    logger.info("Part 4: Save Results")
    logger.info("=" * 80)
    logger.info("")

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

        logger.info(f"Results saved to: {output_file}")
        logger.info("")

        # Show summary
        total_reactions = sum(len(r.get("reactions", [])) for r in results.values())
        logger.info("Summary:")
        logger.info(
            f"  - Rhea ID query: {len(results['by_rhea_id']['reactions'])} reaction(s)")
        logger.info(f"  - EC query: {len(results['by_ec']['reactions'])} reaction(s)")
        logger.info("  - Compound query: "
                    + f"{len(results['by_compound']['reactions'])} reaction(s)")
        logger.info(f"  - Total: {total_reactions} reaction(s)")
        logger.info("")

    finally:
        await tool.close()


async def print_summary():
    """Print summary of Rhea database capabilities."""

    logger.info("=" * 80)
    logger.info("Summary: Rhea Database Query Capabilities")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Query Types:")
    logger.info("  1. By Rhea ID:      get_reaction_by_id('RHEA:15109')")
    logger.info("  2. By EC number:    get_reactions_by_ec('2.7.1.1', limit=10)")
    logger.info("  3. By compound:     search_reactions_by_compound('ATP')")
    logger.info("  4. By ChEBI ID:     search_reactions_by_compound('CHEBI:30616')")
    logger.info("")

    logger.info("Returned Information:")
    logger.info("  - Reaction equation (substrates <-> products)")
    logger.info("  - EC numbers")
    logger.info("  - ChEBI compound IDs and names")
    logger.info("  - UniProt enzyme count")
    logger.info("  - GO terms")
    logger.info("  - PubMed article IDs")
    logger.info("  - Cross-references (KEGG, MetaCyc, EcoCyc, Reactome, M-CSA)")
    logger.info("")

    logger.info("Mechanism Information:")
    logger.info("  - PubMed article links (via get_mechanism_links())")
    logger.info("  - M-CSA catalytic mechanism entries")
    logger.info("  - ChEBI stereochemistry data (SMILES, InChIKey)")
    logger.info("  - Rhea web page with detailed publications")
    logger.info("")

    logger.info("Use Cases:")
    logger.info("  - Find reaction equations for metabolic pathways")
    logger.info("  - Get cross-references for other databases")
    logger.info("  - Retrieve mechanistic studies from literature")
    logger.info("  - Access stereochemistry information")
    logger.info("  - Build metabolic network models")
    logger.info("")


async def main():
    """Run Rhea demonstrations."""

    setup_logging()

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
