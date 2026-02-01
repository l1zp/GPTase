"""Rhea Reaction Mechanism Information Demo.

This script demonstrates how to extract mechanism-related information
from Rhea reactions, including:
- Links to mechanistic studies (PubMed articles)
- Catalytic mechanism information (M-CSA)
- Stereochemistry data (ChEBI)
- Direct access to reaction details

Usage:
    python examples/rhea_mechanism_demo.py
"""

import asyncio
from src.tools.external_databases.rhea import RheaReactionLookupTool
from src.tools.base import ToolStatus


async def main():
    """Demonstrate mechanism information extraction from Rhea."""

    print("=" * 80)
    print("Rhea Reaction Mechanism Information Demo")
    print("=" * 80)
    print()

    tool = RheaReactionLookupTool()

    try:
        # Example 1: Chorismate synthase (radical mechanism)
        print("Example 1: Chorismate Synthase - Radical Mechanism")
        print("-" * 80)
        result = await tool.get_reaction_by_id("RHEA:21020")

        if result.status == ToolStatus.SUCCESS:
            reaction = result.data["reactions"][0]

            print(f"Reaction: {reaction['equation']}")
            print(f"EC: {', '.join(reaction['ec_numbers'])}")
            print()

            # Get mechanism-related links
            links = tool.get_mechanism_links(reaction)

            print("Mechanism Information Sources:")
            print()

            # Rhea web page
            print(f"1. Rhea Web Page (detailed publications):")
            print(f"   {links['rhea_web_url']}")
            print()

            # PubMed articles
            print(f"2. Mechanistic Studies (PubMed Articles):")
            for article in links["pubmed_articles"][:3]:  # Show first 3
                print(f"   - PubMed {article['pubmed_id']}:")
                print(f"     {article['url']}")
            if len(links["pubmed_articles"]) > 3:
                print(f"   ... and {len(links['pubmed_articles']) - 3} more articles")
            print()

            # ChEBI compounds (stereochemistry)
            print(f"3. Stereochemistry & Molecular Structure (ChEBI):")
            for compound in links["chebi_compounds"][:3]:
                print(f"   - {compound['chebi_name']}:")
                print(f"     {compound['url']}")
            print()

            # M-CSA (if available)
            if links["mcsa_links"]:
                print(f"4. Catalytic Mechanism (M-CSA):")
                for mcsa in links["mcsa_links"]:
                    print(f"   - {mcsa['mcsa_id']}:")
                    print(f"     {mcsa['url']}")
                print()
            else:
                print("4. Catalytic Mechanism (M-CSA):")
                print("   No M-CSA entries available for this reaction")
                print()
        print()

        # Example 2: Reaction with M-CSA data
        print("Example 2: Searching for Reactions with Catalytic Mechanism Data")
        print("-" * 80)
        result = await tool.get_reactions_by_ec("3.2.1.1", limit=10)

        if result.status == ToolStatus.SUCCESS:
            reactions_with_mcsa = []
            for r in result.data["reactions"]:
                links = tool.get_mechanism_links(r)
                if links["mcsa_links"]:
                    reactions_with_mcsa.append((r, links))

            if reactions_with_mcsa:
                print(f"Found {len(reactions_with_mcsa)} reactions with M-CSA data:")
                for reaction, links in reactions_with_mcsa[:3]:
                    print(f"  - {reaction['rhea_id']}: {reaction['equation'][:60]}...")
                    for mcsa in links["mcsa_links"]:
                        print(f"    {mcsa['url']}")
            else:
                print("No reactions with M-CSA data found in this batch")
                print("Try searching different EC numbers")
        print()

        # Example 3: Stereochemistry information
        print("Example 3: Extracting Stereochemistry Information")
        print("-" * 80)
        result = await tool.search_reactions_by_compound("chorismate", limit=3)

        if result.status == ToolStatus.SUCCESS:
            for reaction in result.data["reactions"]:
                print(f"Reaction: {reaction['equation']}")
                links = tool.get_mechanism_links(reaction)

                print("ChEBI entries with stereochemistry:")
                for compound in links["chebi_compounds"]:
                    print(f"  - {compound['chebi_id']}: {compound['chebi_name']}")
                    print(f"    SMILES and InChIKey available at: {compound['url']}")
                print()
        print()

        # Summary
        print("=" * 80)
        print("Summary: Mechanism Information Sources")
        print("=" * 80)
        print()
        print("1. Rhea Web Pages:")
        print("   - Provide curated publications with mechanistic insights")
        print("   - Include detailed experimental evidence")
        print("   - Example: https://www.rhea-db.org/21020")
        print()
        print("2. PubMed Articles:")
        print("   - Primary literature on reaction mechanisms")
        print("   - Kinetic isotope effects, transition state studies")
        print("   - Stereochemistry and mutagenesis experiments")
        print()
        print("3. M-CSA (Catalytic Site Atlas):")
        print("   - Detailed catalytic residue information")
        print("   - Reaction mechanism diagrams")
        print("   - Transition state analog structures")
        print("   - URL: https://www.ebi.ac.uk/thornton-srv/m-csa/")
        print()
        print("4. ChEBI:")
        print("   - Stereochemistry (SMILES with @ and @@)")
        print("   - Molecular coordinates (Mol files)")
        print("   - InChIKey with stereochemistry layers")
        print("   - URL: https://www.ebi.ac.uk/chebi/")
        print()
        print("5. Note: Rhea does NOT provide:")
        print("   - Direct transition state structures")
        print("   - Energy barriers or activation energies")
        print("   - Atom-atom mapping (available in RXN/RD files only)")
        print("   - Reaction intermediate structures")
        print("   For these, use specialized databases like M-CSA or computational tools")
        print()

    finally:
        await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
