"""Demonstration of LLM enzyme extraction using the default Model."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path to import local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.specialized.llm_enzyme_extractor import LLMEnzymeExtractorAgent
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry
from src.utils import default_manager


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract enzyme reaction data from markdown documents"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input markdown file path (default: data/listov2025.md)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: data/extraction/{input_stem}_extraction.json)"
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Run enzyme extraction using the default Model and print results."""
    try:
        # Initialize manager using default configuration
        manager = default_manager()
        print("Successfully initialized default Model.")

        # Determine input file path
        data_dir = Path(__file__).resolve().parent.parent / "data"
        if args.input:
            target_file = Path(args.input)
            if not target_file.is_absolute():
                target_file = data_dir / args.input
        else:
            # Default to listov2025.md for backward compatibility
            target_file = data_dir / "listov2025.md"

        if not target_file.exists():
            print(f"Error: Input file not found: {target_file}")
            return

        # Determine output file path
        if args.output:
            output_file = Path(args.output)
            if not output_file.is_absolute():
                output_file = data_dir / args.output
        else:
            # Default to extraction directory with input filename stem
            extraction_dir = data_dir / "extraction"
            output_file = extraction_dir / f"{target_file.stem}_extraction.json"

        print(f"Processing file: {target_file}")

        # Initialize tool registry and memory manager
        tool_registry = ToolRegistry()
        tool_registry.register_tools([DocumentLoaderTool()])
        memory_manager = MemoryManager()

        # Create LLMEnzymeExtractorAgent
        agent = LLMEnzymeExtractorAgent(
            agent_id="reaction_extractor",
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=manager
        )
        result = await agent.process_task(
            {"document": {
                "source_type": "file",
                "path": str(target_file)
            }})

        # Display and save results
        if result["status"] == "success":
            # LLMEnzymeExtractorAgent returns data nested in "extraction"
            data = result.get("data", {}).get("extraction", {})
            reactions = data.get("reactions", [])
            print(f"LLM extraction succeeded with default Model.")
            print(f"Reactions parsed: {len(reactions)}")

            # Save results to JSON file
            output_file.parent.mkdir(
                exist_ok=True)  # Ensure extraction directory exists
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
            print(f"Extraction results saved to: {output_file}")
        else:
            print(f"LLM extraction failed: {result.get('error')}")

    except Exception as e:
        print(f"Demo failed: {str(e)}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
