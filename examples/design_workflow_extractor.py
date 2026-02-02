"""Demonstration of enzyme design workflow extraction using LLM.

This script extracts enzyme design steps and workflows from scientific literature,
including design objectives, methodology steps, key parameters, and validation approaches.

This version uses the EnzymeDesignExtractorAgent directly (delegation pattern).
"""

import argparse
import asyncio
import json
import logging

from src.agents.specialized.enzyme_design_extractor_agent import \
    EnzymeDesignExtractorAgent
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry
from src.utils import default_manager

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Configure logging format and level.

    Args:
        debug: If True, set log level to DEBUG; otherwise INFO.
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract enzyme design workflows from markdown documents")
    parser.add_argument("-i",
                        "--input",
                        type=str,
                        default=None,
                        help="Input markdown file path (default: listov2025.md)")
    parser.add_argument("-o",
                        "--output",
                        type=str,
                        default=None,
                        help="Output JSON file path")
    parser.add_argument("--debug",
                        action="store_true",
                        help="Enable debug-level logging")
    return parser.parse_args()


def truncate_text(text: str, max_len: int) -> str:
    """Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_len: Maximum length

    Returns:
        Truncated text
    """
    return text[:max_len - 3] + "..." if len(text) > max_len else text


def log_extraction_results(data: dict, output_file) -> None:
    """Log extraction results to console.

    Args:
        data: Extraction result data
        output_file: Output file path for saving results
    """
    logger.info("Design extraction completed successfully!")

    # Display design objectives
    objectives = data.get("design_objectives", [])
    if objectives:
        logger.info("[Design Objectives] (%d):", len(objectives))
        for obj in objectives:
            logger.info("  - %s", obj)
    else:
        logger.info("[INFO] No design objectives found.")

    # Display design steps
    design_steps = data.get("design_steps", [])
    if design_steps:
        logger.info("[Design Steps] (%d):", len(design_steps))
        for step in design_steps:
            step_id = step.get("step_id", "?")
            category = step.get("category", "General")
            desc = truncate_text(step.get("description", "N/A"), 100)
            techniques = step.get("techniques", [])

            logger.info("  [Step %s] %s", step_id, category)
            logger.info("    Description: %s", desc)
            if techniques:
                tech_str = ", ".join(techniques[:3])
                if len(techniques) > 3:
                    tech_str += " ..."
                logger.info("    Techniques: %s", tech_str)
    else:
        logger.info("[INFO] No design steps found.")

    # Display key constraints
    constraints = data.get("key_constraints", [])
    if constraints:
        logger.info("[Key Constraints] (%d):", len(constraints))
        for constraint in constraints:
            logger.info("  - %s", constraint)

    # Display optimization cycles
    opt_cycles = data.get("optimization_cycles", [])
    if opt_cycles:
        logger.info("[Optimization Cycles] (%d):", len(opt_cycles))
        for cycle in opt_cycles:
            cycle_id = cycle.get("cycle_id", "?")
            method = cycle.get("method", "Unknown")
            rounds = cycle.get("rounds")
            rounds_str = f" ({rounds} rounds)" if rounds else ""
            logger.info("  [Cycle %s] %s%s", cycle_id, method, rounds_str)
            improvements = cycle.get("improvements", [])
            if improvements:
                for imp in improvements[:2]:
                    logger.info("    - %s", imp)
                if len(improvements) > 2:
                    logger.info("    ... and %d more", len(improvements) - 2)

    # Display validation approach
    validation = data.get("validation_approach")
    if validation:
        logger.info("[Validation Approach]:")
        logger.info("  %s", truncate_text(validation, 200))

    # Display experimental conditions
    exp_conditions = data.get("experimental_conditions", {})
    if exp_conditions and any(exp_conditions.values()):
        logger.info("[Experimental Conditions]:")
        for key, value in exp_conditions.items():
            if value:
                logger.info("  %s: %s", key, value)

    # Display results
    results = data.get("results", {})
    if results and any(results.values()):
        logger.info("[Results]:")
        final_variants = results.get("final_variants", [])
        if final_variants:
            variants_str = ", ".join(final_variants[:5])
            if len(final_variants) > 5:
                variants_str += " ..."
            logger.info("  Final variants: %s", variants_str)
        metrics = results.get("performance_metrics", {})
        if metrics:
            logger.info("  Performance metrics:")
            for key, value in list(metrics.items())[:3]:
                logger.info("    %s: %s", key, value)

    # Display Chinese annotations
    annotations = data.get("annotations_zh")
    if annotations:
        logger.info("[Chinese Annotations]:")
        logger.info("  %s", truncate_text(annotations, 300))

    # Save results to JSON file
    logger.info("Saving results to: %s", output_file)
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Design extraction results saved successfully!")


async def main(args: argparse.Namespace) -> None:
    """Run enzyme design extraction using LLM and log results."""
    manager = default_manager()
    logger.info("Successfully initialized default Model.")

    paths = get_paths()

    try:
        target_file = (paths.resolve_input_path(args.input)
                       if args.input else paths.get_document_path("listov2025"))

        if not target_file.exists():
            logger.error("Input file not found: %s", target_file)
            return

        output_file = (paths.resolve_output_path(args.output) if args.output else
                       paths.get_extraction_path(f"{target_file.stem}_design"))

        logger.info("Processing file: %s", target_file)

        tool_registry = ToolRegistry()
        tool_registry.register_tools([DocumentLoaderTool()])
        memory_manager = MemoryManager()

        agent = EnzymeDesignExtractorAgent(
            agent_id="design_extractor",
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=manager,
        )

        loader = DocumentLoaderTool()
        load_result = await loader.execute(path=str(target_file))

        if load_result.status == "error":
            logger.error("Error loading document: %s", load_result.error)
            return

        document_text = load_result.data.get("content", "")

        logger.info("Extracting enzyme design workflow...")
        result = await agent.process_task({
            "text": document_text,
            "source_file": str(target_file)
        })

        if result.get("status") == "success":
            data = result.get("data", {})
            log_extraction_results(data, output_file)

            session_id = result.get("data", {}).get("session_id")
            if session_id and session_id != "tracking_disabled":
                logger.info("[Session] ID: %s", session_id)
                logger.info("[INFO] View extraction details in the web UI:")
                logger.info("  Run: streamlit run src/webui/app.py")
                logger.info("  Navigate to: Agent Sessions")
        else:
            error_msg = result.get("data", {}).get("error", "Unknown error")
            logger.error("Design extraction failed: %s", error_msg)

    except Exception as e:
        logger.error("Demo failed: %s", str(e), exc_info=True)
    finally:
        await manager.shutdown()
        logger.info("Cleaned up resources.")


if __name__ == "__main__":
    args = parse_args()
    setup_logging(debug=args.debug)
    asyncio.run(main(args))
