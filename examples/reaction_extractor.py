#!/usr/bin/env python3
"""Standard Enzyme Reaction Extraction Runner.

This script demonstrates the AI-native orchestration pattern:
1. Load a Standard Operating Procedure (SOP) defined in JSON.
2. Execute the task via the generic AgentOrchestrator and ExecutorAgent.
3. Handle cross-agent data flow automatically through the Executor context.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig
from src.core.logging import setup_logging
from src.core.paths import get_paths

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
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Run the extraction pipeline using the unified SOP executor."""
    setup_logging("DEBUG" if args.debug else "INFO")
    paths = get_paths()

    # 1. Resolve input
    target_file = paths.resolve_input_path(
        args.input) if args.input else paths.get_document_path("listov2025")
    if not target_file.exists():
        logger.error(f"Input file not found: {target_file}")
        return

    logger.info(f"🚀 Starting Expert Pipeline for: {target_file.name}")

    # 2. Prepare Orchestrator
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    try:
        # 3. Execute SOP
        # The 'enzyme_extraction_pipeline' SOP defines the flow: Scan -> Extract -> Summarize
        task = {
            "id": f"extraction_{target_file.stem}",
            "plan_id":
            "enzyme_extraction_pipeline_sop",  # Suffix _sop allows loading from config/sops/
            "document_path": str(target_file),
            "text": target_file.read_text(encoding="utf-8")
        }

        result = await orchestrator.execute_task(task)

        # 4. Process Results
        if result.get("status") == "success":
            logger.info("✅ Pipeline completed successfully.")
            summary = result.get("execution_summary", {})
            logger.info(
                f"Total Steps: {summary.get('total_steps')} | Completed: {summary.get('completed_steps')}"
            )

            # Step 2 results (kinetics) and Step 3 results (summary) are in 'step_results'
            step_results = result.get("step_results", [])
            for res in step_results:
                logger.info(
                    f"[STEP {res['step_id']}] {res['agent']}.{res['action']} -> {res['status']}"
                )
        else:
            logger.error(f"❌ Pipeline failed: {result.get('error')}")

    except Exception as e:
        logger.error(f"Execution Error: {e}", exc_info=args.debug)
    finally:
        await orchestrator.shutdown()
        logger.info("Resources cleaned up.")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
