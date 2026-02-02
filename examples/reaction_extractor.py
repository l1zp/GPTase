#!/usr/bin/env python3
"""Extract enzyme reaction data from markdown documents."""

import argparse
import asyncio
import json
import logging

from src.agents.specialized.enzyme_extraction_summary_agent import \
    EnzymeExtractionSummaryAgent
from src.agents.specialized.llm_enzyme_extractor_orchestrator import \
    LLMEnzymeExtractorAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry
from src.utils import default_manager

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration.

    Args:
        debug: Enable debug level logging
    """
    log_format = ("%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                  if debug else "%(levelname)s: %(message)s")
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=log_format,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract enzyme reaction data from markdown documents")
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
    parser.add_argument("--enable-vision",
                        action="store_true",
                        help="Enable vision model analysis of figures")
    parser.add_argument("--generate-summary",
                        action="store_true",
                        help="Generate summary report after extraction")
    parser.add_argument("--summary-formats",
                        nargs="+",
                        choices=["markdown", "json", "html"],
                        default=["markdown"],
                        help="Summary output formats")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def generate_summary(extraction_path: str, output_formats: list,
                           document_name: str) -> str:
    """Generate summary report for extraction results.

    Args:
        extraction_path: Path to extraction.json file
        output_formats: List of output formats
        document_name: Document name for report title

    Returns:
        STATUS_SUCCESS or STATUS_ERROR
    """
    try:
        memory_manager = MemoryManager()
        tool_registry = ToolRegistry()
        agent = EnzymeExtractionSummaryAgent(
            agent_id="extraction_summary",
            memory_manager=memory_manager,
            tool_registry=tool_registry,
        )

        task = {
            "extraction_path": extraction_path,
            "output_formats": output_formats,
            "document_name": document_name,
        }

        result = await agent.process_task(task)

        if result["status"] != STATUS_SUCCESS:
            logger.error("Summary generation failed: %s",
                         result.get("error", "Unknown error"))
            return STATUS_ERROR

        for file_path in result.get("files_written", []):
            logger.info("Summary written: %s", file_path)
        return STATUS_SUCCESS

    except Exception as e:
        logger.error("Summary generation exception: %s", str(e), exc_info=True)
        return STATUS_ERROR


async def main(args: argparse.Namespace) -> None:
    """Run enzyme extraction and print results."""
    setup_logging(args.debug)
    manager = default_manager()
    paths = get_paths()

    try:
        target_file = (paths.resolve_input_path(args.input)
                       if args.input else paths.get_document_path("listov2025"))

        if not target_file.exists():
            logger.error("Input file not found: %s", target_file)
            return

        output_file = (paths.resolve_output_path(args.output)
                       if args.output else paths.get_extraction_path(target_file.stem))

        logger.info("Processing file: %s", target_file)

        tool_registry = ToolRegistry()
        tool_registry.register_tools([DocumentLoaderTool()])
        memory_manager = MemoryManager()

        agent = LLMEnzymeExtractorAgent(
            agent_id="reaction_extractor",
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=manager,
            enable_vision_analysis=args.enable_vision,
        )

        result = await agent.process_task(
            {"document": {
                "source_type": "file",
                "path": str(target_file)
            }})

        if result["status"] != STATUS_SUCCESS:
            logger.error("LLM extraction failed: %s", result.get("error"))
            return

        data = result.get("data", {}).get("extraction", {})
        reactions = data.get("reactions", [])

        if reactions:
            logger.info("LLM extraction succeeded. Reactions parsed: %d",
                        len(reactions))
        else:
            logger.warning("No reactions found. Document may not contain "
                           "extractable enzyme kinetics data.")

        session_id = result.get("data", {}).get("session_id")
        if session_id and session_id != "tracking_disabled":
            logger.info("Session ID: %s", session_id)
            logger.info("View extraction details in the web UI:")
            logger.info("  Run: streamlit run src/webui/app.py")
            logger.info("  Navigate to: Agent Sessions")

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Extraction results saved to: %s", output_file)

        if args.generate_summary:
            logger.info("Generating summary report...")
            summary_status = await generate_summary(str(output_file),
                                                    args.summary_formats,
                                                    target_file.stem)
            if summary_status == STATUS_SUCCESS:
                logger.info("Summary report generated successfully!")
            else:
                logger.warning("Summary generation failed")

    except Exception as e:
        logger.error("Extraction failed: %s", str(e), exc_info=True)
    finally:
        await manager.shutdown()
        logger.info("Cleaned up resources.")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
