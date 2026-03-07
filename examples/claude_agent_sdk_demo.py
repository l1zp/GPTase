#!/usr/bin/env python3
"""Claude Agent SDK demo with streaming and tool restrictions.

This example demonstrates how to use the Claude Agent SDK for simple
agent interactions with controlled tool access.

Usage:
    python examples/claude_agent_sdk_demo.py
    python examples/claude_agent_sdk_demo.py --prompt "List all Python files"
"""

import argparse
import asyncio
import logging

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk import query

from gptase.utils import setup_logging

logger = logging.getLogger(__name__)


async def run_agent(prompt: str, allowed_tools: list[str]) -> str:
    """Run Claude Agent with specified prompt and tool restrictions.

    Args:
        prompt: The user prompt to send to the agent.
        allowed_tools: List of tool names the agent is allowed to use.

    Returns:
        The final result from the agent.
    """
    result = None
    async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=allowed_tools),
    ):
        if hasattr(message, "result"):
            result = message.result
            print(message.result)
    return result


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Claude Agent SDK demo with streaming and tool restrictions")
    parser.add_argument("--prompt",
                        default="What files are in this directory?",
                        help="Prompt to send to the agent")
    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging()

    allowed_tools = ["Bash", "Glob"]
    logger.info("Running agent with tools: %s", allowed_tools)

    await run_agent(prompt=args.prompt, allowed_tools=allowed_tools)
    logger.info("Agent completed")


if __name__ == "__main__":
    asyncio.run(main())
