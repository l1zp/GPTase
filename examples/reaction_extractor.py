#!/usr/bin/env python3
"""Extract enzyme reaction data from markdown documents."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract enzyme reaction data from markdown documents")
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input markdown file path (default: data/input/documents/listov2025.md)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help=("Output JSON file path "
              "(default: data/extraction/{input_stem}_extraction.json)"),
    )
    parser.add_argument(
        "--enable-vision",
        action="store_true",
        help="Enable vision model analysis of figures (Phase 2.2)",
    )
    parser.add_argument(
        "--generate-summary",
        action="store_true",
        help="Automatically generate summary report after extraction",
    )
    parser.add_argument(
        "--summary-formats",
        nargs="+",
        choices=["markdown", "json", "html"],
        default=["markdown"],
        help="Summary output formats (default: markdown)",
    )
    return parser.parse_args()


async def generate_summary(
    extraction_path: str,
    output_formats: list[str],
    document_name: str,
) -> str:
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

        if result["status"] == STATUS_SUCCESS:
            if "files_written" in result:
                print("[Summary] Files written:")
                for file_path in result["files_written"]:
                    print(f"  - {file_path}")
            return STATUS_SUCCESS
        else:
            print(f"[Summary] Error: {result.get('error', 'Unknown error')}")
            return STATUS_ERROR

    except Exception as e:
        print(f"[Summary] Exception: {str(e)}")
        return STATUS_ERROR


async def main(args: argparse.Namespace) -> None:
    """Run enzyme extraction and print results."""
    manager = default_manager()
    paths = get_paths()

    try:
        # Determine input file path
        if args.input:
            target_file = paths.resolve_input_path(args.input)
        else:
            target_file = paths.get_document_path("listov2025")

        if not target_file.exists():
            print(f"Error: Input file not found: {target_file}")
            return

        # Determine output file path
        if args.output:
            output_file = paths.resolve_output_path(args.output)
        else:
            output_file = paths.get_extraction_path(target_file.stem)

        print(f"Processing file: {target_file}")

        # Initialize and run extraction
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

        # Handle results
        if result["status"] == "success":
            data = result.get("data", {}).get("extraction", {})
            reactions = data.get("reactions", [])

            if reactions:
                print(f"LLM extraction succeeded with default Model.")
                print(f"Reactions parsed: {len(reactions)}")
            else:
                print("LLM extraction completed, but no reactions found.")
                print("This may indicate the document doesn't contain "
                      "extractable enzyme kinetics data.")

            # Display session ID
            session_id = result.get("data", {}).get("session_id")
            if session_id and session_id != "tracking_disabled":
                print(f"\nSession ID: {session_id}")
                print("View extraction details in the web UI:")
                print("  Run: streamlit run src/webui/app.py")
                print("  Navigate to: Extraction Sessions")

            # Save results
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
            print(f"Extraction results saved to: {output_file}")

            # Generate summary if requested
            if args.generate_summary:
                print("\n[Summary] Generating summary report...")
                summary_result = await generate_summary(
                    str(output_file),
                    args.summary_formats,
                    target_file.stem,
                )
                if summary_result == STATUS_SUCCESS:
                    print("[Summary] Summary report generated successfully!")
                else:
                    print("[Summary] Warning: Summary generation failed")
        else:
            print(f"LLM extraction failed: {result.get('error')}")

    except Exception as e:
        print(f"Demo failed: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        await manager.shutdown()
        print("Cleaned up resources.")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
