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

    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluate agent output quality")
    eval_parser.add_argument(
        "-p",
        "--paper",
        type=str,
        default=None,
        help="Paper ID to evaluate",
    )
    eval_parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help="Single agent to evaluate (default: all agents in golden.yaml)",
    )
    eval_parser.add_argument(
        "--live",
        action="store_true",
        help="Run agents live against the LLM API (costs tokens)",
    )
    eval_parser.add_argument(
        "--list",
        action="store_true",
        help="List available eval papers",
    )
    eval_parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Custom cached output directory",
    )
    eval_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save JSON report to this file path",
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
    """List available agent names."""
    agents_dir = Path(__file__).parent.parent / ".claude" / "agents"
    if agents_dir.exists():
        return [f.stem for f in agents_dir.glob("*.md")]
    return []


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
    if not content:
        return {}

    content = content.strip()

    # Handle markdown code blocks
    if "```json" in content:
        parts = content.split("```json")
        if len(parts) > 1:
            json_part = parts[1].split("```")[0].strip()
            try:
                return json.loads(json_part)
            except (json.JSONDecodeError, ValueError):
                pass
    elif content.startswith("```"):
        parts = content.split("```")
        if len(parts) > 1:
            json_part = parts[1].strip()
            if "\n" in json_part:
                json_part = json_part.split("\n", 1)[1]
            try:
                return json.loads(json_part)
            except (json.JSONDecodeError, ValueError):
                pass

    # Try direct JSON parse
    if content.startswith("{") or content.startswith("["):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass

    return {}


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
                    lines.append(
                        f"- {p.get('name', p.get('enzyme_name', 'Unknown'))}: "
                        f"{p.get('value', 'N/A')} {p.get('unit', '')}"
                    )
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

    from gptase.agents.base import Agent
    from gptase.agents.plan_loader import PlanRegistry
    from gptase.agents.planner import PlanManager
    from gptase.models.model import Model

    registry = PlanRegistry.get_instance()

    # List Plans
    if args.list:
        from gptase.utils import format_plan_list

        plans = registry.list_plans()
        print(format_plan_list(plans))
        return 0

    # List sessions
    if args.list_sessions:
        agent = Agent(system_prompt="", agent_id="plan_orchestrator")
        orchestrator = PlanManager(agent)
        sessions = await orchestrator.list_sessions()

        if not sessions:
            print("No sessions found.")
            return 0

        print("Plan Execution Sessions:")
        print("-" * 80)
        print(f"{'Session ID':<35} {'Plan ID':<25} {'Status':<12} {'Progress'}")
        print("-" * 80)
        for s in sessions:
            print(f"{s['session_id']:<35} {s['plan_id']:<25} {s['status']:<12} "
                  f"{s['completed_steps']}/{s['total_steps']} ({s['progress']}%)")
        return 0

    # Show session status
    if args.session_status:
        agent = Agent(system_prompt="", agent_id="plan_orchestrator")
        orchestrator = PlanManager(agent)
        status = await orchestrator.get_session_status(args.session_status)

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
        if status.get("task_results"):
            print("  Step Results:")
            for task_id, sr in status["task_results"].items():
                print(f"    - {task_id}: {sr['status']}")
        return 0

    # Resume from session
    if args.resume:
        model = Model()
        agent = Agent(system_prompt="", agent_id="plan_orchestrator")
        orchestrator = PlanManager(agent, model_manager=model)

        logger.info("[INFO] Resuming session: %s", args.resume)

        # Resolve plan: use -p flag if provided, otherwise look up from checkpoint
        if args.plan:
            resume_plan = registry.get_plan(args.plan)
        else:
            session_status = await orchestrator.get_session_status(args.resume)
            if not session_status:
                logger.error("[ERROR] Session not found: %s", args.resume)
                return 1
            resume_plan = registry.get_plan(session_status["plan_id"])

        # Prepare input_data override if provided
        input_data = None
        if args.input_text:
            input_data = {"text": args.input_text}

        result = await orchestrator.execute_plan(
            plan=resume_plan,
            session_id=args.resume,
            input_data=input_data)

        # Cleanup

        if result.get("status") == "error":
            logger.error("[ERROR] Plan execution failed: %s", result.get("error"))
            logger.info("[INFO] Session ID for resume: %s", args.resume)
            return 1

        # Output results
        output_dir = Path(args.output) if args.output else Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{result.get('plan_id', 'resumed')}_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        logger.info("[OK] Plan execution completed")
        logger.info("[INFO] Results saved to: %s", output_file)

        task_results = result.get("task_results", {})
        print(f"\nExecution Summary:")
        print("-" * 50)
        print(f"  Session: {args.resume}")
        print(f"  Steps Completed: {len(task_results)}")
        print(f"  Output: {output_file}")

        return 0

    # Execute Plan
    if not args.plan:
        logger.error("[ERROR] Plan ID is required. Use -p/--plan")
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
    model = Model()
    agent = Agent(system_prompt="", agent_id="plan_orchestrator")
    orchestrator = PlanManager(agent, model_manager=model)

    auto_checkpoint = not args.no_checkpoint

    # Initialize workspace directory using ProjectPaths
    from gptase.utils.paths import ProjectPaths
    paths = ProjectPaths()

    doc_name = Path(args.input).stem if args.input else "interactive"
    workspace_dir = paths.get_plan_output_dir(document_name=doc_name, plan_id=args.plan)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[INFO] Executing Plan: %s", args.plan)
    result = await orchestrator.execute_plan(
        plan=registry.get_plan(args.plan),
        input_data=input_data,
        document_path=document_path,
        auto_checkpoint=auto_checkpoint,
        workspace_dir=str(workspace_dir),
    )

    # Cleanup: close database connections before event loop shuts down

    if result.get("status") == "error":
        logger.error("[ERROR] Plan execution failed: %s", result.get("error"))
        logger.info("[INFO] Session ID for resume: %s", result.get("session_id"))
        return 1

    # Output results
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{args.plan}_result.json"
    else:
        output_file = workspace_dir / f"{args.plan}_result.json"

    # Save results
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    # Organize output into structured directories
    final_output_dir = output_file.parent
    _organize_plan_output(result, final_output_dir, doc_name)
    logger.info(
        "[INFO] Organized output into analysis/, extraction/, vision/, summary/")

    logger.info("[OK] Plan execution completed")
    logger.info("[INFO] Results saved to: %s", output_file)

    # Print summary
    task_results = result.get("task_results", {})
    print(f"\nExecution Summary:")
    print("-" * 50)
    print(f"  Plan: {args.plan}")
    print(f"  Session: {result.get('session_id', 'N/A')}")
    print(f"  Steps Completed: {len(task_results)}")
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
    from gptase.evals.runner import list_eval_papers

    if args.list:
        papers = list_eval_papers()
        if not papers:
            print("No eval papers found. Add data/evals/<paper_id>/golden.yaml to get started.")
        else:
            print("Available eval papers:")
            for paper_id in papers:
                print(f"  {paper_id}")
        return 0

    if not args.paper:
        logger.error("[ERROR] Paper ID required. Use -p/--paper or --list")
        return 1

    try:
        runner = EvalRunner(paper_id=args.paper, cache_dir=args.cache_dir)
    except FileNotFoundError as exc:
        logger.error("[ERROR] %s", exc)
        return 1

    if args.agent:
        results = [await runner.eval_agent(args.agent, live=args.live)]
    else:
        results = await runner.eval_all(live=args.live)

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
