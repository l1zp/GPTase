"""Demo: Using Base Classes for New Database Tools.

This script demonstrates how to quickly create new database lookup tools
using the reusable base classes.

Usage:
    python examples/base_class_demo.py
"""

import asyncio
from src.tools.base import ToolStatus, ToolResult
from src.tools.external_databases.base import BaseAPITool, BaseHTMLTool, BaseDatabaseLookupTool


# Example 1: Simple REST API Tool (using BaseAPITool)
class ChEBITool(BaseAPITool):
    """ChEBI chemical entities database lookup.

    ChEBI: https://www.ebi.ac.uk/chebi/
    API: https://www.ebi.ac.uk/chebi/webapi/
    """

    TOOL_NAME = "chebi_lookup"
    BASE_URL = "https://www.ebi.ac.uk/chebi/api/data"
    RATE_LIMIT_DELAY = 0.2  # 200ms between requests

    async def execute(self, chebi_id: str) -> ToolResult:
        """Get compound information by ChEBI ID."""
        try:
            chebi_id = chebi_id.upper().replace("CHEBI:", "")
            endpoint = f"chebiId/{chebi_id}"
            data = await self._api_get(endpoint)

            result = {
                "chebi_id":
                f"CHEBI:{chebi_id}",
                "name":
                data.get("chebiAsciiName", ""),
                "smiles":
                data.get("smiles", ""),
                "formula":
                data.get("formulae", [{}])[0].get("formula", "")
                if data.get("formulae") else "",
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

    print("=" * 80)
    print("Context Manager Demo")
    print("=" * 80)
    print()

    async with ChEBITool() as tool:
        print("Tool initialized with automatic session management")
        print(f"Tool name: {tool.TOOL_NAME}")
        print(f"Base URL: {tool.BASE_URL}")
        print(f"Rate limit delay: {tool.RATE_LIMIT_DELAY}s")
        print(f"Max retries: {tool.MAX_RETRIES}")
        print()

    print("Session automatically closed after context exit")
    print()


async def demo_code_reuse():
    """Demonstrate code reuse benefits."""

    print("=" * 80)
    print("Code Reuse Demo")
    print("=" * 80)
    print()

    print("Base classes provide these features out of the box:")
    print()
    print("1. HTTP Session Management:")
    print("   - Automatic connection pooling")
    print("   - Session reuse across requests")
    print("   - Clean session.close() on exit")
    print()
    print("2. Retry Logic:")
    print("   - 3 automatic retries (configurable)")
    print("   - Exponential backoff (0.5s factor)")
    print("   - Retry on HTTP 429, 500, 502, 503, 504")
    print()
    print("3. Error Handling:")
    print("   - Automatic timeout handling")
    print("   - HTTP error catching")
    print("   - Standardized ToolResult format")
    print()
    print("4. Rate Limiting Support:")
    print("   - Configurable delay between requests")
    print("   - Automatic timing enforcement")
    print()
    print("5. Convenience Methods (BaseAPITool):")
    print("   - _api_get(): GET requests with JSON parsing")
    print("   - _api_post(): POST requests with JSON support")
    print()
    print("6. HTML Parsing (BaseHTMLTool):")
    print("   - _get_html_soup(): BeautifulSoup integration")
    print("   - _extract_text(): Text extraction helper")
    print()


async def show_template_comparison():
    """Compare code with and without base classes."""

    print("=" * 80)
    print("Code Comparison: With vs Without Base Classes")
    print("=" * 80)
    print()

    print("WITHOUT base class (manual implementation):")
    print("-" * 80)
    print("""
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

    print()
    print("WITH base class (reusing components):")
    print("-" * 80)
    print("""
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

    print()
    print("Result: ~70% less code, more maintainable!")
    print()


async def main():
    """Run all demonstrations."""

    print("\n" + "=" * 80)
    print("External Database Base Classes - Reusability Demo")
    print("=" * 80)
    print()

    await demo_code_reuse()
    await demo_context_manager()
    await show_template_comparison()

    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print()
    print("Three base classes available for code reuse:")
    print()
    print("1. BaseDatabaseLookupTool:")
    print("   - Generic database queries")
    print("   - Full control over request/response")
    print()
    print("2. BaseAPITool:")
    print("   - REST APIs with JSON responses")
    print("   - Convenience methods: _api_get(), _api_post()")
    print()
    print("3. BaseHTMLTool:")
    print("   - Web scraping with BeautifulSoup")
    print("   - HTML parsing helpers")
    print()
    print("Key benefits:")
    print("  - Less code to write")
    print("  - Consistent error handling")
    print("  - Automatic retry logic")
    print("  - Session management")
    print("  - Rate limiting support")
    print()
    print("See QUICKSTART.md for detailed examples!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
