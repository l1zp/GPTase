"""OpenAlex Academic Literature Search Tool.

Search academic papers using OpenAlex API with support for:
- Keyword and field-specific queries
- Publisher and repository filtering
- Abstract reconstruction from inverted index
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# Default publisher IDs (top academic publishers)
DEFAULT_PUBLISHERS = [
    "P4310319908",  # Elsevier
    "P4310320017",  # Springer Nature
    "P4310318332",  # Wiley
    "P4310320990",  # Taylor & Francis
    "P4310320595",  # Oxford University Press
    "P4310320556",  # Cambridge University Press
    "P4310311648",  # IEEE
]

# Preprint repository IDs
DEFAULT_REPOSITORIES = [
    "S4306402512",  # bioRxiv
    "S4306400127",  # arXiv
]


def invert_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
    """Convert OpenAlex inverted index abstract to original text.

    Args:
        inverted_index: The abstract_inverted_index from OpenAlex API.

    Returns:
        The original abstract text, or None if input is empty.
    """
    if not inverted_index:
        return None

    # Find the maximum position index
    max_pos = max(pos for positions in inverted_index.values() for pos in positions)
    # Create position-to-word mapping
    words = [''] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return ' '.join(words)


class OpenAlexTool(BaseTool):
    """Tool for searching academic literature via OpenAlex API."""

    def __init__(self):
        super().__init__(
            name="openalex_search",
            description=
            "Search academic papers using OpenAlex API. Returns papers with title, abstract, authors, venue, and open access PDF links.",
            timeout=30,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def execute(
        self,
        query: str = "",
        email: str = "research@example.com",
        days_back: int = 1,
        max_results: int = 50,
        publishers: Optional[List[str]] = None,
        repositories: Optional[List[str]] = None,
        **kwargs,
    ) -> ToolResult:
        """Search academic papers.

        Args:
            query: Search query string (empty returns all recent papers).
            email: Email for User-Agent header (required by OpenAlex).
            days_back: Number of days to look back for papers.
            max_results: Maximum results per filter type.
            publishers: List of OpenAlex publisher IDs to filter.
            repositories: List of OpenAlex repository IDs for preprints.

        Returns:
            ToolResult with list of paper metadata.
        """
        try:
            client = await self._get_client()
            api_key = os.environ.get("OPENALEX_API_KEY", "")

            # Use defaults if not provided
            publishers = publishers or DEFAULT_PUBLISHERS
            repositories = repositories or DEFAULT_REPOSITORIES

            results = await self._search(
                client=client,
                query=query,
                email=email,
                api_key=api_key,
                days_back=days_back,
                max_results=max_results,
                publishers=publishers,
                repositories=repositories,
            )

            return ToolResult.success(
                data=results,
                metadata={
                    "query": query,
                    "total_results": len(results),
                    "days_back": days_back,
                },
            )
        except Exception as e:
            logger.error(f"OpenAlex search failed: {e}")
            return ToolResult.from_error(str(e))

    async def _search(
        self,
        client: httpx.AsyncClient,
        query: str,
        email: str,
        api_key: str,
        days_back: int,
        max_results: int,
        publishers: List[str],
        repositories: List[str],
    ) -> List[Dict[str, Any]]:
        """Execute search with multiple filters and merge results."""
        base_url = "https://api.openalex.org/works"
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        date_str = cutoff_date.strftime("%Y-%m-%d")

        # Build filter values
        pub_filter_val = "|".join([f"https://openalex.org/{p}" for p in publishers])
        repo_filter_val = "|".join([f"https://openalex.org/{r}" for r in repositories])

        # Two filter conditions: publishers and repositories
        filters = [
            f"from_created_date:{date_str},language:en,primary_location.source.host_organization:{pub_filter_val}",
            f"from_created_date:{date_str},language:en,primary_location.source.id:{repo_filter_val}",
        ]

        headers = {"User-Agent": f"mailto:{email}"}
        all_works: Dict[str, Dict] = {}

        for f_str in filters:
            params = {
                "search": query,
                "filter": f_str,
                "per-page": max_results,
                "sort": "publication_date:desc",
            }
            if api_key:
                params["api_key"] = api_key

            logger.info(f"[INFO] OpenAlex query: {f_str[:60]}...")

            try:
                response = await client.get(base_url, params=params, headers=headers)
                if response.status_code != 200:
                    logger.warning(
                        f"[WARNING] OpenAlex request failed: {response.status_code}")
                    continue

                data = response.json()
                for work in data.get("results", []):
                    all_works[work["id"]] = work
            except Exception as e:
                logger.error(f"[ERROR] OpenAlex request exception: {e}")

        logger.info(f"[INFO] Found {len(all_works)} unique papers")
        return self._parse_works(list(all_works.values()))

    def _parse_works(self, works: List[Dict]) -> List[Dict[str, Any]]:
        """Parse raw OpenAlex works into structured format."""
        parsed = []
        for work in works:
            oa_url = work.get("open_access", {}).get("oa_url")
            authors = [
                a["author"]["display_name"] for a in work.get("authorships", [])[:3]
            ]
            venue = (work.get("primary_location", {}).get(
                "source", {}).get("display_name") or "Unknown Venue")

            abstract_inverted = work.get("abstract_inverted_index")
            abstract = invert_abstract(abstract_inverted)

            parsed.append({
                "id":
                work["id"],
                "title":
                work["display_name"],
                "abstract":
                abstract,
                "publication_year":
                work["publication_year"],
                "venue":
                venue,
                "authors":
                authors,
                "pdf_url":
                oa_url,
                "doi":
                work.get("doi"),
                "concepts": [c["display_name"] for c in work.get("concepts", [])[:5]],
            })
        return parsed

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description":
                    "Search query string (empty returns all recent papers)",
                },
                "email": {
                    "type": "string",
                    "description": "Email for User-Agent header (required by OpenAlex)",
                    "default": "research@example.com",
                },
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to look back for papers",
                    "default": 1,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results per filter type",
                    "default": 50,
                },
                "publishers": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of OpenAlex publisher IDs to filter",
                },
                "repositories": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of OpenAlex repository IDs for preprints",
                },
            },
            "required": [],
        }

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
