"""JSON Schema validation helpers for agent input/output contracts.

Agents may declare ``inputs_schema`` and ``output_schema`` in their
frontmatter as JSON Schema dicts. ``DelegateTaskTool.execute`` calls
``validate_agent_inputs`` before delegating and ``validate_agent_output``
after the worker returns, surfacing violations as structured delegation
errors. Agents without schemas keep working unchanged.

The schema dicts themselves are validated at agent load time via
``check_schema`` so malformed schemas fail loudly during
``Agent.from_markdown`` rather than at first delegation.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


def _format_first_error(validator: Draft202012Validator, data: Any) -> Optional[str]:
    """Return a short error string from the first validation failure, or None."""
    error = next(iter(validator.iter_errors(data)), None)
    if error is None:
        return None
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


def validate_agent_inputs(
    data: Optional[Dict[str, Any]],
    schema: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Validate a task_inputs dict against an agent's ``inputs_schema``.

    Args:
        data: The ``task_inputs`` payload. ``None`` is treated as ``{}``.
        schema: The agent's declared ``inputs_schema``. ``None`` skips
            validation entirely.

    Returns:
        ``None`` on success (or when ``schema`` is ``None``); a short
        human-readable error string on failure.
    """
    if schema is None:
        return None
    validator = Draft202012Validator(schema)
    return _format_first_error(validator, data if data is not None else {})


def validate_agent_output(
    content: str,
    schema: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Validate a worker's ``result.data.content`` against ``output_schema``.

    Declaring ``output_schema`` is a contract that the worker emits
    JSON-encoded content. JSON parse failure is reported as a
    contract violation.

    Args:
        content: The string under ``result["data"]["content"]``.
        schema: The agent's declared ``output_schema``. ``None`` skips
            validation entirely.

    Returns:
        ``None`` on success (or when ``schema`` is ``None``); a short
        human-readable error string on failure.
    """
    if schema is None:
        return None
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        return f"content is not valid JSON: {exc}"
    validator = Draft202012Validator(schema)
    return _format_first_error(validator, parsed)


def check_schema(schema: Dict[str, Any], context: str) -> None:
    """Validate that ``schema`` is itself a well-formed JSON Schema.

    Called at agent load time so malformed schemas fail during
    ``Agent.from_markdown`` rather than at first delegation.

    Args:
        schema: The schema dict to check.
        context: Caller-supplied label for the error message (e.g.
            ``"agent 'my-agent' inputs_schema"``).

    Raises:
        ValueError: If the schema is malformed. ``Agent.from_markdown``
            wraps this into an ``AgentInitializationError``.
    """
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(
            f"{context} is not a valid JSON Schema: {exc.message}") from exc
