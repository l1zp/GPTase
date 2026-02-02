"""Rhea Biochemical Reaction Database Lookup Tool.

This tool searches the Rhea database for biochemical reactions and retrieves:
- Reaction equations (substrates <=> products)
- EC numbers
- ChEBI compound identifiers and names
- UniProt enzyme cross-references
- GO (Gene Ontology) terms
- PubMed references

Rhea Database: https://www.rhea-db.org/
REST API: https://www.rhea-db.org/help/rest-api
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.base import ToolStatus

logger = logging.getLogger(__name__)

# Rhea ID pattern: RHEA:XXXXX (5 digits)
RHEA_ID_PATTERN = re.compile(r"^RHEA:\d+$", re.IGNORECASE)
# EC number pattern
EC_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


class RheaReactionLookupTool(BaseTool):
    """Tool for looking up biochemical reactions from Rhea database.

    This tool uses the Rhea REST API to:
    1. Search for reactions by Rhea ID, EC number, or compound name
    2. Retrieve reaction equations (substrates <=> products)
    3. Get ChEBI compound identifiers and names
    4. Extract cross-references (UniProt, GO, PubMed, KEGG, etc.)

    Database: https://www.rhea-db.org/
    API: https://www.rhea-db.org/help/rest-api
    """

    TOOL_NAME = "rhea_reaction_lookup"

    # Rhea API endpoints
    RHEA_BASE_URL = "https://www.rhea-db.org"
    RHEA_REST_URL = f"{RHEA_BASE_URL}/rest/1.0/ws"
    RHEA_QUERY_URL = f"{RHEA_BASE_URL}/rhea"

    # Request timeout (seconds)
    DEFAULT_TIMEOUT = 10

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF = 0.5

    # Headers to identify the client
    HEADERS = {
        "User-Agent": "GPTase-Framework/1.0 (https://github.com/l1zp/GPTase)",
        "Accept": "text/tab-separated-values",
    }

    def __init__(self):
        """Initialize Rhea Reaction Lookup Tool."""
        super().__init__(
            name=self.TOOL_NAME,
            description="Look up biochemical reactions from Rhea database",
        )
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic.

        Returns:
            Configured requests.Session with retry adapter
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    async def execute(
        self,
        query: str,
        query_type: str = "rhea-id",
        columns: Optional[List[str]] = None,
        limit: int = 10,
    ) -> ToolResult:
        """Execute reaction lookup from Rhea database.

        Args:
            query: Search query (Rhea ID, EC number, or compound name)
            query_type: Type of query:
                - "rhea-id": Search by Rhea ID (e.g., "RHEA:15109")
                - "ec": Search by EC number (e.g., "2.7.1.1")
                - "compound": Search by compound name or ChEBI ID
                - "uniprot": Search for reactions with UniProt enzymes
                - "all": Search all reactions (empty query)
            columns: Columns to retrieve (default: all)
            limit: Maximum number of results to return (default: 10)

        Returns:
            ToolResult with data containing:
                {
                    "reactions": [
                        {
                            "rhea_id": str,
                            "equation": str,
                            "ec_numbers": List[str],
                            "chebi_names": List[str],
                            "chebi_ids": List[str],
                            "uniprot_count": int,
                            "go_terms": List[str],
                            "pubmed_ids": List[str],
                            "xrefs": Dict[str, List[str]]
                        },
                        ...
                    ],
                    "summary": {
                        "query": str,
                        "query_type": str,
                        "total_found": int,
                        "returned": int
                    }
                }
        """
        start_time = time.time()

        try:
            if not query and query_type != "all":
                return ToolResult.from_error(
                    "Query string is required (except for 'all' query type)")

            # Default columns to retrieve
            if columns is None:
                columns = [
                    "rhea-id",
                    "equation",
                    "ec",
                    "chebi",
                    "chebi-id",
                    "uniprot",
                    "go",
                    "pubmed",
                    "reaction-xref(KEGG)",
                    "reaction-xref(MetaCyc)",
                    "reaction-xref(EcoCyc)",
                    "reaction-xref(Reactome)",
                    "reaction-xref(M-CSA)",
                ]

            # Build query string based on query type
            query_str = self._build_query_string(query, query_type)

            # Fetch data from Rhea
            results = await self._query_rhea(
                query_str=query_str,
                columns=columns,
                limit=limit,
            )

            if not results:
                return ToolResult.from_error(
                    error_message=f"No reactions found for query: {query}",
                    execution_time=time.time() - start_time,
                )

            execution_time = time.time() - start_time

            # Prepare summary data
            data = {
                "reactions": results,
                "summary": {
                    "query": query,
                    "query_type": query_type,
                    "total_found": len(results),
                    "returned": len(results),
                },
            }

            logger.info(
                f"Rhea query completed: {len(results)} reactions found for '{query}'")

            return ToolResult.success(
                data=data,
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Rhea query failed: {e}", exc_info=True)
            return ToolResult.from_error(
                error_message=f"Rhea query failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _build_query_string(self, query: str, query_type: str) -> str:
        """Build Rhea query string based on query type.

        Args:
            query: Search query
            query_type: Type of query

        Returns:
            Formatted query string for Rhea API
        """
        if query_type == "rhea-id":
            # Rhea ID search: just use the ID number (without prefix)
            # Extract numeric part from "RHEA:15109" -> "15109"
            rhea_id = query.upper().replace("RHEA:", "")
            if not rhea_id.isdigit():
                logger.warning(f"Invalid Rhea ID format: {query}")
            return rhea_id

        elif query_type == "ec":
            # EC number search: use full EC string
            if not EC_PATTERN.match(query):
                logger.warning(f"Invalid EC number format: {query}")
            return query

        elif query_type == "compound":
            # Compound search by name or ChEBI ID
            if query.upper().startswith("CHEBI:"):
                # Remove CHEBI: prefix for search
                return query.upper().replace("CHEBI:", "")
            else:
                return query

        elif query_type == "uniprot":
            # Search for reactions with UniProt enzymes
            return ""

        elif query_type == "all":
            # Search all reactions
            return ""

        else:
            logger.warning(
                f"Unknown query type: {query_type}, using as compound search")
            return query

    async def _query_rhea(
        self,
        query_str: str,
        columns: List[str],
        limit: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Query Rhea database.

        Args:
            query_str: Formatted query string
            columns: List of columns to retrieve
            limit: Maximum number of results

        Returns:
            List of reaction dictionaries or None if error
        """
        try:
            # Build URL parameters
            params = {
                "query": query_str,
                "columns": ",".join(columns),
                "format": "tsv",
                "limit": limit,
            }

            # Make request
            response = self._session.get(
                self.RHEA_QUERY_URL,
                params=params,
                headers=self.HEADERS,
                timeout=self.DEFAULT_TIMEOUT,
            )
            response.raise_for_status()

            # Parse TSV response
            results = self._parse_tsv_response(
                response.text,
                columns,
            )

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error querying Rhea: {e}")
            return None
        except Exception as e:
            logger.error(f"Error querying Rhea: {e}")
            return None

    def _parse_tsv_response(
        self,
        tsv_text: str,
        columns: List[str],
    ) -> List[Dict[str, Any]]:
        """Parse TSV response from Rhea API.

        Args:
            tsv_text: TSV formatted text
            columns: List of column names

        Returns:
            List of parsed reaction dictionaries
        """
        results = []

        try:
            lines = tsv_text.strip().split("\n")

            if len(lines) < 2:
                # No data rows
                return results

            # Parse header and data rows
            for line in lines[1:]:  # Skip header row
                if not line.strip():
                    continue

                values = line.split("\t")

                # Build reaction dictionary
                reaction = self._build_reaction_dict(
                    columns,
                    values,
                )

                if reaction:
                    results.append(reaction)

            return results

        except Exception as e:
            logger.error(f"Error parsing TSV response: {e}")
            return []

    def _build_reaction_dict(
        self,
        columns: List[str],
        values: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Build reaction dictionary from column names and values.

        Args:
            columns: List of column names
            values: List of corresponding values

        Returns:
            Reaction dictionary or None if error
        """
        try:
            reaction: Dict[str, Any] = {}

            # Map columns to values
            column_map = dict(zip(columns, values))

            # Extract Rhea ID
            reaction["rhea_id"] = column_map.get("rhea-id", "")

            # Extract equation
            reaction["equation"] = column_map.get("equation", "")

            # Extract EC numbers
            ec_str = column_map.get("ec", "")
            reaction["ec_numbers"] = self._parse_semicolon_list(ec_str)

            # Extract ChEBI names
            chebi_str = column_map.get("chebi", "")
            reaction["chebi_names"] = self._parse_semicolon_list(chebi_str)

            # Extract ChEBI IDs
            chebi_id_str = column_map.get("chebi-id", "")
            reaction["chebi_ids"] = self._parse_semicolon_list(chebi_id_str)

            # Extract UniProt count
            uniprot_str = column_map.get("uniprot", "0")
            reaction["uniprot_count"] = int(uniprot_str) if uniprot_str.isdigit() else 0

            # Extract GO terms
            go_str = column_map.get("go", "")
            reaction["go_terms"] = self._parse_semicolon_list(go_str)

            # Extract PubMed IDs
            pubmed_str = column_map.get("pubmed", "")
            reaction["pubmed_ids"] = self._parse_semicolon_list(pubmed_str)

            # Extract cross-references
            xrefs = {}
            for col in columns:
                if col.startswith("reaction-xref("):
                    db_name = col.replace("reaction-xref(", "").replace(")", "")
                    xref_value = column_map.get(col, "")
                    xrefs[db_name] = self._parse_semicolon_list(xref_value)

            reaction["xrefs"] = xrefs

            # Parse equation into substrates and products
            if reaction["equation"]:
                substrates, products = self._parse_equation(reaction["equation"])
                reaction["substrates"] = substrates
                reaction["products"] = products
            else:
                reaction["substrates"] = []
                reaction["products"] = []

            return reaction

        except Exception as e:
            logger.error(f"Error building reaction dict: {e}")
            return None

    def _parse_semicolon_list(self, value: str) -> List[str]:
        """Parse semicolon-separated list.

        Args:
            value: Semicolon-separated string

        Returns:
            List of non-empty values
        """
        if not value or not value.strip():
            return []

        items = [item.strip() for item in value.split(";")]
        return [item for item in items if item]

    def _parse_equation(self, equation: str) -> tuple[List[str], List[str]]:
        """Parse reaction equation into substrates and products.

        Args:
            equation: Reaction equation (e.g., "A + B = C + D")

        Returns:
            Tuple of (substrates_list, products_list)
        """
        try:
            # Split by reaction direction indicators
            for separator in ["<=>", "<->", "=>", "->", "="]:
                if separator in equation:
                    parts = equation.split(separator)
                    if len(parts) == 2:
                        left, right = parts

                        # Extract substrates (left side)
                        substrates = self._extract_compounds(left)

                        # Extract products (right side)
                        products = self._extract_compounds(right)

                        return substrates, products

            # If no separator found, return empty lists
            return [], []

        except Exception as e:
            logger.error(f"Error parsing equation '{equation}': {e}")
            return [], []

    def _extract_compounds(self, side: str) -> List[str]:
        """Extract compound names from reaction side.

        This function carefully handles chemical names with parentheses
        like NADP(+), H2O, etc., which are part of the compound name
        and should not be removed.

        Args:
            side: One side of reaction equation (e.g., "ATP + glucose + NADP(+)")

        Returns:
            List of compound names with proper formatting

        Examples:
            >>> _extract_compounds("ATP + glucose + NADP(+) + H2O")
            ["ATP", "glucose", "NADP(+)", "H2O"]

            >>> _extract_compounds("2 ATP + glucose 6-phosphate")
            ["ATP", "glucose 6-phosphate"]
        """
        import re

        # Smart splitting: only split by ' + ' (space-plus-space) to avoid
        # splitting within compound names like "NADP(+)" or "H(+)"
        parts = re.split(r'\s\+\s', side.strip())

        compounds = []
        for part in parts:
            compound = part.strip()

            if not compound:
                continue

            # Remove stoichiometry coefficients at the beginning (e.g., "2 ATP" -> "ATP")
            # But be careful not to remove numbers that are part of chemical formulas
            compound = re.sub(r'^\d+\s+', '', compound)

            # Keep the compound as-is, including parentheses in names like "NADP(+)"
            # Only remove explanatory notes that have a space before them
            # e.g., "compound (note)" -> "compound" but keep "NADP(+)" and "H(+)"
            # The pattern \s+\([a-zA-Z]+\)$ removes text notes but not symbols
            compound = re.sub(r'\s+\([a-zA-Z]+\)$', '', compound)

            if compound:
                compounds.append(compound)

        return compounds

    async def get_reaction_by_id(self, rhea_id: str) -> ToolResult:
        """Get a specific reaction by Rhea ID.

        Args:
            rhea_id: Rhea reaction ID (e.g., "RHEA:15109")

        Returns:
            ToolResult with reaction data
        """
        return await self.execute(
            query=rhea_id,
            query_type="rhea-id",
            limit=1,
        )

    async def get_reactions_by_ec(
        self,
        ec_number: str,
        limit: int = 50,
    ) -> ToolResult:
        """Get reactions by EC number.

        Args:
            ec_number: EC number (e.g., "2.7.1.1")
            limit: Maximum number of results

        Returns:
            ToolResult with reaction list
        """
        return await self.execute(
            query=ec_number,
            query_type="ec",
            limit=limit,
        )

    async def search_reactions_by_compound(
        self,
        compound_name: str,
        limit: int = 50,
    ) -> ToolResult:
        """Search for reactions involving a compound.

        Args:
            compound_name: Compound name or ChEBI ID
            limit: Maximum number of results

        Returns:
            ToolResult with reaction list
        """
        return await self.execute(
            query=compound_name,
            query_type="compound",
            limit=limit,
        )

    def get_mechanism_links(self, reaction: Dict[str, Any]) -> Dict[str, Any]:
        """Generate links to mechanism-related databases and resources.

        This method creates direct URLs to external resources that contain
        detailed reaction mechanism information, including:
        - PubMed articles with mechanistic studies
        - M-CSA (Catalytic Site Atlas) for catalytic residues and mechanism
        - ChEBI for stereochemistry and molecular structure
        - Rhea web page for detailed publications

        Args:
            reaction: Reaction dictionary from Rhea query

        Returns:
            Dictionary with mechanism resource URLs and metadata

        Example:
            >>> tool = RheaReactionLookupTool()
            >>> result = await tool.get_reaction_by_id("RHEA:21020")
            >>> if result.status == ToolStatus.SUCCESS:
            ...     reaction = result.data["reactions"][0]
            ...     links = tool.get_mechanism_links(reaction)
            ...     print(links["pubmed_articles"])
            ...     print(links["mcsa_url"])
        """
        links = {
            "rhea_id": reaction.get("rhea_id", ""),
            "rhea_web_url":
            f"{self.RHEA_BASE_URL}/{reaction.get('rhea_id', '').replace(':', '')}",
            "pubmed_articles": [],
            "mcsa_links": [],
            "chebi_compounds": [],
        }

        # Generate PubMed article URLs
        for pubmed_id in reaction.get("pubmed_ids", []):
            links["pubmed_articles"].append({
                "pubmed_id":
                pubmed_id,
                "url":
                f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
                "description":
                f"PubMed article {pubmed_id}",
            })

        # Generate M-CSA links
        for mcsa_id in reaction.get("xrefs", {}).get("M-CSA", []):
            # Extract numeric ID from "M-CSA:123"
            numeric_id = mcsa_id.replace("M-CSA:", "")
            links["mcsa_links"].append({
                "mcsa_id": mcsa_id,
                "url": f"https://www.ebi.ac.uk/thornton-srv/m-csa/entry/{numeric_id}",
                "description": f"Catalytic mechanism from M-CSA",
            })

        # Generate ChEBI compound URLs for stereochemistry
        for i, chebi_id in enumerate(reaction.get("chebi_ids", [])):
            chebi_name = reaction.get("chebi_names", [])[i] if i < len(
                reaction.get("chebi_names", [])) else ""
            links["chebi_compounds"].append({
                "chebi_id":
                chebi_id,
                "chebi_name":
                chebi_name,
                "url":
                f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={chebi_id.replace('CHEBI:', '')}",
                "description":
                f"ChEBI entry for {chebi_name or chebi_id}",
            })

        return links

    async def close(self):
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            self._session = None

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
                    "description":
                    "Search query (Rhea ID, EC number, or compound name)",
                },
                "query_type": {
                    "type": "string",
                    "enum": ["rhea-id", "ec", "compound", "uniprot", "all"],
                    "description": "Type of query to perform",
                    "default": "rhea-id",
                },
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Columns to retrieve (default: all available)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": ["query"],
        }


# Convenience function for direct usage
async def lookup_rhea_reaction(
    query: str,
    query_type: str = "rhea-id",
    limit: int = 10,
) -> Dict[str, Any]:
    """Convenience function to look up reactions from Rhea database.

    Args:
        query: Search query (Rhea ID, EC number, or compound name)
        query_type: Type of query ("rhea-id", "ec", "compound", "uniprot", "all")
        limit: Maximum number of results

    Returns:
        Dictionary with lookup results

    Example:
        >>> # Get reaction by Rhea ID
        >>> result = await lookup_rhea_reaction("RHEA:15109")
        >>> for reaction in result["reactions"]:
        ...     print(f"{reaction['rhea_id']}: {reaction['equation']}")

        >>> # Get reactions by EC number
        >>> result = await lookup_rhea_reaction("2.7.1.1", query_type="ec")

        >>> # Search by compound name
        >>> result = await lookup_rhea_reaction("glucose", query_type="compound")
    """
    tool = RheaReactionLookupTool()
    result = await tool.execute(query=query, query_type=query_type, limit=limit)
    await tool.close()
    return result.data
