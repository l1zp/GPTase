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
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

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


def _organize_sop_output(result: dict, output_dir: Path, document_name: str) -> None:
    """Organize SOP output into structured directories.

    Creates analysis/, extraction/, vision/, summary/ directories with
    corresponding JSON and CSV files.
    """
    import csv
    from datetime import datetime

    step_results = result.get("step_results", {})
    if not step_results:
        return

    # Create output directories
    analysis_dir = output_dir / "analysis"
    extraction_dir = output_dir / "extraction"
    vision_dir = output_dir / "vision"
    summary_dir = output_dir / "summary"

    for d in [analysis_dir, extraction_dir, vision_dir, summary_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Process each step
    for step_id, step_data in step_results.items():
        if not isinstance(step_data, dict):
            continue

        # Extract content
        content = step_data.get("content", "")
        parsed = _parse_content_json(content)

        if not parsed:
            # Try to use step_data directly if it looks like structured data
            if any(k in step_data
                   for k in ["reactions", "images", "sections", "tables"]):
                parsed = step_data
            else:
                continue

        # Route to appropriate directory based on step_id
        if step_id == "1":
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

        elif step_id == "2a":
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

        elif step_id == "2b":
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

        elif step_id == "3":
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
    step_results = result.get("step_results", {})
    if step_results:
        lines.append("## Execution Summary")
        lines.append("")
        lines.append(f"- Steps completed: {len(step_results)}")
        for step_id, step_data in step_results.items():
            lines.append(f"  - Step {step_id}: completed")
        lines.append("")

    return "\n".join(lines)


async def run_sop(args: argparse.Namespace) -> int:
    """Execute an SOP workflow.

    Args:
        args: Parsed command-line arguments with plan, input, output, and debug options.
    """
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

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

    # Initialize workspace directory using ProjectPaths
    from gptase.utils.paths import ProjectPaths
    paths = ProjectPaths()

    doc_name = Path(args.input).stem if args.input else "interactive"
    workspace_dir = paths.get_sop_output_dir(document_name=doc_name, sop_id=args.plan)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[INFO] Executing SOP: %s", args.plan)
    result = await orchestrator.execute_sop(
        plan_id=args.plan,
        input_data=input_data,
        document_path=document_path,
        auto_checkpoint=auto_checkpoint,
        workspace_dir=str(workspace_dir),
    )

    # Cleanup: close database connections before event loop shuts down
    await orchestrator.close()

    if result.get("status") == "error":
        logger.error("[ERROR] SOP execution failed: %s", result.get("error"))
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
    _organize_sop_output(result, final_output_dir, doc_name)
    logger.info(
        "[INFO] Organized output into analysis/, extraction/, vision/, summary/")

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
