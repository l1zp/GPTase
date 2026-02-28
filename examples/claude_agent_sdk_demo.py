#!/usr/bin/env python3
"""Claude Agent SDK demo with streaming and tool restrictions.

This example demonstrates how to use the Claude Agent SDK for simple
agent interactions with controlled tool access.

Usage:
    python examples/claude_agent_sdk_demo.py
    python examples/claude_agent_sdk_demo.py --tools Bash,Glob,Read
    python examples/claude_agent_sdk_demo.py --prompt "List all Python files"
"""

import argparse
import asyncio
import logging

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk import query

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
    parser.add_argument(
        "--prompt",
        "-p",
        default="What files are in this directory?",
        help="Prompt to send to the agent",
    )
    parser.add_argument(
        "--tools",
        "-t",
        default="Bash,Glob",
        help="Comma-separated list of allowed tools",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(debug=args.debug)

    allowed_tools = [t.strip() for t in args.tools.split(",")]
    logger.info("Running agent with tools: %s", allowed_tools)

    await run_agent(prompt=args.prompt, allowed_tools=allowed_tools)
    logger.info("Agent completed")


if __name__ == "__main__":
    asyncio.run(main())
