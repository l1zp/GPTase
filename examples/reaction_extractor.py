#!/usr/bin/env python3
"""Run a predefined extraction plan through the orchestrator harness."""

import argparse
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path

from gptase.agents.plan_loader import PlanRegistry
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig
from gptase.utils.paths import get_paths

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GPTase Enzyme Extraction Runner (Harness Mode)")
    parser.add_argument("-i",
                        "--input",
                        type=str,
                        default=None,
                        help="Input markdown file path")
    parser.add_argument("-o",
                        "--output",
                        type=str,
                        default=None,
                        help="Output directory")
    parser.add_argument(
        "-p",
        "--plan",
        type=str,
        default="enzyme_extraction_pipeline",
        help="Draft plan ID to execute",
    )
    parser.add_argument("--list-plans",
                        action="store_true",
                        help="List available predefined plans")
    parser.add_argument("--review",
                        action="store_true",
                        help="Stop after creating the draft plan")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def list_available_plans() -> None:
    registry = PlanRegistry.get_instance()
    plans = registry.list_plans()
    for plan in plans:
        print(f"- {plan['plan_id']}: {plan['name']}")


async def run_plan(args: argparse.Namespace) -> None:
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    paths = get_paths()
    documents_dir = paths.project_root / "data" / "input" / "documents"
    if args.input:
        arg_path = Path(args.input)
        target_file = arg_path if arg_path.is_absolute() else documents_dir / args.input
    else:
        target_file = documents_dir / "listov2025.md"
    if not target_file.exists():
        logger.error("[ERROR] Input file not found: %s", target_file)
        return

    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = (paths.project_root / "data" / "output" / target_file.stem
                      / timestamp)
    output_dir.mkdir(parents=True, exist_ok=True)

    orchestrator = AgentOrchestrator(FrameworkConfig())
    result = await orchestrator.dispatch({
        "description": f"Extract enzyme data from {target_file.name}",
        "plan_id": args.plan,
        "auto_execute": not args.review,
        "workspace_dir": str(output_dir),
    })

    output_file = output_dir / "results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"[INFO] Session: {result.get('session_id')}")
    print(f"[INFO] Status: {result.get('status')}")
    print(f"[INFO] Results saved to: {output_file}")


async def main(args: argparse.Namespace) -> None:
    if args.list_plans:
        await list_available_plans()
        return
    await run_plan(args)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
