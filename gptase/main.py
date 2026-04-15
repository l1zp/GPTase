"""CLI entry point for GPTase."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

from .agents.enzyme_variant_normalizer import flatten_normalized_variants
from .core.orchestrator import AgentOrchestrator
from .core.types import DispatchRequest
from .utils.config import FrameworkConfig

logger = logging.getLogger(__name__)

# Plans listed here receive ``document_path`` instead of ``input_data["text"]``.
# The plan YAML is responsible for distributing the path to its steps.
# When adding a plan that reads the document path directly, add its ID here.
_DOCUMENT_PATH_ONLY_PLANS = {"enzyme_extraction_pipeline"}


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add shared args (--debug) to a sub-parser."""
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gptase",
        description="GPTase - Multi-Agent Framework for AI Task Automation",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── Three core modes ──────────────────────────────────────

    # chat: Auto Orchestrator (interactive runtime → direct answer / coordinator / plan handoff)
    chat_p = sub.add_parser("chat", help="Auto Orchestrator mode")
    chat_p.add_argument("description",
                        type=str,
                        nargs="?",
                        default=None,
                        help="Task description (prompted if omitted)")
    _add_common_args(chat_p)

    # agent: Direct single-agent execution
    agent_p = sub.add_parser("agent", help="Run a single agent directly")
    agent_p.add_argument("-n", "--name", type=str, required=True, help="Agent name")
    agent_p.add_argument("-d",
                         "--description",
                         type=str,
                         default=None,
                         help="Task description")
    _add_common_args(agent_p)

    # plan: Structured Plan workflows
    plan_p = sub.add_parser("plan", help="Plan workflows")
    plan_sub = plan_p.add_subparsers(dest="plan_action", help="Plan actions")
    plan_sub.add_parser("list", help="List available Plans")
    plan_sub.add_parser("sessions", help="List all sessions")

    plan_st = plan_sub.add_parser("status", help="Show session status")
    plan_st.add_argument("session_id", type=str, help="Session ID")

    plan_run = plan_sub.add_parser("run", help="Execute a Plan")
    plan_run.add_argument("-p", "--plan", type=str, required=True, help="Plan ID")
    plan_run.add_argument("-o",
                          "--output",
                          type=str,
                          default=None,
                          help="Output directory")
    plan_run.add_argument("--no-checkpoint",
                          action="store_true",
                          help="Disable auto checkpoint")
    plan_run.add_argument("--review",
                          action="store_true",
                          help="Draft plan only, no execution")
    plan_run.add_argument("--auto-replan",
                          action="store_true",
                          help="Allow auto follow-up plans")
    plan_run.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        metavar="FILE",
        help="Input file path (contents passed as input_data['text'])")
    _add_common_args(plan_run)

    plan_resume = plan_sub.add_parser("resume", help="Resume a session")
    plan_resume.add_argument("session_id", type=str, help="Session ID to resume")
    plan_resume.add_argument("--feedback",
                             type=str,
                             default=None,
                             help="Feedback to revise or continue")
    plan_resume.add_argument("--review",
                             action="store_true",
                             help="Draft only, no execution")
    plan_resume.add_argument("--auto-replan",
                             action="store_true",
                             help="Allow auto follow-up plans")

    # ── Utility commands ──────────────────────────────────────

    sub.add_parser("list", help="List available agents")
    sub.add_parser("status", help="Show system status")

    eval_p = sub.add_parser("eval", help="Evaluate agent output quality")
    eval_p.add_argument("-a", "--agent", type=str, required=True, help="Agent name")
    eval_p.add_argument("--live", action="store_true", help="Run live against LLM API")
    eval_p.add_argument("--save-output",
                        action="store_true",
                        help="Save live output to evals directory")
    eval_p.add_argument("--save",
                        type=str,
                        default=None,
                        help="Save JSON report to file")
    eval_p.add_argument("--config",
                        type=str,
                        default=None,
                        metavar="FILE",
                        help="LLM config JSON for live runs")

    web_p = sub.add_parser("web", help="Start the Web UI")
    web_p.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    web_p.add_argument("--host",
                       type=str,
                       default="127.0.0.1",
                       help="Host (default: 127.0.0.1)")

    return parser.parse_args()


async def run_chat(args: argparse.Namespace) -> int:
    """Auto Orchestrator mode: interactive runtime with plan handoff."""
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    description = args.description
    if not description:
        description = input("gptase> ").strip()
        if not description:
            return 0

    orchestrator = AgentOrchestrator(FrameworkConfig())
    try:
        result = await orchestrator.dispatch(
            DispatchRequest(query=description, auto_execute=True))
    finally:
        await orchestrator.close()

    if result.get("status") == "failed":
        logger.error("[ERROR] %s", result.get("error"))
        return 1

    data = result.get("data")
    if data and isinstance(data, dict):
        print(data.get("content", ""))
    elif data:
        print(data)
    return 0


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

    description = args.description
    if not description:
        logger.error("[ERROR] Task description required. Use -d/--description")
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

    logger.info("[INFO] Running agent: %s", agent_name)

    # Run agent
    result = await agent.run(prompt=description)

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

    tasks = result.get("tasks", {})
    if not tasks:
        return

    # Create output directories
    analysis_dir = output_dir / "analysis"
    extraction_dir = output_dir / "extraction"
    vision_dir = output_dir / "vision"
    normalized_dir = output_dir / "normalized"
    summary_dir = output_dir / "summary"

    for d in [analysis_dir, extraction_dir, vision_dir, normalized_dir, summary_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Process each step
    for task_id, task_data in tasks.items():
        if not isinstance(task_data, dict):
            continue
        task_output = task_data.get("output") if isinstance(task_data.get("output"),
                                                            dict) else task_data

        # Extract content
        content = task_output.get("content", "")
        parsed = _parse_content_json(content)

        if not parsed:
            # Try to use task_data directly if it looks like structured data
            if any(k in task_output
                   for k in ["reactions", "images", "sections", "tables"]):
                parsed = task_output
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
                            "Km":
                            kinetics.get("Km", ""),
                            "Km_unit":
                            kinetics.get("Km_unit", ""),
                            "kcat":
                            kinetics.get("kcat", ""),
                            "kcat_unit":
                            kinetics.get("kcat_unit", ""),
                            "kcat_over_Km":
                            kinetics.get("kcat_over_Km", kinetics.get("kcat/KM", "")),
                            "kcat_over_Km_unit":
                            kinetics.get("kcat_over_Km_unit",
                                         kinetics.get("kcat/KM_unit", "")),
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
            with open(normalized_dir / "normalized_variants.json",
                      "w",
                      encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            normalized_variants = parsed.get("normalized_variants", [])
            if normalized_variants:
                flat_rows = flatten_normalized_variants(normalized_variants)
                all_keys = []
                for row in flat_rows:
                    for key in row:
                        if key not in all_keys:
                            all_keys.append(key)
                with open(normalized_dir / "normalized_variants.csv",
                          "w",
                          encoding="utf-8",
                          newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=all_keys)
                    writer.writeheader()
                    for row in flat_rows:
                        writer.writerow(row)

        elif task_id == "4":
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
        "├── normalized/     # Normalized sequence and variant records",
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
        "### normalized/",
        "- `normalized_variants.json` - Reconciled variant records",
        "- `normalized_variants.csv` - Flat sequence/mutation/kinetics table",
        "",
        "### summary/",
        "- `summary.json` - Statistical summary",
        "- `summary.md` - Human-readable summary",
        "",
    ]

    # Add step results summary
    tasks = result.get("tasks", {})
    if tasks:
        lines.append("## Execution Summary")
        lines.append("")
        lines.append(f"- Steps completed: {len(tasks)}")
        for task_id, task_data in tasks.items():
            status = task_data.get("status", "completed") if isinstance(
                task_data, dict) else "completed"
            lines.append(f"  - Step {task_id}: {status}")
        lines.append("")

    return "\n".join(lines)


async def run_plan(args: argparse.Namespace) -> int:
    """Plan workflow dispatcher.

    Routes to sub-handlers based on args.plan_action.
    """
    level = logging.DEBUG if getattr(args, "debug", False) else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from gptase.agents.plan_loader import PlanRegistry

    registry = PlanRegistry.get_instance()

    action = getattr(args, "plan_action", None)
    if not action:
        # No sub-command: show help
        from gptase.utils import format_plan_list

        plans = registry.list_plans()
        print(format_plan_list(plans))
        return 0

    handlers = {
        "list": _plan_list,
        "sessions": _plan_sessions,
        "status": _plan_status,
        "run": _plan_run,
        "resume": _plan_resume,
    }
    handler = handlers.get(action)
    if handler:
        return await handler(args, registry)
    return 1


async def _plan_list(args: argparse.Namespace, registry) -> int:
    """List available Plans."""
    from gptase.utils import format_plan_list

    plans = registry.list_plans()
    print(format_plan_list(plans))
    return 0


async def _plan_sessions(args: argparse.Namespace, registry) -> int:
    """List all Plan execution sessions."""
    orchestrator = AgentOrchestrator(FrameworkConfig())
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


async def _plan_status(args: argparse.Namespace, registry) -> int:
    """Show status of a specific session."""
    orchestrator = AgentOrchestrator(FrameworkConfig())
    status = await orchestrator.get_session_status(args.session_id)

    if not status:
        logger.error("[ERROR] Session not found: %s", args.session_id)
        return 1

    print(f"Session Status: {args.session_id}")
    print("-" * 50)
    print(f"  Goal: {status.get('goal', '')}")
    print(f"  Status: {status['status']}")
    for key in ("current_plan", "progress", "runtime_progress_detail", "preflight",
                "goal_evaluation"):
        val = status.get(key)
        if val:
            label = key.replace("_", " ").title()
            print(f"  {label}: {val}")
    if status.get("tasks"):
        print("  Tasks:")
        for task_id in status["tasks"].keys():
            print(f"    - {task_id}")
    return 0


async def _plan_resume(args: argparse.Namespace, registry) -> int:
    """Resume a Plan execution session."""
    orchestrator = AgentOrchestrator(FrameworkConfig())
    logger.info("[INFO] Resuming session: %s", args.session_id)

    payload = {"session_id": args.session_id}
    if args.feedback:
        payload["feedback"] = args.feedback
    if not args.review:
        payload["approve_plan"] = True
    if args.auto_replan:
        payload["auto_replan"] = True

    try:
        result = await orchestrator.dispatch(DispatchRequest(**payload))
    finally:
        await orchestrator.close()
    return _write_harness_result(result, None, args.session_id)


async def _plan_run(args: argparse.Namespace, registry) -> int:
    """Execute a Plan."""
    from gptase.utils.paths import ProjectPaths

    paths = ProjectPaths()
    if args.output:
        workspace_dir = paths.resolve_output_path(args.output, default_subdir="output")
    else:
        workspace_dir = paths.get_plan_output_dir(document_name="interactive",
                                                  plan_id=args.plan)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    input_data: dict = {}
    if getattr(args, "input", None):
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error("[ERROR] Input file not found: %s", args.input)
            return 1
        if args.plan not in _DOCUMENT_PATH_ONLY_PLANS:
            input_data = {"text": input_path.read_text(encoding="utf-8")}

    orchestrator = AgentOrchestrator(FrameworkConfig())
    logger.info("[INFO] Executing draft plan via harness: %s", args.plan)
    try:
        result = await orchestrator.dispatch(
            DispatchRequest(
                query=f"Execute draft plan {args.plan}",
                plan_id=args.plan,
                input_data=input_data or None,
                document_path=args.input,
                auto_execute=not args.review,
                auto_replan=args.auto_replan,
                workspace_dir=str(workspace_dir),
            ))
    finally:
        await orchestrator.close()
    return _write_harness_result(result, str(workspace_dir), args.plan)


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

    if args.command == "chat":
        return asyncio.run(run_chat(args))
    elif args.command == "agent":
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
