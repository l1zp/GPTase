"""Shared utilities for creating standardized agent responses.

This module provides helper functions to create consistent response
dictionaries across all agents, reducing code duplication and ensuring
a uniform response structure.
"""

from typing import Any, Dict, Optional

from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS


def create_error_response(
    error: str,
    agent_id: str,
    task_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a standardized error response.

    Args:
        error: Error message describing what went wrong.
        agent_id: ID of the agent reporting the error.
        task_id: Optional task ID.
        metadata: Optional additional metadata.

    Returns:
        Standardized error response dictionary with status, error,
        agent_id, and optional task_id and metadata fields.
    """
    response: Dict[str, Any] = {
        "status": STATUS_ERROR,
        "error": error,
        "agent_id": agent_id,
    }
    if task_id:
        response["task_id"] = task_id
    if metadata:
        response["metadata"] = metadata
    return response


def create_success_response(
    data: Any,
    agent_id: str,
    summary: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a standardized success response.

    Args:
        data: Result data to return.
        agent_id: ID of the agent.
        summary: Optional summary message.
        metadata: Optional additional metadata.

    Returns:
        Standardized success response dictionary with status, data,
        agent_id, and optional summary and metadata fields.
    """
    response: Dict[str, Any] = {
        "status": STATUS_SUCCESS,
        "data": data,
        "agent_id": agent_id,
    }
    if summary:
        response["summary"] = summary
    if metadata:
        response["metadata"] = metadata
    return response
