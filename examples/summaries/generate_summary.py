#!/usr/bin/env python3
"""Generate summary report for enzyme kinetics extraction results.

This script demonstrates how to use the EnzymeExtractionSummaryAgent to
generate comprehensive summaries of extraction results.
"""

import argparse
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.specialized.enzyme_extraction_summary_agent import \
    EnzymeExtractionSummaryAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry


async def generate_summary(
    extraction_path: str,
    output_formats: list,
    output_dir: str = None,
    document_name: str = None,
):
    """Generate summary report.

    Args:
        extraction_path: Path to extraction.json file
        output_formats: List of output formats (markdown, json, html)
        output_dir: Optional output directory path
        document_name: Optional document name for report title
    """
    # Initialize agent components
    memory_manager = MemoryManager()
    tool_registry = ToolRegistry()
    tool_registry.register_tools([])

    # Create agent
    agent = EnzymeExtractionSummaryAgent(
        agent_id="extraction_summary",
        memory_manager=memory_manager,
        tool_registry=tool_registry,
    )

    # Determine document name from path if not provided
    if not document_name:
        extraction_file = Path(extraction_path)
        # Try to extract document name from path
        # Expected path: data/output/{doc}/extraction/extraction.json
        parts = extraction_file.parts
        if "output" in parts:
            output_idx = parts.index("output")
            if output_idx + 1 < len(parts):
                document_name = parts[output_idx + 1]
            else:
                document_name = extraction_file.parent.parent.name
        else:
            document_name = extraction_file.parent.parent.name

    # Prepare task
    task = {
        "extraction_path": extraction_path,
        "output_formats": output_formats,
        "document_name": document_name,
    }

    if output_dir:
        task["output_dir"] = output_dir

    # Execute task
    print(f"Generating summary for: {document_name}")
    print(f"Extraction path: {extraction_path}")
    print(f"Output formats: {', '.join(output_formats)}")
    print()

    result = await agent.process_task(task)

    # Handle results
    if result["status"] == STATUS_SUCCESS:
        print("[SUCCESS] Summary generated successfully!")
        print()

        # Print key findings
        if "summary" in result:
            summary = result["summary"]
            print("Key Findings:")
            for finding in summary.get("key_findings", []):
                print(f"  - {finding}")
            print()

        # Print file locations
        if "files_written" in result:
            print("Files written:")
            for file_path in result["files_written"]:
                print(f"  - {file_path}")
            print()

        # Show preview of markdown output
        if "markdown" in result.get("outputs", {}):
            md_content = result["outputs"]["markdown"]
            lines = md_content.split("\n")
            preview_lines = min(30, len(lines))
            print("Markdown Preview (first 30 lines):")
            print("-" * 60)
            for line in lines[:preview_lines]:
                print(line)
            if len(lines) > preview_lines:
                print(f"... ({len(lines) - preview_lines} more lines)")
            print("-" * 60)

        return 0
    else:
        print(f"[ERROR] {result.get('error', 'Unknown error')}")
        return 1


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate summary report for enzyme kinetics extraction results",
        epilog="""
Examples:
  # Generate markdown summary for listov2025
  python generate_summary.py -i data/output/listov2025/extraction/extraction.json

  # Generate all formats (markdown, json, html)
  python generate_summary.py -i data/output/listov2025/extraction/extraction.json -f markdown json html

  # Specify custom output directory and document name
  python generate_summary.py -i extraction.json -o my_summary -d "My Paper"

  # Generate summary for zhang2022
  python generate_summary.py -i data/output/zhang2022/extraction/extraction.json
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to extraction.json file",
    )
    parser.add_argument(
        "-f",
        "--formats",
        nargs="+",
        choices=["markdown", "json", "html"],
        default=["markdown"],
        help="Output formats (default: markdown)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Output directory path (default: data/output/{doc}/summary)",
    )
    parser.add_argument(
        "-d",
        "--document-name",
        help="Document name for report title (default: auto-detected from path)",
    )

    args = parser.parse_args()

    # Validate input path
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {args.input}")
        return 1

    if not input_path.name == "extraction.json":
        print(f"[WARNING] Input file is not named 'extraction.json': {args.input}")

    # Generate summary
    return await generate_summary(
        extraction_path=str(input_path),
        output_formats=args.formats,
        output_dir=args.output_dir,
        document_name=args.document_name,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
