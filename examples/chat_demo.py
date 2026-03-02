#!/usr/bin/env python3
"""Simple chat demo with streaming and thinking mode support."""

import argparse
import asyncio
import json
import logging

from gptase.core.config import FrameworkConfig
from gptase.models.model import Model
from gptase.models.types import ModelConfig
from gptase.utils import default_manager

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Configure logging format and level.

    Args:
        debug: If True, set log level to DEBUG; otherwise INFO.
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_model_manager(config_path: str = None, enable_tracking: bool = True):
    """Create a ModelManager with optional custom config.

    Args:
        config_path: Path to custom config file
        enable_tracking: Whether to enable conversation tracking

    Returns:
        Tuple of (ModelManager, ModelConfig)
    """
    if config_path:
        with open(config_path, "r") as f:
            config_data = json.load(f)
        framework_config = FrameworkConfig(**config_data)
        model_config = framework_config.get_model_config()
        manager = Model(default_config=model_config, enable_tracking=enable_tracking)
        logger.info("Testing config: %s", config_path)
        return manager, manager.default_config
    return default_manager(enable_tracking=enable_tracking), None


def get_config_with_thinking(manager, base_config, enable_thinking: bool):
    """Get config with thinking mode applied.

    Args:
        manager: ModelManager instance
        base_config: Base config (None for default manager)
        enable_thinking: Whether to enable thinking mode

    Returns:
        ModelConfig with thinking setting
    """
    if base_config is not None:
        return base_config
    return ModelConfig(
        provider=manager.default_config.provider,
        model_name=manager.default_config.model_name,
        api_key=manager.default_config.api_key,
        base_url=manager.default_config.base_url,
        temperature=manager.default_config.temperature,
        max_tokens=manager.default_config.max_tokens,
        timeout=manager.default_config.timeout,
        thinking=manager.default_config.thinking,
        enable_thinking=enable_thinking,
        provider_config=manager.default_config.provider_config,
    )


async def run_streaming_demo(enable_thinking: bool = True,
                             config_path: str = None) -> None:
    """Run streaming chat demo with optional thinking mode.

    Args:
        enable_thinking: Whether to enable thinking mode
        config_path: Path to custom config file to test
    """
    try:
        manager, base_config = create_model_manager(config_path)
        await manager.initialize_tracking()
    except Exception as e:
        logger.error("Error loading config: %s", e, exc_info=True)
        return

    config = get_config_with_thinking(manager, base_config, enable_thinking)
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

    logger.info("Thinking mode: %s",
                "enabled" if config.is_thinking_enabled() else "disabled")

    is_thinking = False

    try:
        async for chunk in manager.generate_stream(messages, config=config):
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

    except Exception as e:
        logger.error("Streaming error: %s", e, exc_info=True)
    finally:
        await manager.shutdown()


async def run_simple_demo(enable_thinking: bool = False) -> None:
    """Run a simple one-shot chat without streaming.

    Args:
        enable_thinking: Whether to enable thinking mode
    """
    try:
        manager = default_manager(enable_tracking=True)
        await manager.initialize_tracking()
    except ValueError as e:
        logger.error("Initialization error: %s", e)
        return

    config = get_config_with_thinking(manager, None, enable_thinking)
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Explain why the sky is blue."
        },
    ]

    logger.info("Thinking mode: %s", "enabled" if enable_thinking else "disabled")

    try:
        response = await manager.generate(messages, config=config)

        if response.reasoning_content:
            print("[Thinking]")
            print(response.reasoning_content)
            print("\n[Answer]")

        print(response.content)

        if response.usage:
            print(f"\nTokens: {response.usage.get('total_tokens', 'N/A')}")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
    finally:
        await manager.shutdown()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="GPTase Chat Demo - Test different thinking configurations")
    parser.add_argument("--simple", action="store_true", help="Non-streaming mode")
    parser.add_argument("--no-thinking",
                        action="store_true",
                        help="Disable thinking mode (enabled by default)")
    parser.add_argument("--config", type=str, help="Path to custom config file")
    parser.add_argument("--debug",
                        action="store_true",
                        help="Enable debug-level logging")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(debug=args.debug)

    enable_thinking = not args.no_thinking

    if args.simple:
        asyncio.run(run_simple_demo(enable_thinking=enable_thinking))
    else:
        asyncio.run(
            run_streaming_demo(enable_thinking=enable_thinking,
                               config_path=args.config))


if __name__ == "__main__":
    main()
