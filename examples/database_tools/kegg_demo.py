"""KEGG Pathway Database Lookup Demo.

This script demonstrates how to use the KEGGLookupTool to query
pathway and gene information from the KEGG database.

Usage:
    python examples/database_tools/kegg_demo.py
"""

import asyncio

from src.tools.base import ToolStatus
from src.tools.external_databases.kegg import KEGGLookupTool


async def demo_pathway_search():
    """Demonstrate pathway search capabilities."""

    print("=" * 80)
    print("Part 1: Pathway Search")
    print("=" * 80)
    print()

    tool = KEGGLookupTool()

    try:
        # 1.1 Search by pathway ID
        print("1.1 Search by Pathway ID (Glycolysis)")
        print("-" * 80)
        result = await tool.execute(
            query="map00010",
            query_type="pathway",
            organism="hsa",
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            if pathways:
                pathway = pathways[0]
                print(f"Pathway ID: {pathway.get('pathway_id', 'N/A')}")
                print(f"Name: {pathway.get('name', 'N/A')}")
                print(f"Description: {pathway.get('description', 'N/A')[:80]}...")
                print(f"Genes: {len(pathway.get('genes', []))} genes")
                print(f"Compounds: {len(pathway.get('compounds', []))} compounds")
        print()

        # 1.2 Search by keyword
        print("1.2 Search by Keyword (glycolysis)")
        print("-" * 80)
        result = await tool.execute(
            query="glycolysis",
            query_type="pathway",
            organism="hsa",
            limit=3,
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            print(f"Found {len(pathways)} pathways:")
            for pathway in pathways:
                print(
                    f"  {pathway.get('pathway_id', 'N/A')}: {pathway.get('name', 'N/A')[:70]}..."
                )
        print()

    finally:
        await tool.close()


async def demo_organism_pathways():
    """Demonstrate organism-specific pathway retrieval."""

    print("=" * 80)
    print("Part 2: Organism-Specific Pathways")
    print("=" * 80)
    print()

    tool = KEGGLookupTool()

    try:
        # 2.1 Human pathways
        print("2.1 Human Pathways (hsa)")
        print("-" * 80)
        result = await tool.execute(
            query="",
            query_type="organism",
            organism="hsa",
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            print(f"Found {len(pathways)} human pathways")
            print("First 5 pathways:")
            for pathway in pathways[:5]:
                print(
                    f"  {pathway.get('pathway_id', 'N/A')}: {pathway.get('name', 'N/A')[:60]}..."
                )
        print()

        # 2.2 E. coli pathways
        print("2.2 E. coli Pathways (eco)")
        print("-" * 80)
        result = await tool.execute(
            query="",
            query_type="organism",
            organism="eco",
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            print(f"Found {len(pathways)} E. coli pathways")
            print("First 5 pathways:")
            for pathway in pathways[:5]:
                print(
                    f"  {pathway.get('pathway_id', 'N/A')}: {pathway.get('name', 'N/A')[:60]}..."
                )
        print()

    finally:
        await tool.close()


async def demo_gene_search():
    """Demonstrate gene search."""

    print("=" * 80)
    print("Part 3: Gene Search")
    print("=" * 80)
    print()

    tool = KEGGLookupTool()

    try:
        print("3.1 Search for 'hexokinase' genes in human")
        print("-" * 80)
        result = await tool.execute(
            query="hexokinase",
            query_type="gene",
            organism="hsa",
            limit=5,
        )

        if result.status == ToolStatus.SUCCESS:
            genes = result.data["results"]
            print(f"Found {len(genes)} genes:")
            for gene in genes[:5]:
                print(f"  Gene: {gene.get('gene', 'N/A')}")
        print()

    finally:
        await tool.close()


async def demo_compound_search():
    """Demonstrate compound search."""

    print("=" * 80)
    print("Part 4: Compound Search")
    print("=" * 80)
    print()

    tool = KEGGLookupTool()

    try:
        # 4.1 Search by compound name
        print("4.1 Search by Name (glucose)")
        print("-" * 80)
        result = await tool.execute(
            query="glucose",
            query_type="compound",
            limit=3,
        )

        if result.status == ToolStatus.SUCCESS:
            compounds = result.data["results"]
            print(f"Found {len(compounds)} compounds:")
            for compound in compounds:
                print(
                    f"  {compound.get('compound_id', 'N/A')}: {compound.get('name', 'N/A')}"
                )
        print()

        # 4.2 Search by compound ID
        print("4.2 Search by ID (C00031 - Glucose)")
        print("-" * 80)
        result = await tool.execute(
            query="C00031",
            query_type="compound",
        )

        if result.status == ToolStatus.SUCCESS:
            compounds = result.data["results"]
            if compounds:
                compound = compounds[0]
                print(f"Compound ID: {compound.get('compound_id', 'N/A')}")
                print(f"Name: {compound.get('name', 'N/A')}")
                print(f"Formula: {compound.get('formula', 'N/A')}")
                print(f"Exact Mass: {compound.get('exact_mass', 'N/A')}")
                print(f"Molecular Weight: {compound.get('molecular_weight', 'N/A')}")
        print()

    finally:
        await tool.close()


async def demo_pathway_details():
    """Demonstrate getting detailed pathway information."""

    print("=" * 80)
    print("Part 5: Pathway Details - Genes, Reactions, Compounds")
    print("=" * 80)
    print()

    tool = KEGGLookupTool()

    try:
        pathway_id = "map00010"  # Glycolysis

        print(f"5.1 Genes in {pathway_id} (Glycolysis)")
        print("-" * 80)
        result = await tool.get_pathway_genes(pathway_id)

        if result.status == ToolStatus.SUCCESS:
            genes = result.data["genes"]
            print(f"Found {len(genes)} genes:")
            for gene in genes[:10]:
                print(f"  {gene.get('gene', 'N/A')}")
            if len(genes) > 10:
                print(f"  ... and {len(genes) - 10} more genes")
        print()

        print(f"5.2 Reactions in {pathway_id}")
        print("-" * 80)
        result = await tool.get_pathway_reactions(pathway_id)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            print(f"Found {len(reactions)} reactions:")
            for reaction in reactions[:5]:
                print(f"  {reaction.get('reaction', 'N/A')}")
            if len(reactions) > 5:
                print(f"  ... and {len(reactions) - 5} more reactions")
        print()

        print(f"5.3 Compounds in {pathway_id}")
        print("-" * 80)
        result = await tool.get_pathway_compounds(pathway_id)

        if result.status == ToolStatus.SUCCESS:
            compounds = result.data["compounds"]
            print(f"Found {len(compounds)} compounds:")
            for compound in compounds[:10]:
                print(
                    f"  {compound.get('compound_id', 'N/A')}: {compound.get('name', 'N/A')}"
                )
            if len(compounds) > 10:
                print(f"  ... and {len(compounds) - 10} more compounds")
        print()

    finally:
        await tool.close()


async def print_summary():
    """Print summary of KEGG capabilities."""

    print("=" * 80)
    print("Summary: KEGG Database Query Capabilities")
    print("=" * 80)
    print()

    print("Query Types:")
    print("  1. Pathway:      get_pathway_by_id('map00010')")
    print("  2. Organism:    get_organism_pathways('hsa')")
    print("  3. Gene:        search_genes('hexokinase', organism='hsa')")
    print("  4. Compound:    search_compounds('glucose')")
    print()

    print("Detailed Information:")
    print("  - Pathway genes:      get_pathway_genes('map00010')")
    print("  - Pathway reactions:  get_pathway_reactions('map00010')")
    print("  - Pathway compounds:  get_pathway_compounds('map00010')")
    print()

    print("Common Organism Codes:")
    print("  - hsa: Homo sapiens (human)")
    print("  - eco: Escherichia coli")
    print("  - mmu: Mus musculus (mouse)")
    print("  - sce: Saccharomyces cerevisiae (yeast)")
    print("  - dre: Danio rerio (zebrafish)")
    print()

    print("Use Cases:")
    print("  - Find all genes in a metabolic pathway")
    print("  - Get organism-specific pathways")
    print("  - Retrieve reaction and compound information")
    print("  - Build metabolic network models")
    print()


async def main():
    """Run KEGG demonstrations."""

    print("\n" + "=" * 80)
    print("KEGG Pathway Database Demo")
    print("=" * 80)
    print()

    await demo_pathway_search()
    await demo_organism_pathways()
    await demo_gene_search()
    await demo_compound_search()
    await demo_pathway_details()
    await print_summary()

    print("=" * 80)
    print("Demo completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
