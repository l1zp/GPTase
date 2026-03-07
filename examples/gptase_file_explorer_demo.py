#!/usr/bin/env python3
"""GPTase file explorer demo using markdown-defined agent.

This example demonstrates how to use GPTase's markdown agent definition
format, equivalent to the claude_agent_sdk_demo.py example.

Usage:
    python examples/gptase_file_explorer_demo.py
    python examples/gptase_file_explorer_demo.py --prompt "List all Python files"
"""

import argparse
import asyncio
import logging
from pathlib import Path

from gptase.agents.base import Agent
from gptase.utils import setup_logging

logger = logging.getLogger(__name__)


async def run_agent(prompt: str, agent_md_path: Path) -> dict:
    """Run agent defined in markdown file.

    Args:
        prompt: The user prompt to send to the agent.
        agent_md_path: Path to the agent markdown definition file.

    Returns:
        The result from the agent.
    """
    agent = Agent.from_markdown(agent_md_path)

    logger.info("Agent: %s", agent.agent_id)
    logger.info("Tools: %s", agent.tools)
    logger.info("Model: %s", agent.model_name)

    result = await agent.run(prompt)
    return result


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="GPTase file explorer demo using markdown-defined agent")
    parser.add_argument(
        "--prompt",
        default="What files are in this directory?",
        help="Prompt to send to the agent",
    )
    parser.add_argument(
        "--agent-md",
        default=Path(__file__).parent / "file-explorer.md",
        help="Path to agent markdown definition file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(debug=args.debug)

    agent_md_path = Path(args.agent_md)
    if not agent_md_path.exists():
        logger.error("Agent markdown file not found: %s", agent_md_path)
        return

    logger.info("Running agent from: %s", agent_md_path)

    result = await run_agent(prompt=args.prompt, agent_md_path=agent_md_path)

    if result.get("status") == "success":
        print("\n[RESULT]")
        data = result.get("data", {})
        if isinstance(data, dict):
            print(data.get("content", "No content"))
        else:
            print(data)
    else:
        logger.error("Agent failed: %s", result.get("error"))

    logger.info("Agent completed")


if __name__ == "__main__":
    asyncio.run(main())
