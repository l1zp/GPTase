"""Core eval engine: EvalResult, schema validation, key fact assertions.

The heart of the evaluation framework. Two main public functions:

    validate_schema(data, schema_name) -> (bool, str)
    evaluate_key_facts(data, key_facts, agent_name) -> EvalResult

extract_field() implements a JSONPath-lite DSL used in golden.yaml:
    "statistics.total_variants"           dotted path
    "reactions[*].enzyme_name"            wildcard -> list of values
    "reactions[enzyme_name=Des27].kinetics.kcat/KM"  filter by field value
"""

from dataclasses import dataclass
from dataclasses import field
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from gptase.evals.schemas import SCHEMA_MAP

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Result for a single agent evaluation."""

    agent_name: str
    schema_valid: bool
    schema_error: str
    total_facts: int
    passed_facts: int
    failure_reason: str = ""
    failed_facts: List[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Fraction of key facts that passed (0.0 to 1.0)."""
        if self.total_facts == 0:
            return 1.0
        return self.passed_facts / self.total_facts


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_schema(data: dict, schema_name: str) -> Tuple[bool, str]:
    """Validate data against a named Pydantic schema.

    Args:
        data: Parsed agent output dict.
        schema_name: Key in SCHEMA_MAP (e.g. "enzyme_kinetics").

    Returns:
        (ok, error_message) -- error_message is empty string on success.
    """
    model_class = SCHEMA_MAP.get(schema_name)
    if model_class is None:
        return False, f"Unknown schema: {schema_name}"
    try:
        model_class.model_validate(data)
        return True, ""
    except ValidationError as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Field extraction (JSONPath-lite)
# ---------------------------------------------------------------------------


def extract_field(data: Any, field_path: str) -> Any:
    """Extract a value from nested data using a simple path DSL.

    Supports:
        "field"                         top-level key
        "a.b.c"                         dotted traversal
        "list[*].field"                 wildcard: list of all .field values
        "list[key=value].field"         filter: first match where item[key]==value,
                                        then optional .field traversal

    The filter value is compared as a string (case-sensitive).

    Returns:
        The extracted value, or None if the path does not resolve.
    """
    if not field_path or data is None:
        return None

    # Split on first '[' to detect array notation
    if "[" in field_path:
        bracket_idx = field_path.index("[")
        prefix = field_path[:bracket_idx]
        rest = field_path[bracket_idx:]

        # Navigate to the list
        node = _dotted_get(data, prefix) if prefix else data
        if not isinstance(node, list):
            return None

        # Parse bracket content
        close = rest.index("]")
        bracket_content = rest[1:close]
        after_bracket = rest[close + 1:]  # e.g. ".kinetics.kcat/KM"
        if after_bracket.startswith("."):
            after_bracket = after_bracket[1:]

        if bracket_content == "*":
            # Wildcard: collect field values from all items
            if after_bracket:
                return [_dotted_get(item, after_bracket) for item in node]
            return node
        elif "=" in bracket_content:
            # Filter: find first item where key==value
            key, value = bracket_content.split("=", 1)
            for item in node:
                if isinstance(item, dict) and str(item.get(key, "")) == value:
                    if after_bracket:
                        return _dotted_get(item, after_bracket)
                    return item
            return None
        else:
            # Integer index
            try:
                idx = int(bracket_content)
                item = node[idx]
                if after_bracket:
                    return _dotted_get(item, after_bracket)
                return item
            except (ValueError, IndexError):
                return None
    else:
        return _dotted_get(data, field_path)


def _dotted_get(data: Any, path: str) -> Any:
    """Traverse a dotted path through nested dicts.

    Handles keys that contain '/' (e.g. 'kcat/KM').
    """
    if not path or data is None:
        return data

    # Split only on '.' that are not inside a key containing '/'
    # Strategy: split on '.' and greedily join segments that don't exist
    # as keys until we find a match.
    parts = path.split(".")
    node = data

    i = 0
    while i < len(parts):
        if not isinstance(node, dict):
            return None

        # Try joining consecutive parts until we find a key match
        matched = False
        for j in range(len(parts), i, -1):
            candidate = ".".join(parts[i:j])
            if candidate in node:
                node = node[candidate]
                i = j
                matched = True
                break

        if not matched:
            return None

    return node


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def _normalize_to_str_list(value: Any) -> List[str]:
    """Coerce a value to a list of strings for membership checks."""
    if not isinstance(value, list):
        value = [value]
    return [str(v) for v in value]


def _truncate_text(value: Any, limit: int = 160) -> str:
    """Return a shortened string representation for failure messages."""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _check_condition(actual: Any, condition: str, spec: dict) -> Tuple[bool, str]:
    """Evaluate a single condition against an actual value.

    Returns (passed, failure_description).
    """
    if actual is None:
        return False, f"field resolved to None"

    if condition == "length_gte":
        expected = spec["value"]
        try:
            length = len(actual)
        except TypeError:
            return False, f"cannot take len() of {type(actual).__name__}"
        if length >= expected:
            return True, ""
        return False, f"length {length} < {expected}"

    elif condition == "gte":
        expected = spec["value"]
        try:
            if float(actual) >= float(expected):
                return True, ""
            return False, f"{actual} < {expected}"
        except (TypeError, ValueError):
            return False, f"cannot compare {actual!r} >= {expected}"

    elif condition == "approx_eq":
        expected = spec["value"]
        tolerance = spec.get("tolerance", 0.15)
        try:
            actual_f = float(actual)
            expected_f = float(expected)
        except (TypeError, ValueError):
            return False, f"cannot convert to float: actual={actual!r}, expected={expected!r}"

        if expected_f == 0:
            if actual_f == 0:
                return True, ""
            return False, f"expected 0, got {actual_f}"

        rel_diff = abs(actual_f - expected_f) / abs(expected_f)
        pct = rel_diff * 100
        if rel_diff <= tolerance:
            return True, ""
        return False, f"expected ~{expected_f}, got {actual_f} (diff {pct:.1f}%)"

    elif condition == "contains":
        value = spec["value"]
        if value in str(actual):
            return True, ""
        return False, f"{value!r} not in {str(actual)!r}"

    elif condition == "contains_all":
        values = spec["values"]
        actual_strs = _normalize_to_str_list(actual)
        missing = [
            value for value in values
            if not any(value in candidate for candidate in actual_strs)
        ]
        if not missing:
            return True, ""
        return False, (f"missing values: {missing}; checked against "
                       f"{_truncate_text(actual_strs)}")

    elif condition == "contains_any":
        values = spec["values"]
        actual_strs = _normalize_to_str_list(actual)
        if any(value in candidate for value in values for candidate in actual_strs):
            return True, ""
        return False, (f"none of {values} found in {_truncate_text(actual_strs)}")

    else:
        return False, f"unknown condition: {condition!r}"


# ---------------------------------------------------------------------------
# Key fact evaluation
# ---------------------------------------------------------------------------


def evaluate_key_facts(
    data: dict,
    key_facts: List[dict],
    agent_name: str,
    schema_valid: bool = True,
    schema_error: str = "",
) -> EvalResult:
    """Evaluate a list of key_fact assertions against agent output data.

    Args:
        data: Parsed agent output dict.
        key_facts: List of assertion dicts from golden.yaml.
        agent_name: Name used in EvalResult and failure messages.
        schema_valid: Result of Pydantic schema validation.
        schema_error: Error string if schema validation failed.

    Returns:
        Fully populated EvalResult.
    """
    passed = 0
    failed = []

    for fact in key_facts:
        field_path = fact.get("field", "")
        condition = fact.get("condition", "")
        actual = extract_field(data, field_path)
        ok, reason = _check_condition(actual, condition, fact)

        if ok:
            passed += 1
        else:
            failed.append(f"{agent_name}: {field_path} [{condition}] -- {reason}")

    return EvalResult(
        agent_name=agent_name,
        schema_valid=schema_valid,
        schema_error=schema_error,
        failure_reason="",
        total_facts=len(key_facts),
        passed_facts=passed,
        failed_facts=failed,
    )
