"""
Utility tools for calculation and web search.
"""

import logging
from typing import Any, Dict

from src.core.constants import Timeouts
from src.tools.base import tool

logger = logging.getLogger(__name__)

# Calculator constants
_CALC_ALLOWED_CHARS = set("0123456789+-*/.() ")


# Simple tools using @tool decorator
@tool(
    name="calculator",
    description="Perform mathematical calculations safely",
    timeout=Timeouts.CALCULATOR,
)
async def calculate(expression: str) -> Dict[str, Any]:
    """Evaluate a safe mathematical expression.

    Args:
        expression: Mathematical expression to evaluate (e.g., '2+2', '3*4/2').

    Returns:
        Dictionary with expression, result, and result type.

    Raises:
        ValueError: If expression contains invalid characters.
    """
    if not all(c in _CALC_ALLOWED_CHARS for c in expression):
        raise ValueError(f"Invalid characters in expression: {expression}")

    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {
            "expression": expression,
            "result": float(result) if isinstance(result, int) else result,
            "type": type(result).__name__,
        }
    except Exception as e:
        raise ValueError(f"Failed to evaluate expression: {e}")


# Simple tools using @tool decorator
@tool(
    name="web_search",
    description="Search the web for information (mock implementation)",
    timeout=Timeouts.WEB_SEARCH,
)
async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Mock web search - integrate with search APIs in production.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default: 5).

    Returns:
        Dictionary with query, mock results, and total count.
    """
    query_slug = query.replace(" ", "-")
    mock_results = [{
        "title": f"Result {i + 1} for '{query}'",
        "url": f"https://example.com/search/{query_slug}-{i + 1}",
        "snippet": f"This is a mock search result snippet for {query}...",
    } for i in range(max_results)]

    return {"query": query, "results": mock_results, "total_found": len(mock_results)}


# Backward compatibility: create wrapper classes if needed,
# but @tool already returns a FunctionTool which implements BaseTool.
