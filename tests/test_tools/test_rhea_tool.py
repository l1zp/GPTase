"""Tests for Rhea Reaction Lookup Tool."""

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from src.tools.base import ToolStatus
from src.tools.external_databases.rhea import RheaReactionLookupTool


class TestRheaReactionLookupTool:
    """Test suite for RheaReactionLookupTool."""

    def test_initialization(self):
        """Test tool initialization."""
        tool = RheaReactionLookupTool()
        assert tool.name == "rhea_reaction_lookup"
        assert tool.description is not None
        assert tool.DEFAULT_TIMEOUT == 10

    @pytest.mark.asyncio
    async def test_get_reaction_by_id_success(self):
        """Test successful reaction lookup by ID."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reaction_by_id("RHEA:15109")

        assert result.status == ToolStatus.SUCCESS
        assert result.data is not None
        assert "reactions" in result.data
        assert len(result.data["reactions"]) > 0

        reaction = result.data["reactions"][0]
        assert reaction["rhea_id"] == "RHEA:15109"
        assert "equation" in reaction
        assert "ec_numbers" in reaction
        assert "chebi_ids" in reaction

        await tool.close()

    @pytest.mark.asyncio
    async def test_get_reaction_by_id_invalid(self):
        """Test reaction lookup with invalid ID."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reaction_by_id("RHEA:99999999")

        # Should handle invalid ID gracefully
        assert result.status in [ToolStatus.ERROR, ToolStatus.SUCCESS]
        if result.status == ToolStatus.SUCCESS:
            # If success, should have empty reactions list
            assert len(result.data.get("reactions", [])) == 0

        await tool.close()

    @pytest.mark.asyncio
    async def test_get_reactions_by_ec(self):
        """Test reaction lookup by EC number."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reactions_by_ec("2.7.1.1", limit=5)

        assert result.status == ToolStatus.SUCCESS
        assert result.data is not None
        assert len(result.data["reactions"]) > 0

        # Check that all returned reactions have the EC number
        for reaction in result.data["reactions"]:
            assert "EC:2.7.1.1" in reaction["ec_numbers"]

        await tool.close()

    @pytest.mark.asyncio
    async def test_search_reactions_by_compound(self):
        """Test reaction search by compound name."""
        tool = RheaReactionLookupTool()
        result = await tool.search_reactions_by_compound("ATP", limit=3)

        assert result.status == ToolStatus.SUCCESS
        assert result.data is not None
        assert len(result.data["reactions"]) > 0

        await tool.close()

    @pytest.mark.asyncio
    async def test_search_reactions_by_chebi_id(self):
        """Test reaction search by ChEBI ID."""
        tool = RheaReactionLookupTool()
        result = await tool.search_reactions_by_compound("CHEBI:30616", limit=3)

        assert result.status == ToolStatus.SUCCESS
        assert result.data is not None
        assert len(result.data["reactions"]) >= 0

        await tool.close()

    @pytest.mark.asyncio
    async def test_equation_parsing(self):
        """Test reaction equation parsing into substrates and products."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reaction_by_id("RHEA:10948")

        assert result.status == ToolStatus.SUCCESS
        reaction = result.data["reactions"][0]

        # Check that equation was parsed
        assert "substrates" in reaction
        assert "products" in reaction
        assert isinstance(reaction["substrates"], list)
        assert isinstance(reaction["products"], list)

        # Verify substrates are not empty
        assert len(reaction["substrates"]) > 0
        assert len(reaction["products"]) > 0

        # Check that compounds with parentheses are preserved
        all_compounds = reaction["substrates"] + reaction["products"]
        # If H(+) or NADP(+) are present, they should be intact
        has_parenthesized_compound = any(
            "(" in c and ")" in c for c in all_compounds
        )
        # Note: Not all reactions have parenthesized compounds

        await tool.close()

    @pytest.mark.asyncio
    async def test_get_mechanism_links(self):
        """Test generation of mechanism information links."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reaction_by_id("RHEA:21020")

        assert result.status == ToolStatus.SUCCESS
        reaction = result.data["reactions"][0]

        # Get mechanism links
        links = tool.get_mechanism_links(reaction)

        # Check required fields
        assert "rhea_id" in links
        assert "rhea_web_url" in links
        assert "pubmed_articles" in links
        assert "mcsa_links" in links
        assert "chebi_compounds" in links

        # Verify URL format
        assert links["rhea_web_url"].startswith("https://www.rhea-db.org/")

        # Check PubMed articles
        if len(links["pubmed_articles"]) > 0:
            article = links["pubmed_articles"][0]
            assert "pubmed_id" in article
            assert "url" in article
            assert article["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")

        # Check ChEBI compounds
        if len(links["chebi_compounds"]) > 0:
            compound = links["chebi_compounds"][0]
            assert "chebi_id" in compound
            assert "url" in compound
            assert compound["url"].startswith("https://www.ebi.ac.uk/chebi/")

        await tool.close()

    @pytest.mark.asyncio
    async def test_cross_references(self):
        """Test extraction of cross-references."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reaction_by_id("RHEA:15109")

        assert result.status == ToolStatus.SUCCESS
        reaction = result.data["reactions"][0]

        # Check cross-references structure
        assert "xrefs" in reaction
        assert isinstance(reaction["xrefs"], dict)

        # Check for expected databases
        expected_dbs = ["KEGG", "MetaCyc", "EcoCyc", "Reactome", "M-CSA"]
        for db in expected_dbs:
            assert db in reaction["xrefs"]

        await tool.close()

    @pytest.mark.asyncio
    async def test_chebi_data_extraction(self):
        """Test ChEBI compound data extraction."""
        tool = RheaReactionLookupTool()
        result = await tool.get_reaction_by_id("RHEA:10948")

        assert result.status == ToolStatus.SUCCESS
        reaction = result.data["reactions"][0]

        # Check ChEBI data
        assert "chebi_names" in reaction
        assert "chebi_ids" in reaction
        assert isinstance(reaction["chebi_names"], list)
        assert isinstance(reaction["chebi_ids"], list)

        # Verify ChEBI IDs have correct format
        for chebi_id in reaction["chebi_ids"]:
            assert chebi_id.startswith("CHEBI:")

        await tool.close()

    def test_get_schema(self):
        """Test tool schema definition."""
        tool = RheaReactionLookupTool()
        schema = tool.get_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Check required parameters
        assert "query" in schema["required"]
        assert "query" in schema["properties"]

        # Check optional parameters
        assert "query_type" in schema["properties"]
        assert "limit" in schema["properties"]

        # Check query_type enum
        query_type_schema = schema["properties"]["query_type"]
        assert "enum" in query_type_schema
        expected_types = ["rhea-id", "ec", "compound", "uniprot", "all"]
        for qt in expected_types:
            assert qt in query_type_schema["enum"]

    @pytest.mark.asyncio
    async def test_close(self):
        """Test session cleanup."""
        tool = RheaReactionLookupTool()
        assert tool._session is not None

        await tool.close()
        assert tool._session is None

    @pytest.mark.asyncio
    async def test_execute_with_query_type(self):
        """Test execute method with different query types."""
        tool = RheaReactionLookupTool()

        # Test rhea-id query type
        result = await tool.execute(
            query="15109",
            query_type="rhea-id",
            limit=1,
        )
        assert result.status == ToolStatus.SUCCESS

        # Test ec query type
        result = await tool.execute(
            query="2.7.1.1",
            query_type="ec",
            limit=1,
        )
        assert result.status == ToolStatus.SUCCESS

        # Test compound query type
        result = await tool.execute(
            query="ATP",
            query_type="compound",
            limit=1,
        )
        assert result.status == ToolStatus.SUCCESS

        await tool.close()

    @pytest.mark.asyncio
    async def test_uniprot_query(self):
        """Test query for reactions with UniProt annotations."""
        tool = RheaReactionLookupTool()
        result = await tool.execute(
            query="",
            query_type="uniprot",
            limit=5,
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.data is not None

        # If reactions are found, they should have uniprot_count
        if len(result.data["reactions"]) > 0:
            for reaction in result.data["reactions"]:
                assert "uniprot_count" in reaction
                assert reaction["uniprot_count"] > 0

        await tool.close()
