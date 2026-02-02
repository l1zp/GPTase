"""Demo: Using Base Classes for New Database Tools.

This script demonstrates how to quickly create new database lookup tools
using the reusable base classes.

Usage:
    python examples/base_class_demo.py
"""

import asyncio
import logging

from src.tools.base import ToolResult
from src.tools.base import ToolStatus
from src.tools.external_databases.base import BaseAPITool
from src.tools.external_databases.base import BaseDatabaseLookupTool
from src.tools.external_databases.base import BaseHTMLTool

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


# Example 1: Simple REST API Tool (using BaseAPITool)
class ChEBITool(BaseAPITool):
    """ChEBI chemical entities database lookup.

    ChEBI: https://www.ebi.ac.uk/chebi/
    API: https://www.ebi.ac.uk/chebi/webapi/
    """

    TOOL_NAME = "chebi_lookup"
    BASE_URL = "https://www.ebi.ac.uk/chebi/api/data"
    RATE_LIMIT_DELAY = 0.2

    async def execute(self, chebi_id: str) -> ToolResult:
        """Get compound information by ChEBI ID."""
        try:
            chebi_id = chebi_id.upper().replace("CHEBI:", "")
            endpoint = f"chebiId/{chebi_id}"
            data = await self._api_get(endpoint)

            formula = ""
            if data.get("formulae"):
                formula = data["formulae"][0].get("formula", "")

            result = {
                "chebi_id": f"CHEBI:{chebi_id}",
                "name": data.get("chebiAsciiName", ""),
                "smiles": data.get("smiles", ""),
                "formula": formula,
            }
            return ToolResult.success(data=result)
        except Exception as e:
            return ToolResult.from_error(f"ChEBI lookup failed: {e}")

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "chebi_id": {
                    "type": "string"
                }
            },
            "required": ["chebi_id"]
        }


# Example 2: Using context manager for automatic cleanup
async def demo_context_manager():
    """Demonstrate context manager usage."""

    logger.info("=" * 80)
    logger.info("Context Manager Demo")
    logger.info("=" * 80)
    logger.info("")

    async with ChEBITool() as tool:
        logger.info("Tool initialized with automatic session management")
        logger.info(f"Tool name: {tool.TOOL_NAME}")
        logger.info(f"Base URL: {tool.BASE_URL}")
        logger.info(f"Rate limit delay: {tool.RATE_LIMIT_DELAY}s")
        logger.info(f"Max retries: {tool.MAX_RETRIES}")
        logger.info("")

    logger.info("Session automatically closed after context exit")
    logger.info("")


async def demo_code_reuse():
    """Demonstrate code reuse benefits."""

    logger.info("=" * 80)
    logger.info("Code Reuse Demo")
    logger.info("=" * 80)
    logger.info("")

    features = [
        ("HTTP Session Management", [
            "Automatic connection pooling", "Session reuse across requests",
            "Clean session.close() on exit"
        ]),
        ("Retry Logic", [
            "3 automatic retries (configurable)", "Exponential backoff (0.5s factor)",
            "Retry on HTTP 429, 500, 502, 503, 504"
        ]),
        ("Error Handling", [
            "Automatic timeout handling", "HTTP error catching",
            "Standardized ToolResult format"
        ]),
        ("Rate Limiting Support",
         ["Configurable delay between requests", "Automatic timing enforcement"]),
        ("Convenience Methods (BaseAPITool)", [
            "_api_get(): GET requests with JSON parsing",
            "_api_post(): POST requests with JSON support"
        ]),
        ("HTML Parsing (BaseHTMLTool)", [
            "_get_html_soup(): BeautifulSoup integration",
            "_extract_text(): Text extraction helper"
        ]),
    ]

    logger.info("Base classes provide these features out of the box:")
    logger.info("")
    for i, (title, items) in enumerate(features, 1):
        logger.info(f"{i}. {title}:")
        for item in items:
            logger.info(f"   - {item}")
        logger.info("")


async def show_template_comparison():
    """Compare code with and without base classes."""

    logger.info("=" * 80)
    logger.info("Code Comparison: With vs Without Base Classes")
    logger.info("=" * 80)
    logger.info("")

    logger.info("WITHOUT base class (manual implementation):")
    logger.info("-" * 80)
    logger.info("""
class MyTool:
    def __init__(self):
        # Manual session setup
        self.session = requests.Session()
        # Manual retry configuration
        retry = Retry(total=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    async def execute(self, query):
        # Manual error handling
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return ToolResult.success(data)
        except Exception as e:
            return ToolResult.from_error(str(e))

    async def close(self):
        # Manual cleanup
        if self.session:
            self.session.close()
""")

    logger.info("")
    logger.info("WITH base class (reusing components):")
    logger.info("-" * 80)
    logger.info("""
class MyTool(BaseAPITool):
    TOOL_NAME = "my_tool"
    BASE_URL = "https://api.example.com"
    RATE_LIMIT_DELAY = 0.2

    async def execute(self, query):
        # All session management, retry logic, and error
        # handling are inherited from base class!
        data = await self._api_get("search", params={"q": query})
        return ToolResult.success(data)
""")

    logger.info("")
    logger.info("Result: ~70% less code, more maintainable!")
    logger.info("")


async def main():
    """Run all demonstrations."""

    setup_logging()
    logger.info("")
    logger.info("=" * 80)
    logger.info("External Database Base Classes - Reusability Demo")
    logger.info("=" * 80)
    logger.info("")

    await demo_code_reuse()
    await demo_context_manager()
    await show_template_comparison()

    logger.info("=" * 80)
    logger.info("Summary")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Three base classes available for code reuse:")
    logger.info("")
    logger.info("1. BaseDatabaseLookupTool:")
    logger.info("   - Generic database queries")
    logger.info("   - Full control over request/response")
    logger.info("")
    logger.info("2. BaseAPITool:")
    logger.info("   - REST APIs with JSON responses")
    logger.info("   - Convenience methods: _api_get(), _api_post()")
    logger.info("")
    logger.info("3. BaseHTMLTool:")
    logger.info("   - Web scraping with BeautifulSoup")
    logger.info("   - HTML parsing helpers")
    logger.info("")
    logger.info("Key benefits:")
    logger.info("  - Less code to write")
    logger.info("  - Consistent error handling")
    logger.info("  - Automatic retry logic")
    logger.info("  - Session management")
    logger.info("  - Rate limiting support")
    logger.info("")
    logger.info("See QUICKSTART.md for detailed examples!")
    logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
