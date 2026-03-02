#!/usr/bin/env python3
"""Standard Enzyme Reaction Extraction Runner.

This script demonstrates the AI-native orchestration pattern:
1. Load a Standard Operating Procedure (SOP) defined in JSON.
2. Execute the task via the generic AgentOrchestrator.
3. Handle cross-agent data flow automatically through the execution context.
"""

import argparse
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path

from gptase.agents.orchestrator import AgentOrchestrator
from gptase.core.config import FrameworkConfig
from gptase.core.logging import setup_logging
from gptase.core.paths import get_paths

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
    parser.add_argument("--enable-vision",
                        action="store_true",
                        help="Enable vision model analysis of figures")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Run the extraction pipeline using the unified SOP executor."""
    log_level = "DEBUG" if args.debug else "WARNING"
    setup_logging(log_level)
    paths = get_paths()

    # 1. Resolve input
    target_file = paths.resolve_input_path(
        args.input) if args.input else paths.get_document_path("listov2025")
    if not target_file.exists():
        logger.error(f"Input file not found: {target_file}")
        return

    # 2. Resolve output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = paths.output_dir / target_file.stem / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Starting Expert Pipeline for: {target_file.name}")
    print(f"[INFO] Output directory: {output_dir}")

    # 2. Prepare Orchestrator
    config = FrameworkConfig(log_level=log_level)
    orchestrator = AgentOrchestrator(config)

    # Vision analysis is now part of the default pipeline
    print(f"[INFO] Using plan: enzyme_extraction_pipeline_sop")
    print(
        f"[INFO] Vision analysis: {'enabled' if not args.enable_vision else 'enabled (parallel)'}"
    )

    try:
        # 3. Execute SOP
        # The SOP defines the flow: Scan -> (Extract + Vision) -> Summarize
        task = {
            "id": f"extraction_{target_file.stem}",
            "plan_id": "enzyme_extraction_pipeline_sop",
            "document_path": str(target_file),
            "text": target_file.read_text(encoding="utf-8"),
            "output_dir": str(output_dir)  # Pass for caching
        }

        result = await orchestrator.execute_task(task)

        # 4. Process Results
        if result.get("status") == "success":
            print("[OK] Pipeline completed successfully.")
            summary = result.get("execution_summary", {})
            print(
                f"[INFO] Total Steps: {summary.get('total_steps')} | Completed: {summary.get('completed_steps')}"
            )

            # Step 2 results (kinetics) and Step 3 results (summary) are in 'step_results'
            step_results = result.get("step_results", [])
            for res in step_results:
                print(
                    f"[INFO] [STEP {res['step_id']}] {res['agent']}.{res['action']} -> {res['status']}"
                )

            # Save results to output directory
            results_file = output_dir / "results.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Results saved to: {results_file}")

            # Save each step's output separately
            for res in step_results:
                step_file = output_dir / f"step_{res['step_id']}_{res['action']}.json"
                with open(step_file, 'w', encoding='utf-8') as f:
                    json.dump(res.get('outputs', {}), f, indent=2, ensure_ascii=False)
                print(f"[INFO] Step {res['step_id']} output: {step_file}")

        else:
            print(f"[ERROR] Pipeline failed: {result.get('error')}")
            # Save error result
            error_file = output_dir / "error.json"
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Error details saved to: {error_file}")

    except Exception as e:
        print(f"[ERROR] Execution Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
    finally:
        await orchestrator.shutdown()
        print("[INFO] Resources cleaned up.")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
