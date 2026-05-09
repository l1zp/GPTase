#!/usr/bin/env python3
"""Simple chat demo with streaming and thinking mode support."""

import argparse
import asyncio
import json
import logging

from gptase.models.model import Model
from gptase.models.types import ModelConfig
from gptase.utils import default_manager
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)


def create_model(config_path: str = None) -> tuple[Model, ModelConfig]:
    """Create a Model with optional custom config.

    Returns:
        Tuple of (Model, ModelConfig)
    """
    if config_path:
        with open(config_path, "r") as f:
            config_data = json.load(f)
        framework_config = FrameworkConfig(**config_data)
        model_config = framework_config.to_model_config()
        model = Model(default_config=model_config, enable_tracking=True)
        logger.info("Loaded config: %s", config_path)
        return model, model_config

    model = default_manager(enable_tracking=True)
    return model, model.default_config


async def run_demo(
    stream: bool = True,
    thinking: bool = False,
    config_path: str = None,
) -> None:
    """Run chat demo.

    Args:
        stream: Whether to use streaming mode
        thinking: Whether to enable thinking/reasoning mode
        config_path: Path to custom config file
    """
    try:
        model, base_config = create_model(config_path)
        await model.initialize_tracking()
    except Exception as e:
        logger.error("Error loading config: %s", e, exc_info=True)
        return

    # Apply CLI overrides on top of config
    config = ModelConfig(
        model_name=base_config.model_name,
        api_key=base_config.api_key,
        base_url=base_config.base_url,
        temperature=base_config.temperature,
        max_tokens=base_config.max_tokens,
        timeout=base_config.timeout,
        stream=stream,
        enable_thinking=thinking,
    )

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Explain why the sky is blue in simple terms."
        },
    ]

    print(f"Model: {config.model_name}")
    print(f"Stream: {stream} | Thinking: {thinking}")
    print("---")

    try:
        if stream:
            await _run_stream(model, messages, config)
        else:
            await _run_simple(model, messages, config)
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
    finally:
        await model.shutdown()


async def _run_stream(model: Model, messages, config: ModelConfig) -> None:
    """Stream response chunks to stdout."""
    is_thinking = False

    async for chunk in model.generate_stream(messages, config=config):
        if chunk.is_thinking and chunk.reasoning_content:
            if not is_thinking:
                print("[Thinking]")
                is_thinking = True
            print(chunk.reasoning_content, end="", flush=True)
        elif chunk.content and not chunk.is_thinking:
            if is_thinking:
                print("\n\n[Answer]")
                is_thinking = False
            print(chunk.content, end="", flush=True)

        if chunk.is_complete and "usage" in chunk.metadata:
            usage = chunk.metadata["usage"]
            print(f"\n\nTokens: {usage.get('total_tokens', 'N/A')}")


async def _run_simple(model: Model, messages, config: ModelConfig) -> None:
    """One-shot response to stdout."""
    response = await model.generate(messages, config=config)

    if response.reasoning_content:
        print("[Thinking]")
        print(response.reasoning_content)
        print("\n[Answer]")

    print(response.content)

    if response.usage:
        print(f"\nTokens: {response.usage.get('total_tokens', 'N/A')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPTase Chat Demo")
    parser.add_argument("--stream",
                        action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Enable/disable streaming (default: on)")
    parser.add_argument("--thinking",
                        action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Enable/disable thinking mode (default: on)")
    parser.add_argument("--config", type=str, help="Path to custom config file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(
        run_demo(stream=args.stream, thinking=args.thinking, config_path=args.config))


if __name__ == "__main__":
    main()
