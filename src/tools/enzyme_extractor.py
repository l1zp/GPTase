"""Enzyme design step extraction from text and HTML.

This module provides functions to extract enzyme design steps from
text or HTML content by scoring snippets against keyword categories.
"""

import re
from typing import Any, Dict, List

from .enzyme_terms import CATEGORY_ZH, TERMS

# Scoring thresholds
MIN_CONFIDENCE_THRESHOLD = 0.3
DEFAULT_SNIPPET_LENGTH = 240

# Scoring parameters
KEYWORD_HIT_BASE_SCORE = 0.6
MIN_SNIPPET_LENGTH = 50
MAX_SNIPPET_LENGTH = 1000
LENGTH_PENALTY_THRESHOLD = 1000

# Status values
STATUS_SUCCESS = "success"

# Component categories
COMPONENT_DESIGN = "Design"
COMPONENT_ASSAY = "Assay"
COMPONENT_OPTIMIZATION = "Optimization"


def normalize_text(text: str) -> str:
    """Normalize text by normalizing line endings.

    Args:
        text: Raw text content.

    Returns:
        Text with consistent line endings.
    """
    t = text.replace("\r", "\n")
    t = re.sub(r"\n{2,}", "\n", t)
    return t


def _score_snippet(snippet: str, keywords: List[str]) -> float:
    """Score a snippet based on keyword matches.

    Args:
        snippet: Text snippet to score.
        keywords: List of keywords to search for.

    Returns:
        Score between 0 and 1 based on keyword matches and length.
    """
    s = snippet.lower()
    hits = sum(1 for k in keywords if k.lower() in s)
    if hits == 0:
        return 0.0

    length_penalty = min(1.0, LENGTH_PENALTY_THRESHOLD / max(MIN_SNIPPET_LENGTH, len(snippet)))
    base = min(1.0, KEYWORD_HIT_BASE_SCORE * hits)
    return round(base * length_penalty, 3)


def _strip_html(html: str) -> str:
    """Remove HTML tags from content.

    Args:
        html: HTML content.

    Returns:
        Plain text with HTML tags removed.
    """
    return re.sub(r"<[^>]+>", " ", html)


def extract_steps(text: str) -> Dict[str, Any]:
    """Extract enzyme design steps from text content.

    Analyzes paragraphs to identify relevant enzyme design steps
    based on keyword matching against predefined categories.

    Args:
        text: Text content to analyze.

    Returns:
        Dictionary with status, steps list, components by category,
        and overall confidence score.
    """
    txt = normalize_text(text)
    paragraphs = [p.strip() for p in re.split(r"\n+", txt) if p.strip()]
    results: List[Dict[str, Any]] = []
    step_id = 1

    for paragraph in paragraphs:
        cat_scores = _score_categories(paragraph)
        for category, score in cat_scores.items():
            if score >= MIN_CONFIDENCE_THRESHOLD:
                results.append(_create_step_record(
                    str(step_id), category, paragraph, score
                ))
                step_id += 1

    overall_conf = _calculate_overall_confidence(results)
    components = _group_by_component(results)

    return {
        "status": STATUS_SUCCESS,
        "steps": results,
        "components": components,
        "confidence_overall": overall_conf,
    }


def _score_categories(text: str) -> Dict[str, float]:
    """Score text against all keyword categories.

    Args:
        text: Text to score.

    Returns:
        Dictionary mapping category names to scores.
    """
    return {cat: _score_snippet(text, kws) for cat, kws in TERMS.items()}


def _create_step_record(
    step_id: str, category: str, description: str, confidence: float
) -> Dict[str, Any]:
    """Create a step record dictionary.

    Args:
        step_id: Unique step identifier.
        category: Category name.
        description: Full description text.
        confidence: Confidence score.

    Returns:
        Step record dictionary.
    """
    return {
        "step_id": step_id,
        "category": category,
        "label_zh": CATEGORY_ZH.get(category, category),
        "description": description,
        "evidence": description[:DEFAULT_SNIPPET_LENGTH],
        "confidence": confidence,
    }


def _calculate_overall_confidence(results: List[Dict[str, Any]]) -> float:
    """Calculate overall confidence from results.

    Args:
        results: List of step result dictionaries.

    Returns:
        Average confidence score rounded to 3 decimals.
    """
    if not results:
        return 0.0
    return round(
        sum(r["confidence"] for r in results) / len(results), 3
    )


def _group_by_component(results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Group step descriptions by component category.

    Args:
        results: List of step result dictionaries.

    Returns:
        Dictionary mapping component names to description lists.
    """
    return {
        COMPONENT_DESIGN: [
            r["description"] for r in results if r["category"] == COMPONENT_DESIGN
        ],
        COMPONENT_ASSAY: [
            r["description"] for r in results if r["category"] == COMPONENT_ASSAY
        ],
        COMPONENT_OPTIMIZATION: [
            r["description"] for r in results if r["category"] == COMPONENT_OPTIMIZATION
        ],
    }


def extract_from_html(html: str) -> Dict[str, Any]:
    """Extract enzyme design steps from HTML content.

    Strips HTML tags and processes as plain text.

    Args:
        html: HTML content to analyze.

    Returns:
        Dictionary with extraction results.
    """
    return extract_steps(_strip_html(html))
