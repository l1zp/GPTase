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
import sys

# Add parent directory to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

from gptase.agents.loader import AgentParser
from gptase.agents.loader import MarkdownAgentFactory
from gptase.models.model import Model

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


async def run_agent(prompt: str, agent_md_path: Path) -> dict:
    """Run agent defined in markdown file.

    Args:
        prompt: The user prompt to send to the agent.
        agent_md_path: Path to the agent markdown definition file.

    Returns:
        The result from the agent.
    """
    # Parse agent definition from markdown
    parser = AgentParser(config_dir=agent_md_path.parent)
    definition = parser.parse_file(agent_md_path)

    logger.info("Loaded agent: %s", definition.name)
    logger.info("Tools: %s", definition.tools)
    logger.info("Model: %s", definition.model)

    # Initialize model manager (loads config from config/llm_config.template.json)
    model_manager = Model()

    # Create factory with custom config directory
    factory = MarkdownAgentFactory(config_dir=agent_md_path.parent)
    agent = factory.create_agent(
        definition.name,
        model_manager=model_manager,
    )

    logger.info("Agent tools: %s", agent.tools)
    logger.info("Agent model: %s", agent.model_name)

    # Run the agent
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
