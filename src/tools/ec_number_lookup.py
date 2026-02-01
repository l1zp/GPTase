"""ExPASy Enzyme Database Lookup Tool.

This tool searches the ExPASy (Expert Protein Analysis System) enzyme database
for EC numbers and retrieves reaction information including:
- Enzyme name and classification
- Catalyzed reaction (substrates -> products)
- Cofactors and prosthetic groups
- Comments on enzyme function
- References to literature

ExPASy Enzyme Database: https://enzyme.expasy.org/
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from src.tools.base import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)

# EC number pattern: X.X.X.X (1-4 digits per level)
EC_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


class ExPAsyEnzymeLookupTool(BaseTool):
    """Tool for looking up enzyme reaction information from ExPASy database.

    This tool uses the ExPASy Enzyme database to:
    1. Search for enzymes by EC number
    2. Retrieve catalyzed reactions
    3. Get cofactors, prosthetic groups, and comments
    4. Extract literature references

    Database: https://enzyme.expasy.org/
    """

    TOOL_NAME = "expasy_enzyme_lookup"

    # ExPASy enzyme database URLs
    EXPASY_ENZYME_BASE_URL = "https://enzyme.expasy.org"
    EXPASY_ENZYME_URL = f"{EXPASY_ENZYME_BASE_URL}/EC"

    # Request timeout (seconds)
    DEFAULT_TIMEOUT = 10

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF = 0.5

    # Headers to mimic browser requests
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    def __init__(self):
        """Initialize ExPASy Enzyme Lookup Tool."""
        super().__init__(
            name=self.TOOL_NAME,
            description="Look up enzyme reaction information from ExPASy database",
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

    async def execute(self, ec_numbers: List[str]) -> ToolResult:
        """Execute enzyme lookup for EC numbers.

        Args:
            ec_numbers: List of EC numbers to search for (e.g., ["1.1.1.1", "2.7.1.1"])

        Returns:
            ToolResult with data containing:
                {
                    "enzymes": [
                        {
                            "ec_number": str,
                            "enzyme_name": str,
                            "reaction": str,
                            "reaction_equation": str,
                            "substrates": List[str],
                            "products": List[str],
                            "cofactors": List[str],
                            "comments": List[str],
                            "references": List[Dict],
                            "alternate_names": List[str]
                        },
                        ...
                    ],
                    "summary": {
                        "total_searched": int,
                        "found": int,
                        "not_found": int
                    }
                }
        """
        start_time = time.time()

        try:
            if not ec_numbers:
                return ToolResult.from_error("No EC numbers provided")

            results = []
            found_count = 0
            not_found_count = 0

            for ec_number in ec_numbers:
                try:
                    enzyme_data = await self._lookup_enzyme(ec_number)

                    if enzyme_data:
                        results.append(enzyme_data)
                        found_count += 1
                    else:
                        results.append(
                            {
                                "ec_number": ec_number,
                                "enzyme_name": None,
                                "reaction": None,
                                "reaction_equation": None,
                                "substrates": [],
                                "products": [],
                                "cofactors": [],
                                "comments": [],
                                "references": [],
                                "alternate_names": [],
                                "error": "Not found in ExPASy",
                            }
                        )
                        not_found_count += 1

                except Exception as e:
                    logger.error(f"Error looking up EC {ec_number}: {e}")
                    results.append(
                        {
                            "ec_number": ec_number,
                            "enzyme_name": None,
                            "reaction": None,
                            "reaction_equation": None,
                            "substrates": [],
                            "products": [],
                            "cofactors": [],
                            "comments": [],
                            "references": [],
                            "alternate_names": [],
                            "error": str(e),
                        }
                    )
                    not_found_count += 1

            execution_time = time.time() - start_time

            # Prepare summary data
            data = {
                "enzymes": results,
                "summary": {
                    "total_searched": len(ec_numbers),
                    "found": found_count,
                    "not_found": not_found_count,
                },
            }

            logger.info(
                f"ExPASy enzyme lookup completed: {found_count}/{len(ec_numbers)} found"
            )

            return ToolResult.success(
                data=data,
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"ExPASy enzyme lookup failed: {e}", exc_info=True)
            return ToolResult.from_error(
                error_message=f"ExPASy enzyme lookup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    async def _lookup_enzyme(self, ec_number: str) -> Optional[Dict[str, Any]]:
        """Look up a single enzyme in ExPASy database.

        Args:
            ec_number: EC number (e.g., "1.1.1.1")

        Returns:
            Enzyme data dictionary or None if not found
        """
        try:
            # Validate EC number format
            if not EC_PATTERN.match(ec_number.strip()):
                logger.warning(f"Invalid EC number format: {ec_number}")
                return None

            # Construct URL for enzyme entry
            url = f"{self.EXPASY_ENZYME_URL}/{ec_number.strip()}"

            # Fetch page
            response = self._session.get(
                url, headers=self.HEADERS, timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Check if page exists (404 pages have different structure)
            if "not found" in response.text.lower() or response.status_code == 404:
                return None

            # Extract enzyme information
            enzyme_data = self._parse_enzyme_page(soup, ec_number)

            if enzyme_data:
                enzyme_data["ec_number"] = ec_number.strip()
                enzyme_data["source_url"] = url
                return enzyme_data
            else:
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error looking up EC {ec_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error looking up EC {ec_number}: {e}")
            return None

    def _parse_enzyme_page(
        self, soup: BeautifulSoup, ec_number: str
    ) -> Optional[Dict[str, Any]]:
        """Parse ExPASy enzyme page HTML.

        Args:
            soup: BeautifulSoup object
            ec_number: EC number for context

        Returns:
            Parsed enzyme data dictionary
        """
        try:
            # Initialize result
            result = {
                "enzyme_name": None,
                "reaction": None,
                "reaction_equation": None,
                "substrates": [],
                "products": [],
                "cofactors": [],
                "comments": [],
                "references": [],
                "alternate_names": [],
            }

            # Get all text lines from page
            text_lines = soup.get_text(separator="\n", strip=True).split("\n")
            text_lines = [line.strip() for line in text_lines if line.strip()]

            # Parse by line-by-line scanning
            i = 0
            while i < len(text_lines):
                line = text_lines[i]

                # Extract accepted name
                if line == "Accepted Name":
                    if i + 1 < len(text_lines):
                        result["enzyme_name"] = text_lines[i + 1]

                # Extract alternative names
                elif line == "Alternative Name(s)":
                    # Collect all following lines until next section header
                    j = i + 1
                    alt_names = []
                    while j < len(text_lines) and not text_lines[j].startswith(
                        ("Reaction", "Comment", "Cofactor", "Name")
                    ):
                        if text_lines[j]:
                            alt_names.append(text_lines[j])
                        j += 1
                    result["alternate_names"] = alt_names

                # Extract reaction
                elif line.startswith("Reaction catalysed"):
                    # Collect reaction components (substrates, products, cofactors)
                    reaction_parts = []
                    j = i + 1
                    while j < len(text_lines) and not text_lines[j].startswith(
                        ("Comment", "Cofactor", "Name", "Reaction")
                    ):
                        # Skip empty lines and section headers
                        if (
                            text_lines[j]
                            and not text_lines[j].startswith(("(", ")"))
                        ):
                            reaction_parts.append(text_lines[j])
                        j += 1

                    # Build full reaction string
                    result["reaction"] = " ".join(reaction_parts)

                    # Parse substrates, cofactors, and products
                    # Format: substrates -> cofactors -> products
                    if reaction_parts:
                        # Try to identify structure
                        arrow_idx = None
                        for idx, part in enumerate(reaction_parts):
                            if "=" in part or "→" in part or "->" in part:
                                arrow_idx = idx
                                break

                        if arrow_idx is not None:
                            # Everything before arrow = substrates
                            substrates = reaction_parts[:arrow_idx]
                            # Everything after arrow = products
                            products = reaction_parts[arrow_idx + 1:]

                            # Filter out cofactors (in parentheses)
                            result["substrates"] = [
                                s for s in substrates if not s.startswith("(")
                            ]
                            result["cofactors"] = [
                                s.strip("()")
                                for s in substrates
                                if s.startswith("(")
                            ]
                            result["products"] = products

                            # Build equation
                            left = " + ".join(result["substrates"])
                            if result["cofactors"]:
                                left += " + " + " + ".join(result["cofactors"])
                            right = " + ".join(result["products"])
                            result["reaction_equation"] = f"{left} -> {right}"

                # Extract comments
                elif line.startswith("Comment"):
                    j = i + 1
                    comments = []
                    while j < len(text_lines) and not text_lines[j].startswith(
                        ("Cofactor", "Name", "Reaction")
                    ):
                        if text_lines[j]:
                            comments.append(text_lines[j])
                        j += 1
                    result["comments"] = comments

                i += 1

            # Fallback: extract name from title if not found
            if not result["enzyme_name"]:
                title_tag = soup.find("title")
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    # Format: "ENZYME - 4.1.1.48 indole-3-glycerol-phosphate synthase"
                    parts = title_text.split(" ", 2)
                    if len(parts) > 2:
                        result["enzyme_name"] = parts[2].strip()

            return result

        except Exception as e:
            logger.error(f"Error parsing enzyme page for EC {ec_number}: {e}")
            return None

    def _parse_reaction_equation(self, equation: str) -> tuple[List[str], List[str]]:
        """Parse reaction equation into substrates and products.

        Args:
            equation: Reaction equation string (e.g., "A + B -> C + D")

        Returns:
            Tuple of (substrates_list, products_list)
        """
        # Clean up equation
        equation = equation.strip()

        # Split by reaction direction indicators
        for separator in ["<=>", "<->", "→", "->", "="]:
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

    def _extract_compounds(self, side: str) -> List[str]:
        """Extract compound names from reaction side.

        Args:
            side: One side of reaction equation (e.g., "ATP + glucose")

        Returns:
            List of compound names
        """
        # Split by '+' and clean up
        compounds = []
        for part in side.split("+"):
            compound = part.strip()
            # Remove stoichiometry coefficients (e.g., "2 ATP" -> "ATP")
            compound = re.sub(r"^\d+\s+", "", compound)
            # Remove parenthetical notes
            compound = re.sub(r"\s*\([^)]*\)", "", compound)
            if compound:
                compounds.append(compound)
        return compounds

    def _extract_list_from_text(self, text: str) -> List[str]:
        """Extract list items from text.

        Args:
            text: Text containing list items

        Returns:
            List of items
        """
        # Split by common delimiters
        items = re.split(r"[;,\n]\s*", text)
        # Clean up and filter
        cleaned_items = [item.strip() for item in items if item.strip() and len(item.strip()) > 2]
        return cleaned_items

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
                "ec_numbers": {
                    "type": "array",
                    "items": {"type": "string", "pattern": r"^\d+\.\d+\.\d+\.\d+$"},
                    "description": "List of EC numbers to search for (e.g., ['1.1.1.1', '2.7.1.1'])",
                },
            },
            "required": ["ec_numbers"],
        }


# Convenience function for direct usage
async def lookup_enzymes(ec_numbers: List[str]) -> Dict[str, Any]:
    """Convenience function to look up enzymes by EC number.

    Args:
        ec_numbers: List of EC numbers to search

    Returns:
        Dictionary with lookup results

    Example:
        >>> result = await lookup_enzymes(["1.1.1.1", "2.7.1.1"])
        >>> for enzyme in result["enzymes"]:
        ...     if enzyme["enzyme_name"]:
        ...         print(f"{enzyme['ec_number']}: {enzyme['enzyme_name']}")
        ...         print(f"  Reaction: {enzyme['reaction']}")
    """
    tool = ExPAsyEnzymeLookupTool()
    result = await tool.execute(ec_numbers=ec_numbers)
    await tool.close()
    return result.data
