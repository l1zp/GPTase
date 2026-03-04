"""CLI entry point for GPTase."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
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

    # SOP command
    sop_parser = subparsers.add_parser("sop", help="Execute SOP workflows")
    sop_parser.add_argument(
        "--list",
        action="store_true",
        help="List available SOPs",
    )
    sop_parser.add_argument(
        "-p",
        "--plan",
        type=str,
        default=None,
        help="SOP plan ID to execute",
    )
    sop_parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input file path (markdown or text)",
    )
    sop_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output directory path",
    )
    sop_parser.add_argument(
        "--input-text",
        type=str,
        default=None,
        help="Direct input text (instead of file)",
    )
    sop_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    # Checkpoint and resume options
    sop_parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume execution from session ID",
    )
    sop_parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all SOP execution sessions",
    )
    sop_parser.add_argument(
        "--session-status",
        type=str,
        default=None,
        help="Show status of a specific session",
    )
    sop_parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable automatic checkpoint saving",
    )

    return parser.parse_args()


async def run_task(args: argparse.Namespace) -> int:
    """Run a task using the orchestrator.

    Args:
        args: Parsed command-line arguments with description and optional agent_id.
    """
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


async def run_sop(args: argparse.Namespace) -> int:
    """Execute an SOP workflow.

    Args:
        args: Parsed command-line arguments with plan, input, output, and debug options.
    """
    setup_logging("DEBUG" if args.debug else "INFO")

    from gptase.sop import SOPOrchestratorAgent
    from gptase.sop import SOPRegistry

    registry = SOPRegistry.get_instance()

    # List SOPs
    if args.list:
        from gptase.utils import format_sop_list

        sops = registry.list_sops()
        print(format_sop_list(sops))
        return 0

    # List sessions
    if args.list_sessions:
        orchestrator = SOPOrchestratorAgent()
        sessions = await orchestrator.list_sessions()
        await orchestrator.close()

        if not sessions:
            print("No sessions found.")
            return 0

        print("SOP Execution Sessions:")
        print("-" * 80)
        print(f"{'Session ID':<35} {'Plan ID':<25} {'Status':<12} {'Progress'}")
        print("-" * 80)
        for s in sessions:
            print(f"{s['session_id']:<35} {s['plan_id']:<25} {s['status']:<12} "
                  f"{s['completed_steps']}/{s['total_steps']} ({s['progress']}%)")
        return 0

    # Show session status
    if args.session_status:
        orchestrator = SOPOrchestratorAgent()
        status = await orchestrator.get_session_status(args.session_status)
        await orchestrator.close()

        if not status:
            logger.error("[ERROR] Session not found: %s", args.session_status)
            return 1

        print(f"Session Status: {args.session_status}")
        print("-" * 50)
        print(f"  Plan ID: {status['plan_id']}")
        print(f"  Status: {status['status']}")
        print(
            f"  Progress: {status['completed_steps']}/{status['total_steps']} ({status['progress']}%)"
        )
        print(f"  Created: {status['created_at']}")
        print(f"  Updated: {status['updated_at']}")
        if status.get("current_step"):
            print(f"  Current Step: {status['current_step']}")
        if status.get("step_results"):
            print("  Step Results:")
            for step_id, sr in status["step_results"].items():
                print(f"    - {step_id}: {sr['status']}")
        return 0

    # Resume from session
    if args.resume:
        orchestrator = SOPOrchestratorAgent()

        logger.info("[INFO] Resuming session: %s", args.resume)

        # Prepare input_data override if provided
        input_data = None
        if args.input_text:
            input_data = {"text": args.input_text}

        result = await orchestrator.resume_sop(
            session_id=args.resume,
            input_data=input_data,
        )

        # Cleanup
        await orchestrator.close()

        if result.get("status") == "error":
            logger.error("[ERROR] SOP execution failed: %s", result.get("error"))
            logger.info("[INFO] Session ID for resume: %s", args.resume)
            return 1

        # Output results
        output_dir = Path(args.output) if args.output else Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{result.get('plan_id', 'resumed')}_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        logger.info("[OK] SOP execution completed")
        logger.info("[INFO] Results saved to: %s", output_file)

        step_results = result.get("step_results", {})
        print(f"\nExecution Summary:")
        print("-" * 50)
        print(f"  Session: {args.resume}")
        print(f"  Steps Completed: {len(step_results)}")
        print(f"  Output: {output_file}")

        return 0

    # Execute SOP
    if not args.plan:
        logger.error("[ERROR] SOP plan ID is required. Use -p/--plan")
        return 1

    # Prepare input data
    input_data = {}
    document_path = None

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error("[ERROR] Input file not found: %s", args.input)
            return 1
        input_data["text"] = input_path.read_text(encoding="utf-8")
        input_data["document_path"] = str(input_path.parent)
        document_path = str(input_path.parent)

    if args.input_text:
        input_data["text"] = args.input_text

    if not input_data:
        logger.error("[ERROR] No input provided. Use -i/--input or --input-text")
        return 1

    # Create orchestrator and execute
    orchestrator = SOPOrchestratorAgent()

    auto_checkpoint = not args.no_checkpoint

    logger.info("[INFO] Executing SOP: %s", args.plan)
    result = await orchestrator.execute_sop(
        plan_id=args.plan,
        input_data=input_data,
        document_path=document_path,
        auto_checkpoint=auto_checkpoint,
    )

    # Cleanup: close database connections before event loop shuts down
    await orchestrator.close()

    if result.get("status") == "error":
        logger.error("[ERROR] SOP execution failed: %s", result.get("error"))
        logger.info("[INFO] Session ID for resume: %s", result.get("session_id"))
        return 1

    # Output results
    output_dir = Path(args.output) if args.output else Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save results
    output_file = output_dir / f"{args.plan}_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    logger.info("[OK] SOP execution completed")
    logger.info("[INFO] Results saved to: %s", output_file)

    # Print summary
    step_results = result.get("step_results", {})
    print(f"\nExecution Summary:")
    print("-" * 50)
    print(f"  SOP: {args.plan}")
    print(f"  Session: {result.get('session_id', 'N/A')}")
    print(f"  Steps Completed: {len(step_results)}")
    print(f"  Output: {output_file}")

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
    elif args.command == "sop":
        return asyncio.run(run_sop(args))

    return 0


if __name__ == "__main__":
    sys.exit(main())
