"""CLI entry point for GPTase."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

from .core.orchestrator import AgentOrchestrator
from .utils.config import FrameworkConfig

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gptase",
        description="GPTase - Multi-Agent Framework for AI Task Automation",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Agent command (run a single agent)
    agent_parser = subparsers.add_parser("agent", help="Run a single agent")
    agent_parser.add_argument(
        "-n",
        "--name",
        type=str,
        required=True,
        help="Agent name to run",
    )
    agent_parser.add_argument(
        "-d",
        "--description",
        type=str,
        default=None,
        help="Task description (optional, will prompt if not provided)",
    )
    agent_parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input file path (markdown, text, or image)",
    )
    agent_parser.add_argument(
        "--images",
        type=str,
        nargs="+",
        default=None,
        help="Image paths for multimodal agents",
    )
    agent_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    # List agents command
    list_parser = subparsers.add_parser("list", help="List available agents")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")

    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Execute predefined plans")
    plan_parser.add_argument(
        "--list",
        action="store_true",
        help="List available Plans",
    )
    plan_parser.add_argument(
        "-p",
        "--plan",
        type=str,
        default=None,
        help="Plan ID to execute",
    )
    plan_parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input file path (markdown or text)",
    )
    plan_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output directory path",
    )
    plan_parser.add_argument(
        "--input-text",
        type=str,
        default=None,
        help="Direct input text (instead of file)",
    )
    plan_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    # Checkpoint and resume options
    plan_parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume execution from session ID",
    )
    plan_parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all Plan execution sessions",
    )
    plan_parser.add_argument(
        "--session-status",
        type=str,
        default=None,
        help="Show status of a specific session",
    )
    plan_parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable automatic checkpoint saving",
    )
    plan_parser.add_argument(
        "--review",
        action="store_true",
        help="Create a draft plan and stop before execution",
    )
    plan_parser.add_argument(
        "--auto-replan",
        action="store_true",
        help="Allow the harness to generate follow-up plans automatically if the goal is not met",
    )
    plan_parser.add_argument(
        "--feedback",
        type=str,
        default=None,
        help="Feedback to revise or continue an existing harness session",
    )

    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluate agent output quality")
    eval_parser.add_argument(
        "-a",
        "--agent",
        type=str,
        required=True,
        help="Agent name to evaluate",
    )
    eval_parser.add_argument(
        "--live",
        action="store_true",
        help="Run agent live against the LLM API (costs tokens)",
    )
    eval_parser.add_argument(
        "--save-output",
        action="store_true",
        help="Save live output to agent's evals directory",
    )
    eval_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save JSON report to this file path",
    )
    eval_parser.add_argument(
        "--config",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "LLM config JSON file for live runs (overrides default config). "
            "Example: config/llm_config.qwen_vl.example.json"
        ),
    )

    # Web command
    web_parser = subparsers.add_parser("web", help="Start the Web UI")
    web_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )
    web_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to run the server on (default: 127.0.0.1)",
    )

    return parser.parse_args()


async def run_agent(args: argparse.Namespace) -> int:
    """Run a single agent.

    Args:
        args: Parsed command-line arguments with name and description.
    """
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from gptase.agents.base import Agent
    from gptase.models.model import Model

    # Get task description
    description = args.description
    if not description and args.input:
        input_path = Path(args.input)
        if input_path.exists():
            description = input_path.read_text(encoding="utf-8")
    if not description:
        logger.error(
            "[ERROR] Task description required. Use -d/--description or -i/--input")
        return 1

    # Initialize model
    model = Model()

    # Create agent from markdown definition
    agent_name = args.name
    try:
        agent = Agent.from_markdown(agent_name, model_manager=model)
    except FileNotFoundError:
        logger.error("[ERROR] Agent not found: %s", agent_name)
        logger.info("[INFO] Available agents: %s", ", ".join(_list_agent_names()))
        return 1

    # Prepare task
    image_paths = args.images
    if args.input and Path(
            args.input).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        if image_paths is None:
            image_paths = [args.input]

    logger.info("[INFO] Running agent: %s", agent_name)

    # Run agent
    result = await agent.run(
        content=description,
        image_paths=image_paths,
    )

    if result.get("status") == "error":
        logger.error("[ERROR] Agent execution failed: %s", result.get("error"))
        return 1

    logger.info("[OK] Agent completed successfully")

    # Print output
    output = result.get("data", {}).get("content", "")
    print(output)
    return 0


def _list_agent_names() -> list:
    """List available agent names (flat and directory layouts)."""
    from gptase.agents.base import list_agent_md_files

    agents_dir = Path(__file__).parent.parent / ".claude" / "agents"
    if not agents_dir.exists():
        return []
    return [f.stem for f in list_agent_md_files(agents_dir)]


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


def _parse_content_json(content: str) -> dict:
    """Parse JSON from content string, handling markdown code blocks."""
    from gptase.utils.json_utils import parse_json_content

    return parse_json_content(content) or {}


def _organize_plan_output(result: dict, output_dir: Path, document_name: str) -> None:
    """Organize Plan output into structured directories.

    Creates analysis/, extraction/, vision/, summary/ directories with
    corresponding JSON and CSV files.
    """
    import csv
    from datetime import datetime

    task_results = result.get("task_results", {})
    if not task_results:
        return

    # Create output directories
    analysis_dir = output_dir / "analysis"
    extraction_dir = output_dir / "extraction"
    vision_dir = output_dir / "vision"
    summary_dir = output_dir / "summary"

    for d in [analysis_dir, extraction_dir, vision_dir, summary_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Process each step
    for task_id, task_data in task_results.items():
        if not isinstance(task_data, dict):
            continue

        # Extract content
        content = task_data.get("content", "")
        parsed = _parse_content_json(content)

        if not parsed:
            # Try to use task_data directly if it looks like structured data
            if any(k in task_data
                   for k in ["reactions", "images", "sections", "tables"]):
                parsed = task_data
            else:
                continue

        # Route to appropriate directory based on task_id
        if task_id == "1":
            # Document structure analysis
            with open(analysis_dir / "structure_analysis.json", "w",
                      encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            # Create CSV for images
            images = parsed.get("images", [])
            if images:
                with open(analysis_dir / "structure_analysis.csv",
                          "w",
                          encoding="utf-8",
                          newline="") as f:
                    fieldnames = [
                        "image_number", "image_path", "figure_id",
                        "is_reaction_related", "reasoning"
                    ]
                    writer = csv.DictWriter(f,
                                            fieldnames=fieldnames,
                                            extrasaction="ignore")
                    writer.writeheader()
                    for img in images:
                        writer.writerow(img)

        elif task_id == "2a":
            # Text-based extraction
            with open(extraction_dir / "extraction.json", "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            # Create CSV for reactions
            reactions = parsed.get("reactions", [])
            if reactions:
                # Flatten nested structures
                flat_rows = []
                for r in reactions:
                    flat = {
                        "enzyme_name":
                        r.get("enzyme_name", ""),
                        "substrates":
                        ",".join(r.get("substrates", [])) if isinstance(
                            r.get("substrates"), list) else r.get("substrates", ""),
                        "Tm":
                        r.get("Tm", ""),
                        "Tm_unit":
                        r.get("Tm_unit", ""),
                        "mutations":
                        ",".join(r.get("mutations", [])) if isinstance(
                            r.get("mutations"), list) else r.get("mutations", ""),
                        "pdb_ids":
                        ",".join(r.get("pdb_ids", [])) if isinstance(
                            r.get("pdb_ids"), list) else r.get("pdb_ids", ""),
                    }
                    # Extract kinetics
                    kinetics = r.get("kinetics", {})
                    if kinetics:
                        flat.update({
                            "Km": kinetics.get("Km", ""),
                            "Km_unit": kinetics.get("Km_unit", ""),
                            "kcat": kinetics.get("kcat", ""),
                            "kcat_unit": kinetics.get("kcat_unit", ""),
                            "kcat_Km": kinetics.get("kcat_Km", ""),
                            "kcat_Km_unit": kinetics.get("kcat_Km_unit", ""),
                        })
                    flat_rows.append(flat)

                # Find all unique keys
                all_keys = []
                for row in flat_rows:
                    for k in row.keys():
                        if k not in all_keys:
                            all_keys.append(k)

                with open(extraction_dir / "combined_data.csv",
                          "w",
                          encoding="utf-8",
                          newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=all_keys)
                    writer.writeheader()
                    for row in flat_rows:
                        writer.writerow(row)

        elif task_id == "2b":
            # Vision analysis
            with open(vision_dir / "vision_analysis_results.json",
                      "w",
                      encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            # Extract tables
            extracted_tables = parsed.get("extracted_tables", [])
            for tbl in extracted_tables:
                csv_data = tbl.get("csv_data", "")
                img_num = tbl.get("image_number", 1)
                if csv_data:
                    with open(vision_dir / f"extracted_tables.csv",
                              "w",
                              encoding="utf-8") as f:
                        f.write(csv_data)

        elif task_id == "3":
            # Summary
            with open(summary_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            # Create summary.md
            summary_md = _generate_summary_md(parsed, document_name)
            with open(summary_dir / "summary.md", "w", encoding="utf-8") as f:
                f.write(summary_md)

    # Generate README.md
    readme_content = _generate_readme(result, document_name, output_dir)
    with open(output_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)


def _generate_summary_md(parsed: dict, document_name: str) -> str:
    """Generate summary.md content from parsed data."""
    from datetime import datetime

    lines = [
        f"# Enzyme Kinetics Extraction Summary: {document_name}",
        "",
        "## Overview",
        "",
    ]

    # Add statistics if available
    stats = parsed.get("statistics", {})
    if stats:
        lines.append("## Statistics")
        lines.append("")
        for key, value in stats.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # Add top performers if available
    top_performers = parsed.get("top_performers", {})
    if top_performers:
        lines.append("## Top Performers")
        lines.append("")
        if isinstance(top_performers, list):
            for p in top_performers[:10]:
                if isinstance(p, dict):
                    lines.append(f"- {p.get('name', p.get('enzyme_name', 'Unknown'))}: "
                                 f"{p.get('value', 'N/A')} {p.get('unit', '')}")
            lines.append("")
        elif isinstance(top_performers, dict):
            for category, performers in top_performers.items():
                lines.append(f"### {category}")
                lines.append("")
                for p in performers[:5]:
                    lines.append(
                        f"- {p.get('name', 'Unknown')}: {p.get('value', 'N/A')} {p.get('unit', '')}"
                    )
                lines.append("")

    # Add data quality
    quality = parsed.get("data_quality", {})
    if quality:
        lines.append("## Data Quality")
        lines.append("")
        for key, value in quality.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    return "\n".join(lines)


def _generate_readme(result: dict, document_name: str, output_dir: Path) -> str:
    """Generate README.md for the output directory."""
    from datetime import datetime

    lines = [
        f"# {document_name} - Enzyme Extraction Results",
        "",
        f"**Generated**: {datetime.now().isoformat()}",
        "",
        "## Directory Structure",
        "",
        "```",
        f"{document_name}/",
        "├── analysis/       # Document structure analysis",
        "├── extraction/     # Extracted enzyme data",
        "├── vision/         # Vision analysis results",
        "├── summary/        # Summary report",
        "└── README.md       # This file",
        "```",
        "",
        "## Files",
        "",
        "### analysis/",
        "- `structure_analysis.json` - Complete document structure",
        "- `structure_analysis.csv` - Summary of figures and tables",
        "",
        "### extraction/",
        "- `extraction.json` - Primary extraction data",
        "- `combined_data.csv` - Flattened enzyme data for analysis",
        "",
        "### vision/",
        "- `vision_analysis_results.json` - Vision model output",
        "- `extracted_tables.csv` - Tables extracted from figures",
        "",
        "### summary/",
        "- `summary.json` - Statistical summary",
        "- `summary.md` - Human-readable summary",
        "",
    ]

    # Add step results summary
    task_results = result.get("task_results", {})
    if task_results:
        lines.append("## Execution Summary")
        lines.append("")
        lines.append(f"- Steps completed: {len(task_results)}")
        for task_id, task_data in task_results.items():
            lines.append(f"  - Step {task_id}: completed")
        lines.append("")

    return "\n".join(lines)


async def run_plan(args: argparse.Namespace) -> int:
    """Execute an Plan workflow.

    Args:
        args: Parsed command-line arguments with plan, input, output, and debug options.
    """
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from gptase.agents.plan_loader import PlanRegistry

    registry = PlanRegistry.get_instance()
    orchestrator = AgentOrchestrator(FrameworkConfig())

    # List Plans
    if args.list:
        from gptase.utils import format_plan_list

        plans = registry.list_plans()
        print(format_plan_list(plans))
        return 0

    # List sessions
    if args.list_sessions:
        sessions = await orchestrator.list_sessions()

        if not sessions:
            print("No sessions found.")
            return 0

        print("Harness Sessions:")
        print("-" * 80)
        print(f"{'Session ID':<35} {'Status':<20} {'Current Plan'}")
        print("-" * 80)
        for s in sessions:
            print(f"{s['session_id']:<35} {s['status']:<20} "
                  f"{s.get('current_plan_id', 'N/A')}")
        return 0

    # Show session status
    if args.session_status:
        status = await orchestrator.get_session_status(args.session_status)

        if not status:
            logger.error("[ERROR] Session not found: %s", args.session_status)
            return 1

        print(f"Session Status: {args.session_status}")
        print("-" * 50)
        print(f"  Goal: {status.get('goal', '')}")
        print(f"  Status: {status['status']}")
        if status.get("current_plan"):
            print(f"  Current Plan: {status['current_plan'].get('plan_id', 'N/A')}")
        if status.get("progress"):
            print(f"  Progress: {status['progress']}")
        if status.get("goal_evaluation"):
            print(f"  Goal Evaluation: {status['goal_evaluation']}")
        if status.get("task_results"):
            print("  Task Results:")
            for task_id in status["task_results"].keys():
                print(f"    - {task_id}")
        return 0

    # Resume from session
    if args.resume:
        logger.info("[INFO] Resuming session: %s", args.resume)
        payload = {"session_id": args.resume}
        if args.feedback:
            payload["feedback"] = args.feedback
        if not args.review:
            payload["approve_plan"] = True
        if args.auto_replan:
            payload["auto_replan"] = True
        result = await orchestrator.execute_task(payload)
        return _write_harness_result(result, args.output, args.resume)

    # Execute Plan
    if not args.plan:
        logger.error("[ERROR] Plan ID is required. Use -p/--plan")
        return 1

    # Prepare input data
    input_data = {}
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error("[ERROR] Input file not found: %s", args.input)
            return 1
        input_data["text"] = input_path.read_text(encoding="utf-8")
        input_data["document_path"] = str(input_path.resolve())

    if args.input_text:
        input_data["text"] = args.input_text

    if not input_data:
        logger.error("[ERROR] No input provided. Use -i/--input or --input-text")
        return 1

    # Initialize workspace directory using ProjectPaths
    from gptase.utils.paths import ProjectPaths
    paths = ProjectPaths()

    doc_name = Path(args.input).stem if args.input else "interactive"
    workspace_dir = paths.get_plan_output_dir(document_name=doc_name, plan_id=args.plan)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[INFO] Executing draft plan via harness: %s", args.plan)
    result = await orchestrator.execute_task({
        "description": input_data.get("text", f"Execute draft plan {args.plan}"),
        "goal": input_data.get("text", f"Execute draft plan {args.plan}"),
        "plan_id": args.plan,
        "auto_execute": not args.review,
        "auto_replan": args.auto_replan,
        "document_path": input_data.get("document_path"),
        "workspace_dir": str(workspace_dir),
    })
    return _write_harness_result(result, args.output or str(workspace_dir), args.plan)


def _write_harness_result(result: dict, output_dir_arg: str | None,
                          output_name: str) -> int:
    if result.get("status") == "failed":
        logger.error("[ERROR] Harness execution failed: %s", result.get("error"))
        return 1

    output_dir = Path(output_dir_arg) if output_dir_arg else Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{output_name}_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    logger.info("[INFO] Results saved to: %s", output_file)
    print("\nExecution Summary:")
    print("-" * 50)
    print(f"  Session: {result.get('session_id', 'N/A')}")
    print(f"  Status: {result.get('status', 'unknown')}")
    if result.get("current_plan"):
        print(f"  Current Plan: {result['current_plan'].get('plan_id', 'N/A')}")
    print(f"  Output: {output_file}")
    return 0


async def run_eval(args: argparse.Namespace) -> int:
    """Run agent output quality evaluation.

    Args:
        args: Parsed command-line arguments.
    """
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from gptase.evals.report import print_eval_report
    from gptase.evals.report import save_eval_report
    from gptase.evals.runner import EvalRunner

    config_path = args.config

    try:
        runner = EvalRunner(agent_name=args.agent, config_path=config_path)
    except FileNotFoundError as exc:
        logger.error("[ERROR] %s", exc)
        return 1

    result = await runner.eval_agent(live=args.live, save_output=args.save_output)
    results = [result]

    print_eval_report(results)

    if args.save:
        save_eval_report(results, args.save)
        print(f"[INFO] Report saved to: {args.save}")

    all_passed = all(r.schema_valid and r.score == 1.0 for r in results)
    return 0 if all_passed else 1


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.command is None:
        print("GPTase - Multi-Agent Framework")
        print("Use 'gptase --help' for usage information.")
        return 0

    if args.command == "agent":
        return asyncio.run(run_agent(args))
    elif args.command == "list":
        return asyncio.run(list_agents())
    elif args.command == "status":
        return asyncio.run(show_status())
    elif args.command == "plan":
        return asyncio.run(run_plan(args))
    elif args.command == "eval":
        return asyncio.run(run_eval(args))
    elif args.command == "web":
        import threading
        import webbrowser

        import uvicorn

        from gptase.web.server import app

        url = f"http://{args.host}:{args.port}"
        print(f"Starting GPTase Web UI on {url}")

        # Open browser in a separate thread after a short delay
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
