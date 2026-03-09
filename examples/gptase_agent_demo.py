#!/usr/bin/env python3
"""GPTase Agent demo using the unified Agent interface.

This example demonstrates how to use GPTase's own Agent class for
simple agent interactions with skills support.

Usage:
    python examples/gptase_agent_demo.py
    python examples/gptase_agent_demo.py --prompt "List all Python files"
"""

import argparse
import asyncio
import logging

from gptase.agents import Agent
from gptase.utils import default_manager
from gptase.utils import setup_logging

logger = logging.getLogger(__name__)


async def run_agent(prompt: str) -> dict:
    """Run GPTase Agent with specified prompt.

    Args:
        prompt: The user prompt to send to the agent.

    Returns:
        The result dictionary from the agent.
    """
    # Get model manager with default config
    model = default_manager(enable_tracking=False)
    await model.initialize_tracking()

    agent = Agent(
        system_prompt="You are a helpful assistant.",
        model_config=model.default_config,
    )

    result = await agent.run(prompt)

    if result.get("status") == "success":
        data = result.get("data", {})
        content = data.get("content", "")
        print(content)
    else:
        print(f"[ERROR] {result.get('error', 'Unknown error')}")

    await model.shutdown()
    return result


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="GPTase Agent demo with unified Agent interface")
    parser.add_argument("--prompt",
                        default="What files are in this directory?",
                        help="Prompt to send to the agent")
    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging()

    logger.info("Running GPTase agent with prompt: %s", args.prompt[:50])

    result = await run_agent(prompt=args.prompt)

    status = result.get("status", "unknown")
    logger.info("Agent completed with status: %s", status)


if __name__ == "__main__":
    asyncio.run(main())
