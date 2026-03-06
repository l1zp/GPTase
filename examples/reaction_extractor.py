#!/usr/bin/env python3
"""Standard Enzyme Reaction Extraction Runner.

This script demonstrates the SOP orchestration pattern:
1. Load a Standard Operating Procedure (SOP) defined in YAML.
2. Execute via the SOPOrchestratorAgent.
3. Handle cross-agent data flow automatically through template variables.
"""

import argparse
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path

from gptase.sop import SOPOrchestratorAgent
from gptase.sop import SOPRegistry
from gptase.utils.paths import get_paths

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GPTase Enzyme Extraction Runner (SOP Mode)")
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
        help="SOP plan ID to execute",
    )
    parser.add_argument("--list-sops", action="store_true", help="List available SOPs")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def list_available_sops() -> None:
    """List all available SOP definitions."""
    from gptase.utils import format_sop_list

    registry = SOPRegistry.get_instance()
    sops = registry.list_sops()
    print(format_sop_list(sops, desc_width=80))


async def run_sop(args: argparse.Namespace) -> None:
    """Run the SOP extraction pipeline."""
    log_level = "DEBUG" if args.debug else "INFO"
    logging.basicConfig(level=getattr(logging, log_level),
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    paths = get_paths()

    # 1. Resolve input
    target_file = (paths.resolve_input_path(args.input)
                   if args.input else paths.get_document_path("listov2025"))
    if not target_file.exists():
        logger.error("[ERROR] Input file not found: %s", target_file)
        return

    # 2. Resolve output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = paths.output_dir / target_file.stem / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Starting SOP Pipeline for: {target_file.name}")
    print(f"[INFO] Output directory: {output_dir}")

    # 3. Load SOP definition
    registry = SOPRegistry.get_instance()
    sop = registry.get_sop(args.plan)

    print(f"[INFO] SOP: {sop.name or sop.plan_id} (v{sop.version})")
    print(f"[INFO] Steps: {len(sop.get_all_steps())}")

    # 4. Create orchestrator and execute
    orchestrator = SOPOrchestratorAgent()

    try:
        result = await orchestrator.execute_sop(
            plan_id=args.plan,
            input_data={
                "text": target_file.read_text(encoding="utf-8"),
            },
            document_path=str(target_file.parent),
        )

        # 5. Process Results
        if result.get("status") == "success":
            print("[OK] Pipeline completed successfully.")

            step_results = result.get("step_results", {})
            print(f"[INFO] Steps completed: {len(step_results)}")

            for step_id, step_data in step_results.items():
                print(f"[INFO] [STEP {step_id}] completed")

            # Save results to output directory
            results_file = output_dir / "results.json"
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"[INFO] Results saved to: {results_file}")

            # Save each step's output separately
            for step_id, step_data in step_results.items():
                step_file = output_dir / f"step_{step_id}.json"
                with open(step_file, "w", encoding="utf-8") as f:
                    json.dump(step_data, f, indent=2, ensure_ascii=False, default=str)
                print(f"[INFO] Step {step_id} output: {step_file}")

        else:
            print(f"[ERROR] Pipeline failed: {result.get('error')}")
            # Save error result
            error_file = output_dir / "error.json"
            with open(error_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"[INFO] Error details saved to: {error_file}")

    except Exception as e:
        print(f"[ERROR] Execution Error: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
    finally:
        await orchestrator.close()


async def main(args: argparse.Namespace) -> None:
    """Main entry point."""
    if args.list_sops:
        await list_available_sops()
    else:
        await run_sop(args)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
