#!/usr/bin/env python3
"""Streaming chat demo with thinking mode support.

This script demonstrates real-time streaming of LLM responses with
visual separation between reasoning (thinking) and final answer content.

Usage:
    python examples/chat_demo.py              # Streaming with thinking mode
    python examples/chat_demo.py --no-thinking # Streaming without thinking
    python examples/chat_demo.py --simple      # Simple mode (non-streaming)
"""

import asyncio
from pathlib import Path

import sys

# Ensure project root is on sys.path to import the local GPTase package
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models.types import ModelRole

# Common prompt for all modes - easier to compare
COMMON_MESSAGES = [
    {
        "role": "system",
        "content": "You are a helpful assistant who thinks through problems step by step. Show your reasoning process when solving complex questions."
    },
    {
        "role": "user",
        "content": "Explain why the sky appears blue during the day but red/orange during sunset. Think step by step and show your reasoning."
    },
]


# ANSI color codes
class Colors:
    YELLOW = "\033[93m"
    WHITE = "\033[97m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    RESET = "\033[0m"


def print_thinking(text: str) -> None:
    """Print thinking/reasoning content in yellow."""
    print(f"{Colors.YELLOW}{text}{Colors.RESET}", end="", flush=True)


def print_answer(text: str) -> None:
    """Print answer content in white."""
    print(f"{text}", end="", flush=True)


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{'='*60}\n")


def get_mode_name(enable_thinking: bool) -> str:
    """Return the mode name based on thinking setting."""
    return "Thinking Mode" if enable_thinking else "Standard Mode"


def print_demo_header(title: str, enable_thinking: bool, is_streaming: bool) -> None:
    """Print the demo header with configuration details."""
    mode_name = get_mode_name(enable_thinking)
    print_header(f"{title} ({mode_name})")

    print("\n📝 Question:")
    print(COMMON_MESSAGES[-1]["content"])
    print(f"\n⚙️  Mode: {mode_name}")
    print(f"⚙️  Thinking enabled: {'Yes ✅' if enable_thinking else 'No ❌'}")
    print(f"⚙️  Streaming: {'Yes' if is_streaming else 'No'}")


def print_usage_info(usage: dict) -> None:
    """Print token usage information."""
    total = usage.get("total_tokens", "N/A")
    prompt = usage.get("prompt_tokens", "N/A")
    completion = usage.get("completion_tokens", "N/A")
    print(f"\n\n{Colors.GRAY}📊 Tokens: {total} "
          f"(prompt: {prompt}, completion: {completion}){Colors.RESET}")


def create_config(manager, enable_thinking: bool):
    """Create a config with thinking mode setting applied."""
    existing_config = manager.get_role_config(ModelRole.GENERAL)
    return existing_config.model_copy(update={"enable_thinking": enable_thinking})


async def run_streaming_demo(enable_thinking: bool = True):
    """Run streaming chat demo with optional thinking mode.

    Args:
        enable_thinking: Whether to enable thinking mode (default: True)
    """
    from src.utils import default_manager

    try:
        manager = default_manager()
    except ValueError as e:
        print(f"Error: {e}")
        return

    config = create_config(manager, enable_thinking)
    mode_name = get_mode_name(enable_thinking)

    print_demo_header("🤖 GPTase Streaming Chat Demo", enable_thinking, is_streaming=True)
    print_header(f"💭 Streaming Response ({mode_name})")

    thinking_buffer = []
    answer_buffer = []
    is_thinking = False
    chunk_count = 0

    try:
        print(f"{Colors.GRAY}<!-- Waiting for response... -->{Colors.RESET}\r", end="")

        async for chunk in manager.generate_stream(COMMON_MESSAGES, role=ModelRole.GENERAL, config=config):
            chunk_count += 1

            if chunk_count == 1:
                print(" " * 60 + "\r", end="")

            if chunk.is_thinking and chunk.reasoning_content:
                if not is_thinking:
                    print(f"{Colors.YELLOW}🧠 Thinking:{Colors.RESET}")
                    is_thinking = True
                print_thinking(chunk.reasoning_content)
                thinking_buffer.append(chunk.reasoning_content)

            elif chunk.content and not chunk.is_thinking:
                if is_thinking and not answer_buffer:
                    print(f"\n\n{Colors.WHITE}💡 Answer:{Colors.RESET}")
                    is_thinking = False
                print_answer(chunk.content)
                answer_buffer.append(chunk.content)

            if chunk.is_complete:
                if "error" in chunk.metadata:
                    print(f"\n\n{Colors.RED}❌ Error: {chunk.metadata['error']}{Colors.RESET}")
                elif "usage" in chunk.metadata:
                    print_usage_info(chunk.metadata["usage"])

        print("\n")
        print_header("✨ Demo Complete")
        print(f"Total chunks received: {chunk_count}")
        print(f"Thinking length: {len(''.join(thinking_buffer))} chars")
        print(f"Answer length: {len(''.join(answer_buffer))} chars")

        if not enable_thinking:
            print("\n💡 Tip: Run with thinking mode enabled to see the reasoning process:")
            print("   python examples/chat_demo.py")
        elif len(''.join(thinking_buffer)) == 0:
            print("\n💡 Note: Model didn't return reasoning_content.")
            print("   This model may not support thinking mode.")
        else:
            print("\n✅ Thinking mode active! Model showed its reasoning process.")

    except NotImplementedError as e:
        print(f"\n{Colors.RED}❌ Streaming not supported: {e}{Colors.RESET}")
        print("\nTip: Make sure your LLM provider supports streaming (e.g., OpenAI-compatible APIs)")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}")


async def run_simple_demo(enable_thinking: bool = False):
    """Run a simple one-shot chat without streaming.

    Args:
        enable_thinking: Whether to enable thinking mode (default: False)
    """
    from src.utils import default_manager

    try:
        manager = default_manager()
    except ValueError as e:
        print(f"Error: {e}")
        return

    config = create_config(manager, enable_thinking)

    print_demo_header("🤖 GPTase Simple Chat Demo", enable_thinking, is_streaming=False)
    print("\n💡 Response:")

    response = await manager.generate(COMMON_MESSAGES, role=ModelRole.GENERAL, config=config)

    if response.reasoning_content:
        print(f"\n{Colors.YELLOW}🧠 Thinking:{Colors.RESET}")
        print(response.reasoning_content)
        print(f"\n{Colors.WHITE}💡 Answer:{Colors.RESET}")

    print(response.content)

    if response.usage:
        total = response.usage.get("total_tokens", "N/A")
        print(f"\n{Colors.GRAY}📊 Tokens: {total}{Colors.RESET}")

    print("\n💡 Tip: Run streaming mode to see real-time output:")
    print("   python examples/chat_demo.py")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="GPTase Chat Demo - Compare thinking vs standard mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python examples/chat_demo.py               # Streaming with thinking mode (default)
  python examples/chat_demo.py --no-thinking # Streaming without thinking
  python examples/chat_demo.py --simple      # Simple mode (non-streaming)
  python examples/chat_demo.py --simple --thinking  # Simple with thinking mode

The same prompt is used across all modes for easy comparison.
        """
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Run simple demo without streaming"
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="Disable thinking mode (only meaningful with streaming)"
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Enable thinking mode in simple mode"
    )
    args = parser.parse_args()

    if args.simple:
        # Simple mode: default is no thinking, use --thinking to enable
        enable_thinking = args.thinking
        asyncio.run(run_simple_demo(enable_thinking=enable_thinking))
    else:
        # Streaming mode: default is thinking enabled, use --no-thinking to disable
        enable_thinking = not args.no_thinking
        asyncio.run(run_streaming_demo(enable_thinking=enable_thinking))
