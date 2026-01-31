#!/usr/bin/env python3
"""Enzyme Extraction Summary Demo.

This script demonstrates how to use the EnzymeExtractionSummaryAgent
to generate comprehensive summaries of enzyme kinetics extraction results.

Example Usage:
    # Generate markdown summary
    python examples/enzyme_summary_demo.py

    # Generate multiple formats
    python examples/enzyme_summary_demo.py --formats markdown json html

    # Specify custom output directory
    python examples/enzyme_summary_demo.py --output-dir my_summaries
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.specialized.enzyme_extraction_summary_agent import (
    EnzymeExtractionSummaryAgent,
)
from src.core.constants import STATUS_SUCCESS
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate enzyme extraction summary reports"
    )
    parser.add_argument(
        "--extraction-path",
        type=str,
        default=None,
        help="Path to extraction.json file (default: data/output/listov2025/extraction/extraction.json)",
    )
    parser.add_argument(
        "--document-name",
        type=str,
        default=None,
        help="Document name for report title (default: auto-detected from path)",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["markdown", "json", "html"],
        default=["markdown"],
        help="Output formats to generate (default: markdown)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for summary files (default: auto-determined)",
    )
    return parser.parse_args()


async def main():
    """Main function to generate summary."""
    args = parse_args()

    # Determine extraction path
    if args.extraction_path:
        extraction_path = args.extraction_path
    else:
        # Default to listov2025 extraction
        paths = get_paths()
        extraction_path = str(
            paths.data_dir / "output" / "listov2025" / "extraction" / "extraction.json"
        )

    # Check if extraction file exists
    if not Path(extraction_path).exists():
        print(f"Error: Extraction file not found: {extraction_path}")
        print("\nHint: Run the enzyme extractor first:")
        print("  python examples/reaction_extractor.py")
        sys.exit(1)

    # Determine document name
    document_name = args.document_name
    if not document_name:
        # Auto-detect from path
        extraction_path_obj = Path(extraction_path)
        if "output" in extraction_path_obj.parts:
            output_idx = extraction_path_obj.parts.index("output")
            if output_idx + 1 < len(extraction_path_obj.parts):
                document_name = extraction_path_obj.parts[output_idx + 1]
            else:
                document_name = "unknown"
        else:
            document_name = extraction_path_obj.parent.name

    print(f"Generating summary for: {document_name}")
    print(f"Extraction file: {extraction_path}")
    print(f"Output formats: {', '.join(args.formats)}")
    print()

    # Initialize agent components
    memory_manager = MemoryManager()
    tool_registry = ToolRegistry()

    # Create summary agent
    agent = EnzymeExtractionSummaryAgent(
        agent_id="summary_demo",
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        model_manager=None,  # Not needed for summaries
    )

    # Prepare task
    task = {
        "extraction_path": extraction_path,
        "output_formats": args.formats,
        "document_name": document_name,
    }

    if args.output_dir:
        task["output_dir"] = args.output_dir

    # Generate summary
    try:
        result = await agent.process_task(task)

        if result.get("status") in ("success", STATUS_SUCCESS):
            print("Summary generated successfully!")
            print()

            # Print key findings
            summary = result.get("summary", {})
            findings = summary.get("key_findings", [])
            if findings:
                print("Key Findings:")
                for finding in findings:
                    print(f"  - {finding}")
                print()

            # Print output files
            files_written = result.get("files_written", [])
            if files_written:
                print("Output files:")
                for filepath in files_written:
                    print(f"  - {filepath}")
                print()

            # Print statistics
            stats = summary.get("statistics", {})
            if stats:
                total = stats.get("total_variants", 0)
                print(f"Total variants analyzed: {total}")

                for param in ["kcat", "Km", "kcat_over_KM", "Tm"]:
                    if param in stats:
                        s = stats[param]
                        if s["count"] > 0:
                            print(f"  {param}: {s['count']} variants ({s['coverage']:.1f}% coverage)")
        else:
            error = result.get("error", "Unknown error")
            print(f"Error: {error}")
            sys.exit(1)

    except Exception as e:
        print(f"Error generating summary: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
