# External Database Tools - Quick Start Guide

This guide helps you quickly understand and use the external database lookup tools in GPTase.

## 🚀 Quick Start

### Option 1: Using Individual Tools

```python
import asyncio
from src.tools.external_databases.pubchem import PubChemSMILESLookupTool
from src.tools.external_databases.expasy import ExPAsyEnzymeLookupTool
from src.tools.external_databases.rhea import RheaReactionLookupTool

async def lookup_compound_info():
    """Get compound information from PubChem."""
    tool = PubChemSMILESLookupTool()
    result = await tool.execute(compound_names=["glucose", "ATP"])

    if result.status.value == "success":
        for compound in result.data["compounds"]:
            print(f"{compound['name']}: {compound['smiles']}")
    await tool.close()

asyncio.run(lookup_compound_info())
```

### Option 2: Using the Base Class for New Databases

```python
from src.tools.external_databases.base import BaseAPITool

class MyDatabaseTool(BaseAPITool):
    TOOL_NAME = "my_database"
    BASE_URL = "https://api.example.com/v1"
    DEFAULT_TIMEOUT = 15
    MAX_RETRIES = 5
    RATE_LIMIT_DELAY = 0.5  # 500ms between requests

    async def execute(self, query: str, limit: int = 10) -> ToolResult:
        try:
            endpoint = f"{self.BASE_URL}/search"
            data = await self._api_get(
                endpoint,
                params={"q": query, "limit": limit}
            )
            return ToolResult.success(data=data)

        except Exception as e:
            return ToolResult.from_error(str(e))

# Usage
tool = MyDatabaseTool()
result = await tool.execute("my query")
```

## 📊 Available Tools Comparison

| Tool | Database | Query Type | Returns | API Type |
|------|----------|-----------|---------|----------|
| **PubChem** | Chemical compounds | Name/CID/SMILES | SMILES, properties | REST API |
| **ExPASy** | Enzymes | EC number | Reaction, cofactors | HTML scraping |
| **Rhea** | Biochemical reactions | Rhea ID/EC/Compound | Equation, xrefs | REST API (TSV) |

## 🔧 Common Patterns

### 1. Async Session Management

All tools inherit from `BaseDatabaseLookupTool` which provides:

```python
# Automatic HTTP session with retry logic
self._session = self._create_session()

# Make request with automatic retry
response = await self._make_request(url, timeout=10)

# Cleanup
await self.close()
```

**Built-in Features:**
- ✅ Automatic retry (3 retries by default)
- ✅ Exponential backoff
- ✅ Connection pooling
- ✅ Timeout handling
- ✅ Rate limiting support

### 2. Standardized Response Format

All tools return `ToolResult` objects:

```python
ToolResult(
    status=ToolStatus.SUCCESS,  # or ERROR, TIMEOUT
    data={...},                  # Result data
    error_message=None,          # Error message if failed
    execution_time=0.5           # Seconds
)
```

### 3. Error Handling Pattern

```python
try:
    response = await self._make_request(url)
    data = self._parse_json_response(response)
    return ToolResult.success(data=data)

except requests.HTTPError as e:
    logger.error(f"HTTP error: {e}")
    return ToolResult.from_error(f"HTTP error: {e}")

except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return ToolResult.from_error(f"Query failed: {e}")
```

## 🎯 When to Use Each Base Class

### `BaseDatabaseLookupTool`
Use for: **Generic database queries**
- Custom HTTP methods
- Special response parsing
- Full control over request flow

### `BaseAPITool`
Use for: **REST APIs returning JSON**
- Simple GET/POST endpoints
- JSON request/response
- Quick API integration

### `BaseHTMLTool`
Use for: **Web scraping**
- Databases without API
- HTML page parsing
- BeautifulSoup integration

## 📦 Code Reuse Examples

### Example 1: Simple API Query

```python
from src.tools.external_databases.base import BaseAPITool

class UniprotTool(BaseAPITool):
    """UniProt database lookup."""
    TOOL_NAME = "uniprot"
    BASE_URL = "https://rest.uniprot.org/uniprotkb"
    RATE_LIMIT_DELAY = 0.2  # 200ms between requests

    async def execute(self, accession: str) -> ToolResult:
        endpoint = f"{accession}.json"
        try:
            data = await self._api_get(endpoint)
            return ToolResult.success(data=data)
        except Exception as e:
            return ToolResult.from_error(str(e))
```

### Example 2: HTML Scraping

```python
from src.tools.external_databases.base import BaseHTMLTool

class PDBTool(BaseHTMLTool):
    """PDB database lookup via HTML scraping."""
    TOOL_NAME = "pdb"
    BASE_URL = "https://www.rcsb.org/structure"

    async def execute(self, pdb_id: str) -> ToolResult:
        url = f"{self.BASE_URL}/{pdb_id}"
        try:
            soup = await self._get_html_soup(url)

            # Extract data using BeautifulSoup
            title = self._extract_text(soup.find("h1"))
            return ToolResult.success(data={"title": title})

        except Exception as e:
            return ToolResult.from_error(str(e))
```

### Example 3: Custom Parsing

```python
from src.tools.external_databases.base import BaseDatabaseLookupTool

class CustomCSVTool(BaseDatabaseLookupTool):
    """Tool for databases returning CSV."""
    TOOL_NAME = "custom_csv"
    BASE_URL = "https://api.example.com/data"

    async def execute(self, dataset: str) -> ToolResult:
        url = f"{self.BASE_URL}/{dataset}.csv"
        try:
            response = await self._make_request(url)
            rows = self._parse_csv_response(response)
            return ToolResult.success(data={"rows": rows})
        except Exception as e:
            return ToolResult.from_error(str(e))

    def _parse_csv_response(self, response):
        import csv
        reader = csv.DictReader(response.text.splitlines())
        return list(reader)
```

## 🔑 Key Configuration Parameters

All base classes support these configuration options:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEFAULT_TIMEOUT` | 10 | Request timeout (seconds) |
| `MAX_RETRIES` | 3 | Number of retry attempts |
| `RETRY_BACKOFF` | 0.5 | Exponential backoff factor |
| `RATE_LIMIT_DELAY` | 0.0 | Delay between requests (seconds) |
| `RETRY_STATUS_CODES` | [429, 500, 502, 503, 504] | HTTP codes to retry |

## 💡 Best Practices

### 1. Context Manager for Cleanup

```python
# Good: Automatic cleanup
async with tool as db:
    result = await db.execute("query")

# Manual cleanup
tool = MyTool()
result = await tool.execute("query")
await tool.close()
```

### 2. Batch Queries with Rate Limiting

```python
class MyTool(BaseAPITool):
    RATE_LIMIT_DELAY = 0.5  # Respect API limits

    async def batch_query(self, queries: list) -> ToolResult:
        results = []
        for query in queries:
            result = await self.execute(query)
            results.append(result)
        return ToolResult.success(data={"results": results})
```

### 3. Proper Error Handling

```python
async def execute(self, query: str) -> ToolResult:
    try:
        # Validate input
        if not query or not isinstance(query, str):
            return ToolResult.from_error("Invalid query")

        # Make request
        data = await self._api_get("search", params={"q": query})

        # Validate response
        if not data:
            return ToolResult.from_error("No results found")

        return ToolResult.success(data=data)

    except requests.Timeout:
        return ToolResult.from_error("Request timed out")
    except requests.HTTPError as e:
        return ToolResult.from_error(f"HTTP error: {e}")
    except Exception as e:
        logger.exception("Unexpected error")
        return ToolResult.from_error(f"Unexpected error: {e}")
```

## 📚 Next Steps

1. **Explore existing tools**: Look at `pubchem.py`, `expasy.py`, `rhea.py`
2. **Read examples**: Check `examples/` directory for usage demos
3. **Check tests**: See `tests/test_tools/test_*.py` for test patterns
4. **Add new database**: Use the base classes to create new integrations

## 🆘 Troubleshooting

### Import Error
```
ImportError: cannot import name 'BaseDatabaseLookupTool'
```
**Solution**: Make sure you're importing from the correct path:
```python
from src.tools.external_databases.base import BaseDatabaseLookupTool
```

### Session Not Closed
```
ResourceWarning: Unclosed <requests.Session>
```
**Solution**: Always close the session or use context manager:
```python
await tool.close()
# or
async with tool as db:
    ...
```

### Rate Limiting
```
HTTP 429: Too Many Requests
```
**Solution**: Add `RATE_LIMIT_DELAY` to your tool:
```python
class MyTool(BaseAPITool):
    RATE_LIMIT_DELAY = 1.0  # 1 second between requests
```
