"""KEGG Pathway Database Lookup Demo.

This script demonstrates how to use the KEGGLookupTool to query
pathway and gene information from the KEGG database.

Usage:
    python examples/database_tools/kegg_demo.py
"""

import asyncio
import logging

from src.tools.base import ToolStatus
from src.tools.external_databases.kegg import KEGGLookupTool

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


async def demo_pathway_search():
    """Demonstrate pathway search capabilities."""

    logger.info("=" * 80)
    logger.info("Part 1: Pathway Search")
    logger.info("=" * 80)
    logger.info("")

    tool = KEGGLookupTool()

    try:
        # 1.1 Search by pathway ID
        logger.info("1.1 Search by Pathway ID (Glycolysis)")
        logger.info("-" * 80)
        result = await tool.execute(
            query="map00010",
            query_type="pathway",
            organism="hsa",
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            if pathways:
                pathway = pathways[0]
                logger.info(f"Pathway ID: {pathway.get('pathway_id', 'N/A')}")
                logger.info(f"Name: {pathway.get('name', 'N/A')}")
                logger.info(f"Description: {pathway.get('description', 'N/A')[:80]}...")
                logger.info(f"Genes: {len(pathway.get('genes', []))} genes")
                logger.info(f"Compounds: {len(pathway.get('compounds', []))} compounds")
        logger.info("")

        # 1.2 Search by keyword
        logger.info("1.2 Search by Keyword (glycolysis)")
        logger.info("-" * 80)
        result = await tool.execute(
            query="glycolysis",
            query_type="pathway",
            organism="hsa",
            limit=3,
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            logger.info(f"Found {len(pathways)} pathways:")
            for pathway in pathways:
                logger.info(f"  {pathway.get('pathway_id', 'N/A')}: "
                            + f"{pathway.get('name', 'N/A')[:70]}...")
        logger.info("")

    finally:
        await tool.close()


async def demo_organism_pathways():
    """Demonstrate organism-specific pathway retrieval."""

    logger.info("=" * 80)
    logger.info("Part 2: Organism-Specific Pathways")
    logger.info("=" * 80)
    logger.info("")

    tool = KEGGLookupTool()

    try:
        # 2.1 Human pathways
        logger.info("2.1 Human Pathways (hsa)")
        logger.info("-" * 80)
        result = await tool.execute(
            query="",
            query_type="organism",
            organism="hsa",
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            logger.info(f"Found {len(pathways)} human pathways")
            logger.info("First 5 pathways:")
            for pathway in pathways[:5]:
                logger.info(f"  {pathway.get('pathway_id', 'N/A')}: "
                            + f"{pathway.get('name', 'N/A')[:60]}...")
        logger.info("")

        # 2.2 E. coli pathways
        logger.info("2.2 E. coli Pathways (eco)")
        logger.info("-" * 80)
        result = await tool.execute(
            query="",
            query_type="organism",
            organism="eco",
        )

        if result.status == ToolStatus.SUCCESS:
            pathways = result.data["results"]
            logger.info(f"Found {len(pathways)} E. coli pathways")
            logger.info("First 5 pathways:")
            for pathway in pathways[:5]:
                logger.info(f"  {pathway.get('pathway_id', 'N/A')}: "
                            + f"{pathway.get('name', 'N/A')[:60]}...")
        logger.info("")

    finally:
        await tool.close()


async def demo_gene_search():
    """Demonstrate gene search."""

    logger.info("=" * 80)
    logger.info("Part 3: Gene Search")
    logger.info("=" * 80)
    logger.info("")

    tool = KEGGLookupTool()

    try:
        logger.info("3.1 Search for 'hexokinase' genes in human")
        logger.info("-" * 80)
        result = await tool.execute(
            query="hexokinase",
            query_type="gene",
            organism="hsa",
            limit=5,
        )

        if result.status == ToolStatus.SUCCESS:
            genes = result.data["results"]
            logger.info(f"Found {len(genes)} genes:")
            for gene in genes[:5]:
                logger.info(f"  Gene: {gene.get('gene', 'N/A')}")
        logger.info("")

    finally:
        await tool.close()


async def demo_compound_search():
    """Demonstrate compound search."""

    logger.info("=" * 80)
    logger.info("Part 4: Compound Search")
    logger.info("=" * 80)
    logger.info("")

    tool = KEGGLookupTool()

    try:
        # 4.1 Search by compound name
        logger.info("4.1 Search by Name (glucose)")
        logger.info("-" * 80)
        result = await tool.execute(
            query="glucose",
            query_type="compound",
            limit=3,
        )

        if result.status == ToolStatus.SUCCESS:
            compounds = result.data["results"]
            logger.info(f"Found {len(compounds)} compounds:")
            for compound in compounds:
                logger.info(f"  {compound.get('compound_id', 'N/A')}: "
                            + f"{compound.get('name', 'N/A')}")
        logger.info("")

        # 4.2 Search by compound ID
        logger.info("4.2 Search by ID (C00031 - Glucose)")
        logger.info("-" * 80)
        result = await tool.execute(
            query="C00031",
            query_type="compound",
        )

        if result.status == ToolStatus.SUCCESS:
            compounds = result.data["results"]
            if compounds:
                compound = compounds[0]
                logger.info(f"Compound ID: {compound.get('compound_id', 'N/A')}")
                logger.info(f"Name: {compound.get('name', 'N/A')}")
                logger.info(f"Formula: {compound.get('formula', 'N/A')}")
                logger.info(f"Exact Mass: {compound.get('exact_mass', 'N/A')}")
                logger.info(
                    f"Molecular Weight: {compound.get('molecular_weight', 'N/A')}")
        logger.info("")

    finally:
        await tool.close()


async def demo_pathway_details():
    """Demonstrate getting detailed pathway information."""

    logger.info("=" * 80)
    logger.info("Part 5: Pathway Details - Genes, Reactions, Compounds")
    logger.info("=" * 80)
    logger.info("")

    tool = KEGGLookupTool()

    try:
        pathway_id = "map00010"  # Glycolysis

        logger.info(f"5.1 Genes in {pathway_id} (Glycolysis)")
        logger.info("-" * 80)
        result = await tool.get_pathway_genes(pathway_id)

        if result.status == ToolStatus.SUCCESS:
            genes = result.data["genes"]
            logger.info(f"Found {len(genes)} genes:")
            for gene in genes[:10]:
                logger.info(f"  {gene.get('gene', 'N/A')}")
            if len(genes) > 10:
                logger.info(f"  ... and {len(genes) - 10} more genes")
        logger.info("")

        logger.info(f"5.2 Reactions in {pathway_id}")
        logger.info("-" * 80)
        result = await tool.get_pathway_reactions(pathway_id)

        if result.status == ToolStatus.SUCCESS:
            reactions = result.data["reactions"]
            logger.info(f"Found {len(reactions)} reactions:")
            for reaction in reactions[:5]:
                logger.info(f"  {reaction.get('reaction', 'N/A')}")
            if len(reactions) > 5:
                logger.info(f"  ... and {len(reactions) - 5} more reactions")
        logger.info("")

        logger.info(f"5.3 Compounds in {pathway_id}")
        logger.info("-" * 80)
        result = await tool.get_pathway_compounds(pathway_id)

        if result.status == ToolStatus.SUCCESS:
            compounds = result.data["compounds"]
            logger.info(f"Found {len(compounds)} compounds:")
            for compound in compounds[:10]:
                logger.info(f"  {compound.get('compound_id', 'N/A')}: "
                            + f"{compound.get('name', 'N/A')}")
            if len(compounds) > 10:
                logger.info(f"  ... and {len(compounds) - 10} more compounds")
        logger.info("")

    finally:
        await tool.close()


async def print_summary():
    """Print summary of KEGG capabilities."""

    logger.info("=" * 80)
    logger.info("Summary: KEGG Database Query Capabilities")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Query Types:")
    logger.info("  1. Pathway:      get_pathway_by_id('map00010')")
    logger.info("  2. Organism:    get_organism_pathways('hsa')")
    logger.info("  3. Gene:        search_genes('hexokinase', organism='hsa')")
    logger.info("  4. Compound:    search_compounds('glucose')")
    logger.info("")

    logger.info("Detailed Information:")
    logger.info("  - Pathway genes:      get_pathway_genes('map00010')")
    logger.info("  - Pathway reactions:  get_pathway_reactions('map00010')")
    logger.info("  - Pathway compounds:  get_pathway_compounds('map00010')")
    logger.info("")

    logger.info("Common Organism Codes:")
    logger.info("  - hsa: Homo sapiens (human)")
    logger.info("  - eco: Escherichia coli")
    logger.info("  - mmu: Mus musculus (mouse)")
    logger.info("  - sce: Saccharomyces cerevisiae (yeast)")
    logger.info("  - dre: Danio rerio (zebrafish)")
    logger.info("")

    logger.info("Use Cases:")
    logger.info("  - Find all genes in a metabolic pathway")
    logger.info("  - Get organism-specific pathways")
    logger.info("  - Retrieve reaction and compound information")
    logger.info("  - Build metabolic network models")
    logger.info("")


async def main():
    """Run KEGG demonstrations."""

    setup_logging()
    logger.info("")
    logger.info("=" * 80)
    logger.info("KEGG Pathway Database Demo")
    logger.info("=" * 80)
    logger.info("")

    await demo_pathway_search()
    await demo_organism_pathways()
    await demo_gene_search()
    await demo_compound_search()
    await demo_pathway_details()
    await print_summary()

    logger.info("=" * 80)
    logger.info("Demo completed!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
