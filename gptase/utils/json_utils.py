"""Shared JSON parsing utilities for agent output content."""

import json
from typing import Optional


def parse_json_content(content: str) -> Optional[dict]:
    """Parse JSON from an agent content string, handling markdown code blocks.

    Attempts extraction in order:
      1. ```json ... ``` fenced block
      2. ``` ... ``` generic fenced block
      3. Direct JSON if content starts with ``{`` or ``[``

    Args:
        content: Raw string from agent output (may contain markdown).

    Returns:
        Parsed dict/list, or None if no valid JSON could be extracted.
    """
    if not content:
        return None

    content = content.strip()

    if "```json" in content:
        parts = content.split("```json")
        if len(parts) > 1:
            json_part = parts[1].split("```")[0].strip()
            try:
                return json.loads(json_part)
            except (json.JSONDecodeError, ValueError):
                pass
    elif content.startswith("```"):
        parts = content.split("```")
        if len(parts) > 1:
            json_part = parts[1].strip()
            if "\n" in json_part:
                json_part = json_part.split("\n", 1)[1]
            try:
                return json.loads(json_part)
            except (json.JSONDecodeError, ValueError):
                pass

    if content.startswith("{") or content.startswith("["):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass

    return None
