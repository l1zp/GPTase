"""Utility functions for enzyme reaction extraction.

This module contains helper functions for data processing, validation,
and formatting that are used across the enzyme extraction pipeline.
"""

import logging
import re
from typing import Any, Dict, List

from src.utils import create_error_response as create_generic_error_response

# Fields that should be lists (sanitized from None to empty list)
_LIST_FIELDS_TO_SANITIZE = ["substrates", "products", "citations", "pdb_ids"]

# PDB ID pattern: 4-character codes starting with a digit (e.g., 1ABC)
_PDB_ID_PATTERN = r"\b[1-9][A-Za-z0-9]{3}\b"

# Step name for pipeline tracking
_STEP_NAME = "llm_extract"

logger = logging.getLogger(__name__)


def create_error_response(description: str, errors: List[str]) -> Dict[str, Any]:
    """Create a standardized error response for extraction failures.

    This is a convenience wrapper around the generic create_error_response
    utility that pre-fills the step_name for enzyme extraction.

    Args:
        description: Human-readable description of the error.
        errors: List of error messages.

    Returns:
        Dictionary matching the extraction result schema with error status.
    """
    return create_generic_error_response(_STEP_NAME, description, errors)


def extract_pdb_ids_from_text(text: str) -> List[str]:
    """Extract PDB IDs from text.

    PDB IDs are four-character codes starting with a digit (e.g., 1ABC).
    Returns sorted list of unique PDB IDs found in the text.

    Args:
        text: The text to search for PDB IDs.

    Returns:
        Sorted list of unique PDB IDs in uppercase.
    """
    candidates = re.findall(_PDB_ID_PATTERN, text)
    filtered = [c.upper() for c in candidates if any(ch.isalpha() for ch in c[1:])]
    return sorted(set(filtered))


def sanitize_reaction_list_fields(data: Dict[str, Any]) -> None:
    """Convert None values in list fields to empty lists.

    Args:
        data: The extraction data to sanitize in-place.
    """
    for reaction in data.get("reactions", []):
        for field in _LIST_FIELDS_TO_SANITIZE:
            if reaction.get(field) is None:
                reaction[field] = []


def merge_pdb_ids(data: Dict[str, Any], pdb_ids: List[str]) -> None:
    """Merge extracted PDB IDs into reaction data.

    Args:
        data: The extraction data to modify in-place.
        pdb_ids: List of PDB IDs to add to each reaction.
    """
    for reaction in data.get("reactions", []):
        existing = [pid.upper() for pid in reaction.get("pdb_ids", [])]
        reaction["pdb_ids"] = sorted(set(existing + pdb_ids))


def add_pipeline_validations(data: Dict[str, Any], pdb_ids: List[str]) -> None:
    """Add validation information to the pipeline metadata.

    Args:
        data: The extraction data to modify in-place.
        pdb_ids: List of extracted PDB IDs.
    """
    pipeline = data.setdefault("pipeline", {
        "steps": [],
        "validations": [],
        "errors": []
    })
    validations = pipeline.get("validations", [])
    validations.append(f"pdb_ids_extracted:{len(pdb_ids)}")
    pipeline["validations"] = validations
