#!/usr/bin/env python3
"""Simple chat demo with streaming and thinking mode support."""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models.types import ModelRole


def create_config(manager, enable_thinking: bool):
    """Create a config with thinking mode setting applied."""
    existing_config = manager.get_role_config(ModelRole.GENERAL)
    return existing_config.model_copy(update={"enable_thinking": enable_thinking})


async def run_streaming_demo(enable_thinking: bool = True):
    """Run streaming chat demo with optional thinking mode."""
    from src.utils import default_manager

    try:
        manager = default_manager(enable_tracking=True)
        await manager.initialize_tracking()
    except ValueError as e:
        print(f"Error: {e}")
        return

    config = create_config(manager, enable_thinking)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain why the sky is blue."},
    ]

    print(f"Thinking mode: {'enabled' if enable_thinking else 'disabled'}\n")

    is_thinking = False

    try:
        async for chunk in manager.generate_stream(
            messages, role=ModelRole.GENERAL, config=config
        ):
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

    config = create_config(manager, enable_thinking)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain why the sky is blue."},
    ]

    print(f"Thinking mode: {'enabled' if enable_thinking else 'disabled'}\n")

    try:
        response = await manager.generate(messages, role=ModelRole.GENERAL, config=config)

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

    parser = argparse.ArgumentParser(description="GPTase Chat Demo")
    parser.add_argument("--simple", action="store_true", help="Non-streaming mode")
    parser.add_argument("--thinking", action="store_true", help="Enable thinking mode")
    parser.add_argument("--no-thinking", action="store_true", help="Disable thinking mode")
    args = parser.parse_args()

    if args.simple:
        enable_thinking = args.thinking
        asyncio.run(run_simple_demo(enable_thinking=enable_thinking))
    else:
        # Streaming mode: thinking enabled by default
        enable_thinking = not args.no_thinking
        asyncio.run(run_streaming_demo(enable_thinking=enable_thinking))
