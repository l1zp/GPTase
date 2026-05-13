#!/usr/bin/env python3
"""Run a predefined extraction plan through the orchestrator harness."""

import argparse
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path

from gptase.core.orchestrator import AgentOrchestrator
from gptase.core.types import DispatchRequest
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
    plans_dir = get_paths().project_root / "config" / "plans"
    for plan_path in sorted(plans_dir.glob("*.md")):
        title = _read_plan_title(plan_path)
        print(f"- {plan_path.stem}: {title}")


def _read_plan_title(plan_path: Path) -> str:
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line.removeprefix("Goal:").strip()
    return plan_path.name


def _render_plan_prompt(
    plan_id: str,
    document_path: Path,
    workspace_dir: Path,
) -> str:
    plan_path = get_paths().project_root / "config" / "plans" / f"{plan_id}.md"
    if not plan_path.is_file():
        raise FileNotFoundError(f"Plan not found: {plan_path}")

    return (plan_path.read_text(encoding="utf-8").replace(
        "{{document_path}}",
        str(document_path)).replace("{{si_document_path}}",
                                    "").replace("{{workspace_dir}}",
                                                str(workspace_dir)))


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

    try:
        plan_prompt = _render_plan_prompt(args.plan, target_file, output_dir)
    except FileNotFoundError as exc:
        logger.error("[ERROR] %s", exc)
        return

    if args.review:
        prompt_file = output_dir / "plan_prompt.md"
        prompt_file.write_text(plan_prompt, encoding="utf-8")
        print(f"[INFO] Plan prompt saved to: {prompt_file}")
        return

    orchestrator = AgentOrchestrator(FrameworkConfig())
    try:
        result = await orchestrator.dispatch(
            DispatchRequest(query=plan_prompt,
                            auto_execute=True,
                            document_path=str(target_file),
                            workspace_dir=str(output_dir)))
    finally:
        await orchestrator.close()

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
