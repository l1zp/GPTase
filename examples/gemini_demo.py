#!/usr/bin/env python3
"""Gemini API demo using OpenAI-compatible endpoint.

Usage:
    # Set your API key first
    export GEMINI_API_KEY="your-api-key"

    # Run demo
    python examples/gemini_demo.py

    # Or specify config file
    python examples/gemini_demo.py --config config/llm_config.gemini.json
"""

import argparse
import asyncio
import json
import logging
import os

from gptase.models.model import Model
from gptase.models.types import ModelConfig
from gptase.utils import setup_logging
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)


def create_gemini_config(api_key: str = None) -> ModelConfig:
    """Create Gemini config with OpenAI-compatible endpoint.

    Args:
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var)

    Returns:
        ModelConfig for Gemini
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY not set. Run: export GEMINI_API_KEY='your-key'")

    return ModelConfig(
        provider="openai",
        model_name="gemini-2.0-flash",
        api_key=key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        temperature=0.7,
        max_tokens=4096,
        timeout=60,
    )


async def test_gemini(api_key: str = None, config_path: str = None) -> None:
    """Test Gemini API connection.

    Args:
        api_key: Optional API key override
        config_path: Optional path to config file
    """
    if config_path:
        with open(config_path, "r") as f:
            config_data = json.load(f)
        # Build ModelConfig directly from JSON config
        config = ModelConfig(
            provider=config_data.get("provider", "openai"),
            model_name=config_data.get("model_name", "gemini-2.0-flash"),
            api_key=config_data.get("api_key"),
            base_url=config_data.get("base_url"),
            temperature=config_data.get("temperature", 0.7),
            max_tokens=config_data.get("max_tokens", 4096),
            timeout=config_data.get("timeout", 60),
        )
        logger.info("Using config from: %s", config_path)
    else:
        config = create_gemini_config(api_key)

    model = Model(default_config=config)

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello! What model are you?"
        },
    ]

    logger.info("Testing Gemini API with model: %s", config.model_name)
    logger.info("Base URL: %s", config.base_url)

    # Test non-streaming
    print("\n[Non-streaming response]")
    try:
        response = await model.generate(messages, config=config)
        print(response.content)
        if response.usage:
            print(f"\nTokens used: {response.usage}")
    except Exception as e:
        logger.error("Request failed: %s", e)
        return

    # Test streaming
    print("\n[Streaming response]")
    messages[1]["content"] = "Count from 1 to 5, one number per line."

    try:
        async for chunk in model.generate_stream(messages, config=config):
            if chunk.content:
                print(chunk.content, end="", flush=True)
    except Exception as e:
        logger.error("Streaming failed: %s", e)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Gemini API Demo")
    parser.add_argument(
        "--api-key",
        type=str,
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file (e.g., config/llm_config.gemini.json)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(debug=args.debug)

    if not args.api_key and not args.config:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Error: No API key provided.\n"
                  "Set GEMINI_API_KEY env var or use --api-key or --config")
            return

    asyncio.run(test_gemini(api_key=args.api_key, config_path=args.config))


if __name__ == "__main__":
    main()
