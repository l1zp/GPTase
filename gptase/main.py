"""CLI entry point for GPTase."""

import argparse
import asyncio
import logging
import sys

from .agents.orchestrator import AgentOrchestrator
from .core.config import FrameworkConfig
from .core.logging import setup_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gptase",
        description="GPTase - Multi-Agent Framework for AI Task Automation",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a task")
    run_parser.add_argument(
        "-d",
        "--description",
        type=str,
        required=True,
        help="Task description",
    )
    run_parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help="Agent ID to use (optional)",
    )
    run_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    # List agents command
    list_parser = subparsers.add_parser("list", help="List available agents")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")

    return parser.parse_args()


async def run_task(args: argparse.Namespace) -> int:
    """Run a task using the orchestrator."""
    setup_logging("DEBUG" if args.debug else "INFO")

    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    task = {"description": args.description}
    if args.agent:
        task["agent_id"] = args.agent

    result = await orchestrator.execute_task(task)

    if result.get("status") == "failed":
        logger.error("[ERROR] Task failed: %s", result.get("error"))
        return 1

    logger.info("[OK] Task completed successfully")
    print(result.get("data", ""))
    return 0


async def list_agents() -> int:
    """List available agents."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    agents = await orchestrator.list_available_agents()

    print("Available Agents:")
    print("-" * 50)
    for agent in agents:
        print(f"  {agent['agent_id']}")
        print(f"    Type: {agent['type']}")
        print(f"    Capabilities: {', '.join(agent['capabilities'])}")
        print()

    return 0


async def show_status() -> int:
    """Show system status."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    status = await orchestrator.get_system_status()

    print("System Status:")
    print("-" * 50)
    print(f"  Timestamp: {status['timestamp']}")
    print(f"  Active Agents: {len(status['agents'])}")
    print(f"  Memory Usage: {status['memory']}")

    return 0


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.command is None:
        print("GPTase - Multi-Agent Framework")
        print("Use 'gptase --help' for usage information.")
        return 0

    if args.command == "run":
        return asyncio.run(run_task(args))
    elif args.command == "list":
        return asyncio.run(list_agents())
    elif args.command == "status":
        return asyncio.run(show_status())

    return 0


if __name__ == "__main__":
    sys.exit(main())
