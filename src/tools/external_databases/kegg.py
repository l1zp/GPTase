"""KEGG Pathway Database Lookup Tool.

This tool searches the KEGG (Kyoto Encyclopedia of Genes and Genomes) database for:
- Metabolic pathways
- Pathway maps and reactions
- Genes and enzymes in pathways
- Organism-specific pathways
- Cross-references between genes and pathways

KEGG Database: https://www.genome.jp/kegg/
KEGG API: https://www.kegg.jp/kegg/rest/keggapi.html
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.base import ToolStatus
from src.tools.external_databases.base import BaseAPITool

logger = logging.getLogger(__name__)

# KEGG organism code pattern (3-4 letters)
ORGANISM_PATTERN = re.compile(r"^[a-z]{3,4}$", re.IGNORECASE)

# KEGG pathway ID pattern (5 digits)
PATHWAY_PATTERN = re.compile(r"^map\d{5}$", re.IGNORECASE)


class KEGGLookupTool(BaseAPITool):
    """Tool for looking up pathway and gene information from KEGG database.

    This tool uses the KEGG REST API to:
    1. Search for pathways by name or ID
    2. Get pathway maps and reactions
    3. Retrieve genes and enzymes in pathways
    4. Find organism-specific pathways
    5. Get cross-references between genes and pathways

    Database: https://www.genome.jp/kegg/
    API: https://rest.kegg.jp/kegg/rest/
    """

    TOOL_NAME = "kegg_lookup"

    # KEGG REST API endpoints
    KEGG_BASE_URL = "https://rest.kegg.jp"

    # Request timeout (seconds)
    DEFAULT_TIMEOUT = 10

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF = 0.5

    # Rate limiting (KEGG API requests should be spaced out)
    RATE_LIMIT_DELAY = 1.0  # 1 second between requests

    def __init__(self):
        """Initialize KEGG Lookup Tool."""
        super().__init__(base_url=self.KEGG_BASE_URL)

    def _extract_field_value(self, line: str, field_name: str) -> str:
        """Extract field value from KEGG flat file format line.

        Args:
            line: Line from KEGG flat file
            field_name: Name of the field (e.g., "ENTRY", "NAME")

        Returns:
            Field value after the field name, or empty string if not found
        """
        parts = line.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""

    def _tsv_row_to_dict(self, row: List[str], key_name: str,
                         value_name: str) -> Dict[str, str]:
        """Convert TSV row to dictionary with safe indexing.

        Args:
            row: List of string values from TSV
            key_name: Name for the first column
            value_name: Name for the second column

        Returns:
            Dictionary with key and value
        """
        return {
            key_name: row[0] if len(row) > 0 else "",
            value_name: row[1] if len(row) > 1 else "",
        }

    async def execute(
        self,
        query: str,
        query_type: str = "pathway",
        organism: str = "",
        limit: int = 10,
    ) -> ToolResult:
        """Execute KEGG lookup.

        Args:
            query: Search query (pathway ID, pathway name, gene, etc.)
            query_type: Type of query:
                - "pathway": Search pathways by name or ID (default)
                - "organism": Search organism-specific pathways
                - "gene": Search genes by name or ID
                - "compound": Search compounds by name or ID
            organism: Organism code (e.g., "hsa" for human)
            limit: Maximum number of results

        Returns:
            ToolResult with data containing:
                {
                    "query": str,
                    "query_type": str,
                    "results": [...],
                    "summary": {
                        "total_found": int,
                        "returned": int
                    }
                }
        """
        start_time = time.time()

        try:
            if query_type == "pathway":
                results = await self._search_pathways(query, organism, limit)
            elif query_type == "organism":
                results = await self._search_organism_pathways(organism)
            elif query_type == "gene":
                results = await self._search_genes(query, organism, limit)
            elif query_type == "compound":
                results = await self._search_compounds(query, limit)
            else:
                return ToolResult.from_error(f"Unknown query type: {query_type}")

            execution_time = time.time() - start_time

            return ToolResult.success(
                data={
                    "query": query,
                    "query_type": query_type,
                    "results": results,
                    "summary": {
                        "total_found": len(results),
                        "returned": len(results),
                    },
                },
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"KEGG query failed: {e}", exc_info=True)
            return ToolResult.from_error(
                error_message=f"KEGG query failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    async def _search_pathways(
        self,
        query: str,
        organism: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for pathways.

        Args:
            query: Pathway ID (e.g., "map00010") or pathway name
            organism: Organism code (optional)
            limit: Maximum results

        Returns:
            List of pathway dictionaries
        """
        try:
            # Check if query is a pathway ID
            if PATHWAY_PATTERN.match(query.upper()):
                # Get specific pathway (use lowercase for KEGG API)
                endpoint = f"get/{query.lower()}"
                return [await self._get_pathway_details(endpoint)]

            # Search by keyword
            else:
                organism_path = f"/{organism}" if organism else ""
                endpoint = f"list/pathway{organism_path}"
                response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
                pathways = self._parse_tsv_response(response)

                # Filter by keyword
                keyword = query.lower()
                filtered = [
                    p for p in pathways
                    if keyword in p[0].lower() or keyword in p[1].lower()
                ]

                return [
                    self._tsv_row_to_dict(p, "pathway_id", "name")
                    for p in filtered[:limit]
                ]

        except Exception as e:
            logger.error(f"Pathway search failed: {e}")
            return []

    async def _get_pathway_details(self, endpoint: str) -> Dict[str, Any]:
        """Get detailed information about a pathway.

        Args:
            endpoint: API endpoint for pathway details

        Returns:
            Pathway dictionary
        """
        try:
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            lines = response.text.strip().split("\n")

            if len(lines) < 2:
                return {}

            # Parse KEGG flat file format
            pathway = {}
            genes = []
            compounds = []

            for line in lines[1:]:  # Skip first line (ENTRY field)
                line = line.rstrip()
                if not line:
                    continue

                # Parse sections: ENTRY, NAME, DESCRIPTION, etc.
                if line.startswith("ENTRY"):
                    pathway["pathway_id"] = line.split()[-1]
                elif line.startswith("NAME"):
                    pathway["name"] = self._extract_field_value(line, "NAME")
                elif line.startswith("DESCRIPTION"):
                    pathway["description"] = self._extract_field_value(
                        line, "DESCRIPTION")
                elif line.startswith("ORGANISM"):
                    pathway["organism"] = self._extract_field_value(line, "ORGANISM")
                elif line.startswith("GENE"):
                    gene_id = line.split()[-1]
                    genes.append(gene_id)
                elif line.startswith("COMPOUND"):
                    compound_id = line.split()[-1]
                    compounds.append(compound_id)

            pathway["genes"] = genes
            pathway["compounds"] = compounds

            return pathway

        except Exception as e:
            logger.error(f"Failed to get pathway details: {e}")
            return {}

    async def _search_organism_pathways(self, organism: str) -> List[Dict[str, Any]]:
        """Get all pathways for a specific organism.

        Args:
            organism: KEGG organism code (e.g., "hsa", "eco")

        Returns:
            List of pathway dictionaries
        """
        try:
            if not ORGANISM_PATTERN.match(organism):
                logger.warning(f"Invalid organism code: {organism}")
                return []

            endpoint = f"list/pathway/{organism}"
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            tsv_data = self._parse_tsv_response(response)

            return [
                self._tsv_row_to_dict(row, "pathway_id", "name") for row in tsv_data
            ]

        except Exception as e:
            logger.error(f"Organism pathway search failed: {e}")
            return []

    async def _search_genes(
        self,
        query: str,
        organism: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for genes.

        Args:
            query: Gene name or identifier
            organism: Organism code (optional)
            limit: Maximum results

        Returns:
            List of gene dictionaries
        """
        try:
            if not organism:
                return []

            endpoint = f"find/{organism}/{query}"
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            tsv_data = self._parse_tsv_response(response)

            return [
                self._tsv_row_to_dict(row, "gene", "name") for row in tsv_data[:limit]
            ]

        except Exception as e:
            logger.error(f"Gene search failed: {e}")
            return []

    async def _search_compounds(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for compounds.

        Args:
            query: Compound name or ID (e.g., "C00031", "glucose")
            limit: Maximum results

        Returns:
            List of compound dictionaries
        """
        try:
            # Check if query is a compound ID
            if query.upper().startswith("C") and len(query) > 1:
                # Get specific compound
                endpoint = f"get/{query.upper()}"
                response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
                return [self._parse_compound_entry(response.text)]

            # Search by keyword
            endpoint = f"find/compound/{query}"
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            tsv_data = self._parse_tsv_response(response)

            return [
                self._tsv_row_to_dict(row, "compound_id", "name")
                for row in tsv_data[:limit]
            ]

        except Exception as e:
            logger.error(f"Compound search failed: {e}")
            return []

    def _parse_compound_entry(self, text: str) -> Dict[str, Any]:
        """Parse a compound entry from KEGG flat file format.

        Args:
            text: KEGG compound entry text

        Returns:
            Compound dictionary
        """
        try:
            lines = text.strip().split("\n")
            compound = {}

            for line in lines:
                if line.startswith("ENTRY"):
                    compound["compound_id"] = line.split()[-1]
                elif line.startswith("NAME"):
                    compound["name"] = self._extract_field_value(line, "NAME")
                elif line.startswith("FORMULA"):
                    compound["formula"] = self._extract_field_value(line, "FORMULA")
                elif line.startswith("EXACT_MASS"):
                    compound["exact_mass"] = self._extract_field_value(
                        line, "EXACT_MASS")
                elif line.startswith("MOL_WEIGHT"):
                    compound["molecular_weight"] = self._extract_field_value(
                        line, "MOL_WEIGHT")
                elif line.startswith("REMARK"):
                    compound["remark"] = self._extract_field_value(line, "REMARK")
                elif line.startswith("ENZYME"):
                    compound["enzyme"] = self._extract_field_value(line, "ENZYME")

            return compound

        except Exception as e:
            logger.error(f"Failed to parse compound entry: {e}")
            return {}

    def _parse_tsv_response(self, response: requests.Response) -> List[List[str]]:
        """Parse TSV response from KEGG API.

        Args:
            response: requests.Response object

        Returns:
            List of rows (each row is a list of string values)
        """
        try:
            lines = response.text.strip().split("\n")

            if len(lines) < 1:
                return []

            results = []
            for line in lines:
                if not line.strip():
                    continue
                values = line.split("\t")
                results.append(values)

            return results

        except Exception as e:
            logger.error(f"Failed to parse TSV response: {e}")
            return []

    async def get_pathway_genes(self, pathway_id: str) -> ToolResult:
        """Get all genes in a pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g., "map00010")

        Returns:
            ToolResult with gene list
        """
        try:
            endpoint = f"link/hsa/{pathway_id}"
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            tsv_data = self._parse_tsv_response(response)

            genes = [self._tsv_row_to_dict(row, "gene", "pathway") for row in tsv_data]

            return ToolResult.success(data={"pathway_id": pathway_id, "genes": genes})

        except Exception as e:
            return ToolResult.from_error(f"Failed to get pathway genes: {e}")

    async def get_pathway_reactions(self, pathway_id: str) -> ToolResult:
        """Get all reactions in a pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g., "map00010")

        Returns:
            ToolResult with reaction list
        """
        try:
            endpoint = f"link/rn/{pathway_id}"
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            tsv_data = self._parse_tsv_response(response)

            reactions = [
                self._tsv_row_to_dict(row, "reaction", "pathway") for row in tsv_data
            ]

            return ToolResult.success(data={
                "pathway_id": pathway_id,
                "reactions": reactions
            })

        except Exception as e:
            return ToolResult.from_error(f"Failed to get pathway reactions: {e}")

    async def get_pathway_compounds(self, pathway_id: str) -> ToolResult:
        """Get all compounds in a pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g., "map00010")

        Returns:
            ToolResult with compound list
        """
        try:
            endpoint = f"link/cpd/{pathway_id}"
            response = await self._make_request(f"{self.BASE_URL}/{endpoint}")
            tsv_data = self._parse_tsv_response(response)

            compounds = [
                self._tsv_row_to_dict(row, "compound_id", "pathway") for row in tsv_data
            ]

            return ToolResult.success(data={
                "pathway_id": pathway_id,
                "compounds": compounds
            })

        except Exception as e:
            return ToolResult.from_error(f"Failed to get pathway compounds: {e}")

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (pathway ID, name, gene, compound)",
                },
                "query_type": {
                    "type": "string",
                    "enum": ["pathway", "organism", "gene", "compound"],
                    "description": "Type of query to perform",
                    "default": "pathway",
                },
                "organism": {
                    "type":
                    "string",
                    "description":
                    "Organism code (e.g., 'hsa' for human, 'eco' for E. coli)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["query"],
        }


# Convenience function for direct usage
async def lookup_kegg_pathway(
    pathway_id: str,
    organism: str = "hsa",
) -> Dict[str, Any]:
    """Convenience function to look up KEGG pathway information.

    Args:
        pathway_id: KEGG pathway ID (e.g., "map00010")
        organism: Organism code (default: "hsa" for human)

    Returns:
        Dictionary with pathway lookup results

    Example:
        >>> # Get glycolysis pathway information
        >>> result = await lookup_kegg_pathway("map00010", "hsa")
        >>> print(f"Pathway: {result['pathway_id']}")
        >>> print(f"Name: {result['name']}")
        >>> print(f"Genes: {len(result['genes'])} genes found")
    """
    tool = KEGGLookupTool()
    result = await tool.execute(
        query=pathway_id,
        query_type="pathway",
        organism=organism,
        limit=1,
    )
    await tool.close()
    return result.data
