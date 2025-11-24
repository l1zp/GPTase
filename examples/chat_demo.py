#!/usr/bin/env python3
"""Basic simple chat demo using the GPTase framework.

This script loads the template LLM config (e.g., Kimi-K2) and performs
a single chat completion, printing the response.
"""

import json
import sys
from pathlib import Path
import asyncio

# Ensure project root is on sys.path to import the local GPTase package
sys.path.append(str(Path(__file__).resolve().parent.parent))

from GPTase.models.types import ModelRole


def load_template_config() -> dict:
    """Load template config from config/llm_config.template.json."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "llm_config.template.json"
    with open(config_path, "r") as f:
        return json.load(f)


async def run_demo():
    """Run a simple one-shot chat and print the response."""
    # Use default manager configuration
    from src.utils import default_manager
    try:
        manager = default_manager()
    except ValueError as e:
        print(e)
        return

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello and tell me a fun fact."},
    ]

    response = await manager.generate(messages, role=ModelRole.GENERAL)
    print("Response:\n", response.content)


if __name__ == "__main__":
    asyncio.run(run_demo())
