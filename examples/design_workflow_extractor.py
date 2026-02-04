"""Demonstration of enzyme design workflow extraction using LLM.

This script extracts enzyme design steps and workflows from scientific literature,
including design objectives, methodology steps, key parameters, and validation approaches.

This version uses the EnzymeDesignExtractorAgent directly (delegation pattern).
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from src.agents.specialized.enzyme_design_extractor_agent import \
    EnzymeDesignExtractorAgent
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.document import DocumentLoaderTool
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


def log_section(title: str,
                items: list,
                item_formatter: callable,
                none_msg: str = None) -> None:
    """Log a section of extraction results.

    Args:
        title: Section title to display.
        items: List of items to format and display.
        item_formatter: Function to format each item for logging.
        none_msg: Message to log if items is empty.
    """
    if not items:
        if none_msg:
            logger.info(none_msg)
        return

    logger.info("%s (%d):", title, len(items))
    for item in items:
        item_formatter(item)


def format_truncated_list(items: list, max_show: int, separator: str = ", ") -> str:
    """Format a list with truncation if too many items.

    Args:
        items: List of items to format.
        max_show: Maximum number of items to show.
        separator: String to join items with.

    Returns:
        Formatted string with truncation indicator if needed.
    """
    if not items:
        return ""
    result = separator.join(str(x) for x in items[:max_show])
    if len(items) > max_show:
        result += " ..."
    return result


def log_extraction_results(data: dict, output_file) -> None:
    """Log extraction results to console.

    Args:
        data: Extraction result data
        output_file: Output file path for saving results
    """
    logger.info("Design extraction completed successfully!")

    # Chain of Thought
    cot_steps = data.get("chain_of_thought", [])

    def format_cot(cot):
        step_num = cot.get("step", "?")
        phase = cot.get("phase", "Unknown")
        thought = truncate_text(cot.get("thought", "N/A"), 80)
        logger.info("  [Step %s - %s]", step_num, phase)
        logger.info("    Thought: %s", thought)

    if cot_steps:
        logger.info("[Chain of Thought] (%d reasoning steps):", len(cot_steps))
        for cot in cot_steps[:3]:
            format_cot(cot)
        if len(cot_steps) > 3:
            logger.info("  ... and %d more reasoning steps", len(cot_steps) - 3)
    else:
        logger.info("[INFO] No chain of thought found.")

    # Design Objectives
    log_section(
        "[Design Objectives]",
        data.get("design_objectives", []),
        lambda obj: logger.info("  - %s", obj),
        "[INFO] No design objectives found.",
    )

    # Key Decisions
    def format_decision(decision):
        dec_title = truncate_text(decision.get("decision", "N/A"), 60)
        outcome = truncate_text(decision.get("outcome", "N/A"), 60)
        logger.info("  - Decision: %s", dec_title)
        logger.info("    Outcome: %s", outcome)

    log_section("[Key Decisions]", data.get("key_decisions", []), format_decision)

    # Design Steps
    def format_step(step):
        step_id = step.get("step_id", "?")
        category = step.get("category", "General")
        desc = truncate_text(step.get("description", "N/A"), 100)
        techniques = step.get("techniques", [])

        logger.info("  [Step %s] %s", step_id, category)
        logger.info("    Description: %s", desc)
        if techniques:
            logger.info("    Techniques: %s", format_truncated_list(techniques, 3))

    design_steps = data.get("design_steps", [])
    if design_steps:
        logger.info("[Design Steps] (%d):", len(design_steps))
        for step in design_steps:
            format_step(step)
    else:
        logger.info("[INFO] No design steps found.")

    # Key Constraints
    log_section(
        "[Key Constraints]",
        data.get("key_constraints", []),
        lambda c: logger.info("  - %s", c),
    )

    # Optimization Cycles
    def format_cycle(cycle):
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

    log_section("[Optimization Cycles]", data.get("optimization_cycles", []),
                format_cycle)

    # Validation Approach
    validation = data.get("validation_approach")
    if validation:
        logger.info("[Validation Approach]:")
        logger.info("  %s", truncate_text(validation, 200))

    # Experimental Conditions
    exp_conditions = data.get("experimental_conditions", {})
    if exp_conditions and any(exp_conditions.values()):
        logger.info("[Experimental Conditions]:")
        for key, value in exp_conditions.items():
            if value:
                logger.info("  %s: %s", key, value)

    # Results
    results = data.get("results", {})
    if results and any(results.values()):
        logger.info("[Results]:")
        final_variants = results.get("final_variants", [])
        if final_variants:
            logger.info("  Final variants: %s",
                        format_truncated_list(final_variants, 5))
        metrics = results.get("performance_metrics", {})
        if metrics:
            logger.info("  Performance metrics:")
            for key, value in list(metrics.items())[:3]:
                logger.info("    %s: %s", key, value)

    # Final Answer
    final_answer = data.get("final_answer", {})
    if final_answer:
        summary = final_answer.get("summary")
        if summary:
            logger.info("[Final Answer Summary]:")
            logger.info("  %s", truncate_text(summary, 300))

        success_metrics = final_answer.get("success_metrics", {})
        if success_metrics and any(success_metrics.values()):
            logger.info("[Success Metrics]:")
            for key, value in success_metrics.items():
                if value:
                    logger.info("  %s: %s", key, value)

        innovations = final_answer.get("key_innovations", [])
        log_section(
            "[Key Innovations]",
            innovations,
            lambda i: logger.info("  - %s", i),
        )

    # Save results
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
        # Try user-provided path directly first (relative to cwd)
        # Then fall back to paths.resolve_input_path() for legacy compatibility
        if args.input:
            input_path = Path(args.input)
            logger.debug("Checking input path: %s (exists: %s)", input_path,
                         input_path.exists())
            # Check if path exists (handles both absolute and relative paths)
            if input_path.exists():
                target_file = input_path.resolve()
                logger.debug("Using direct path: %s", target_file)
            else:
                target_file = paths.resolve_input_path(args.input)
                logger.debug("Using resolved path: %s", target_file)
        else:
            target_file = paths.get_document_path("listov2025")

        logger.info("Target file: %s", target_file)

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
        load_result = await loader.execute(source_type="file", path=str(target_file))

        logger.debug("Load result status: %s", load_result.status)
        logger.debug("Load result data keys: %s",
                     list(load_result.data.keys()) if load_result.data else [])

        if load_result.status == "error":
            logger.error("Error loading document: %s", load_result.error)
            return

        document_text = load_result.data.get("text", "")
        logger.debug("Document text length: %d", len(document_text))

        if not document_text:
            logger.error("No content extracted from document")
            return

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
