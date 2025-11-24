#!/usr/bin/env python3
"""Basic simple chat demo using the GPTase framework.

This script loads the template LLM config (e.g., Kimi-K2) and performs
a single chat completion, printing the response.
"""

import json
import os
import sys
from pathlib import Path
import asyncio

# Ensure project root is on sys.path to import the local GPTase package
sys.path.append(str(Path(__file__).resolve().parent.parent))

from GPTase.models.manager import ModelManager
from GPTase.models.types import ModelConfig, ModelProvider, ModelRole


def load_template_config() -> dict:
    """Load template config from config/llm_config.template.json."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "llm_config.template.json"
    with open(config_path, "r") as f:
        return json.load(f)


async def run_demo():
    """Run a simple one-shot chat and print the response."""
    template = load_template_config()

    # Resolve API key: prefer template value unless it's missing/placeholder, then env
    tpl_key = template.get("api_key", "") or ""
    is_placeholder = isinstance(tpl_key, str) and tpl_key.strip().startswith("${")
    api_key = tpl_key if (tpl_key and not is_placeholder) else (
        os.getenv("OPENAI_API_KEY") or os.getenv("GPTASE_OPENAI_API_KEY") or ""
    )

    # Abort early if no API key resolved
    if not api_key:
        print("Missing OpenAI API key. Set OPENAI_API_KEY env or add api_key in config/llm_config.template.json.")
        return

    # Use OpenAI provider (real results), honoring custom base_url if provided
    manager = ModelManager(
        default_config=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name=template.get("model_name", "gpt-4o-mini"),
            api_key=api_key,
            base_url=template.get("base_url", None),
            temperature=float(template.get("temperature", 0.7)),
            max_tokens=int(template.get("max_tokens", 1000)),
        )
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello and tell me a fun fact."},
    ]

    response = await manager.generate(messages, role=ModelRole.GENERAL)
    print("Response:\n", response.content)


if __name__ == "__main__":
    asyncio.run(run_demo())
