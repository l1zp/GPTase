# External Database Lookup Tools

This directory contains tools for querying external biochemical and molecular biology databases.

## 🚀 Quick Links

- **[Quick Start Guide](QUICKSTART.md)** - Get started in 5 minutes
- **[Reusable Base Classes](#base-classes)** - Create new database tools easily
- **[Available Tools](#available-tools)** - PubChem, ExPASy, Rhea
- **[Template](#template)** - Copy-paste template for new tools

---

## 🎯 Base Classes (Reusable Components)

We provide three base classes to help you quickly create new database tools:

| Base Class | Use Case | Features |
|------------|----------|----------|
| [`BaseDatabaseLookupTool`](base.py) | Generic database queries | HTTP session, retry logic, error handling |
| [`BaseAPITool`](base.py) | REST APIs (JSON) | `_api_get()`, `_api_post()` convenience methods |
| [`BaseHTMLTool`](base.py) | Web scraping | BeautifulSoup integration, HTML parsing |

**Example: Create a new database tool in 30 seconds**

```python
from src.tools.external_databases.base import BaseAPITool

class UniprotTool(BaseAPITool):
    TOOL_NAME = "uniprot"
    BASE_URL = "https://rest.uniprot.org/uniprotkb"
    RATE_LIMIT_DELAY = 0.2

    async def execute(self, accession: str) -> ToolResult:
        endpoint = f"{accession}.json"
        data = await self._api_get(endpoint)
        return ToolResult.success(data=data)
```

See [QUICKSTART.md](QUICKSTART.md) for more examples.

---

## Available Tools

### PubChem (`pubchem.py`)

**Purpose**: Retrieve compound information from PubChem database

**Capabilities**:
- Search compounds by name, CID, or SMILES
- Retrieve SMILES strings, molecular formulas, and weights
- Extract CAS numbers from synonyms

**Database**: https://pubchem.ncbi.nlm.nih.gov/

**API**: PubChem PUG REST API

**Example Usage**:
```python
from src.tools.external_databases.pubchem import PubChemSMILESLookupTool

tool = PubChemSMILESLookupTool()
result = await tool.execute(compound_names=["acetone", "ethanol"])
```

**Demo Script**: `examples/pubchem_lookup_demo.py`

---

### ExPASy (`expasy.py`)

**Purpose**: Retrieve enzyme reaction information from ExPASy enzyme database

**Capabilities**:
- Query enzymes by EC number
- Retrieve enzyme names and catalyzed reactions
- Extract substrates, products, and cofactors
- Get enzyme comments and literature references
- Access alternate enzyme names (synonyms)

**Database**: https://enzyme.expasy.org/

**API**: HTML scraping (no official REST API)

**Example Usage**:
```python
from src.tools.external_databases.expasy import ExPAsyEnzymeLookupTool

tool = ExPAsyEnzymeLookupTool()
result = await tool.execute(ec_numbers=["1.1.1.1", "4.1.1.48"])

# Access extracted data
for enzyme in result.data["enzymes"]:
    print(f"EC: {enzyme['ec_number']}")
    print(f"Name: {enzyme['enzyme_name']}")
    print(f"Reaction: {enzyme['reaction']}")
    print(f"Substrates: {enzyme['substrates']}")
    print(f"Products: {enzyme['products']}")
    print(f"Cofactors: {enzyme['cofactors']}")
    print(f"Comments: {len(enzyme['comments'])} functional annotations")
```

**Demo Script**: `examples/ec_number_lookup_demo.py`

**Extracted Data**: See [EXAMPLES.md](EXAMPLES.md) for detailed examples of real extracted data including:
- Alcohol dehydrogenase (EC 1.1.1.1) - with substrate specificity and cross-references
- Indole-3-glycerol-phosphate synthase (EC 4.1.1.48) - with pathway context
- Phosphoribosylanthranilate isomerase (EC 5.3.1.24) - with reaction mechanism

**Data Coverage**:
| Field | Coverage | Description |
|-------|----------|-------------|
| Enzyme Name | 100% | Official IUBMB name |
| Reaction | 95%+ | Catalyzed reaction description |
| Substrates/Products | 80% | Parsed from reaction equation |
| Cofactors | 60% | Explicitly listed when available |
| Comments | 90%+ | Functional annotations |
| Alternate Names | 40% | Synonyms and former names |

---

## Common Features

All tools in this directory share these characteristics:

1. **Async/Await**: All tools use async operations for non-blocking queries
2. **Retry Logic**: Automatic retry with exponential backoff for failed requests
3. **Timeout Configuration**: Configurable request timeouts
4. **Structured Output**: Return `ToolResult` objects with standardized data format
5. **Error Handling**: Graceful error handling with informative messages

## Adding New Database Tools

When adding support for a new external database:

1. Create a new file named after the database (e.g., `pdb.py`, `uniprot.py`)
2. Inherit from `BaseTool` class
3. Implement `execute()` method with async support
4. Add retry logic for HTTP requests
5. Return results as `ToolResult.success()` or `ToolResult.from_error()`
6. Create a demo script in `examples/`
7. Update this README with database information

## Template

```python
"""Database name lookup tool.

Description of what this tool does.
"""

import logging
from typing import Any, Dict, List
import requests

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class NewDatabaseLookupTool(BaseTool):
    """Tool for looking up data from NewDatabase."""

    TOOL_NAME = "new_database_lookup"

    BASE_URL = "https://api.database.com"
    DEFAULT_TIMEOUT = 10

    def __init__(self):
        super().__init__(
            name=self.TOOL_NAME,
            description="Look up data from NewDatabase",
        )
        self._session = requests.Session()

    async def execute(self, query_params: Dict[str, Any]) -> ToolResult:
        """Execute lookup with given parameters.

        Args:
            query_params: Dictionary of query parameters

        Returns:
            ToolResult with lookup results
        """
        # Implementation here
        pass

    async def close(self):
        """Cleanup resources."""
        if self._session:
            self._session.close()
```

## Rate Limiting

When querying external databases, be aware of rate limits:

- **PubChem**: No official rate limit, but be reasonable
- **ExPASy**: No official rate limit, but recommend 1 request/second
- Always implement delays between bulk requests
- Consider caching results to avoid redundant queries

## Future Enhancements

Potential databases to add:
- **UniProt**: Protein sequence and function data
- **PDB/RCSB**: Protein 3D structure information
- **ChEBI**: Chemical entities of biological interest
- **KEGG**: Pathway and network data
- **BRENDA**: Comprehensive enzyme information
- **PubMed**: Literature search and citation data
