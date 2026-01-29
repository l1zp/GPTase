#!/usr/bin/env python3
"""Simple chat demo with streaming and thinking mode support."""

import asyncio
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.config import FrameworkConfig
from src.models.types import ModelRole


def load_custom_config(config_path: str) -> dict:
    """Load custom configuration from JSON file.

    Args:
        config_path: Path to the configuration JSON file

    Returns:
        Configuration dictionary
    """
    with open(config_path, "r") as f:
        return json.load(f)


def create_config_legacy(manager, enable_thinking: bool):
    """Create a config with legacy enable_thinking format.

    Args:
        manager: ModelManager instance
        enable_thinking: Whether to enable thinking mode (legacy format)
    """
    existing_config = manager.get_role_config(ModelRole.GENERAL)
    return existing_config.model_copy(update={"enable_thinking": enable_thinking})


async def run_streaming_demo(enable_thinking: bool = True, config_path: str = None):
    """Run streaming chat demo with optional thinking mode.

    Args:
        enable_thinking: Whether to enable thinking mode (legacy format)
        config_path: Path to custom config file to test
    """
    from src.models.model import Model

    try:
        if config_path:
            config_data = load_custom_config(config_path)
            framework_config = FrameworkConfig(**config_data)
            model_config = framework_config.get_model_config()
            manager = Model(default_config=model_config, enable_tracking=True)
            print(f"Testing config: {config_path}\n")

            # Display which thinking format is being used
            if "thinking" in config_data:
                print(
                    f"Using NEW thinking format: thinking.type = '{config_data['thinking']['type']}'"
                )
            elif "enable_thinking" in config_data:
                print(
                    f"Using LEGACY thinking format: enable_thinking = {config_data['enable_thinking']}"
                )
            print()
        else:
            from src.utils import default_manager

            manager = default_manager(enable_tracking=True)

        await manager.initialize_tracking()
    except Exception as e:
        print(f"Error loading config: {e}")
        import traceback

        traceback.print_exc()
        return

    # Get config for the model
    if config_path:
        config = manager.get_role_config(ModelRole.GENERAL)
    else:
        config = create_config_legacy(manager, enable_thinking)

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

    print(
        f"Thinking mode: {'enabled' if config.is_thinking_enabled() else 'disabled'}\n")

    is_thinking = False

    try:
        async for chunk in manager.generate_stream(messages,
                                                   role=ModelRole.GENERAL,
                                                   config=config):
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

            if chunk.is_complete:
                if "usage" in chunk.metadata:
                    usage = chunk.metadata["usage"]
                    print(f"\n\nTokens: {usage.get('total_tokens', 'N/A')}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.shutdown()


async def run_simple_demo(enable_thinking: bool = False):
    """Run a simple one-shot chat without streaming."""
    from src.utils import default_manager

    try:
        manager = default_manager(enable_tracking=True)
        await manager.initialize_tracking()
    except ValueError as e:
        print(f"Error: {e}")
        return

    config = create_config_legacy(manager, enable_thinking)

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

    print(f"Thinking mode: {'enabled' if enable_thinking else 'disabled'}\n")

    try:
        response = await manager.generate(messages,
                                          role=ModelRole.GENERAL,
                                          config=config)

        if response.reasoning_content:
            print("[Thinking]")
            print(response.reasoning_content)
            print("\n[Answer]")

        print(response.content)

        if response.usage:
            print(f"\nTokens: {response.usage.get('total_tokens', 'N/A')}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await manager.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="GPTase Chat Demo - Test different thinking configurations")
    parser.add_argument("--simple", action="store_true", help="Non-streaming mode")
    parser.add_argument("--thinking", action="store_true", help="Enable thinking mode")
    parser.add_argument("--no-thinking",
                        action="store_true",
                        help="Disable thinking mode")
    parser.add_argument(
        "--config",
        type=str,
        help=
        "Path to custom config file to test (e.g., config/llm_config.template.json or config/llm_config.qwen.example.json)"
    )
    args = parser.parse_args()

    if args.simple:
        enable_thinking = args.thinking
        asyncio.run(run_simple_demo(enable_thinking=enable_thinking))
    else:
        # Streaming mode
        if args.config:
            # When using custom config, ignore --thinking and --no-thinking flags
            enable_thinking = True  # Will be overridden by config file
            asyncio.run(
                run_streaming_demo(enable_thinking=enable_thinking,
                                   config_path=args.config))
        else:
            # Use command line flags
            enable_thinking = not args.no_thinking
            asyncio.run(run_streaming_demo(enable_thinking=enable_thinking))
