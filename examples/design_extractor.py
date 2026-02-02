"""Demonstration of enzyme design workflow extraction using LLM.

This script extracts enzyme design steps and workflows from scientific literature,
including design objectives, methodology steps, key parameters, and validation approaches.
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path to import local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.markdown_factory import MarkdownAgentFactory
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry
from src.utils import default_manager


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract enzyme design workflows from markdown documents")
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input markdown file path (default: data/input/documents/listov2025.md)")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: data/extraction/{input_stem}_design.json)"
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Run enzyme design extraction using LLM and print results."""
    # Initialize manager using default configuration
    manager = default_manager()
    print("Successfully initialized default Model.")

    # Get standardized paths
    paths = get_paths()

    try:
        # Determine input file path
        if args.input:
            target_file = paths.resolve_input_path(args.input)
        else:
            # Default to listov2025.md in documents directory
            target_file = paths.get_document_path("listov2025")

        if not target_file.exists():
            print(f"Error: Input file not found: {target_file}")
            return

        # Determine output file path
        if args.output:
            output_file = paths.resolve_output_path(args.output)
        else:
            # Default to extraction directory with input filename stem
            output_stem = f"{target_file.stem}_design"
            output_file = paths.get_extraction_path(output_stem)

        print(f"Processing file: {target_file}")

        # Initialize tool registry and memory manager
        tool_registry = ToolRegistry()
        tool_registry.register_tools([DocumentLoaderTool()])
        memory_manager = MemoryManager()

        # Create enzyme_design_parser agent using markdown factory
        factory = MarkdownAgentFactory()
        agent = factory.create_agent("enzyme_design_parser",
                                     memory_manager,
                                     tool_registry,
                                     model_manager=manager)

        # Load document content
        loader = DocumentLoaderTool()
        load_result = await loader.execute(path=str(target_file))

        if load_result.status == "error":
            print(f"Error loading document: {load_result.error}")
            return

        document_text = load_result.data.get("content", "")

        # Extract design workflow
        result = await agent.process_task(
            {"document": {
                "source_type": "text",
                "content": document_text
            }})

        # Display and save results
        if result.get("status") == "success":
            data = result.get("data", {})

            print(f"LLM design extraction succeeded with default Model.")

            # Display design objectives
            objectives = data.get("design_objectives", [])
            if objectives:
                print(f"\nDesign Objectives ({len(objectives)}):")
                for obj in objectives:
                    print(f"  - {obj}")
            else:
                print(f"\nNo design objectives found.")

            # Display design steps
            design_steps = data.get("design_steps", [])
            if design_steps:
                print(f"\nDesign Steps ({len(design_steps)}):")
                for step in design_steps:
                    desc = step.get("description", "N/A")[:80]
                    print(f"  [{step.get('step_id', '?')}] {desc}...")
            else:
                print(f"\nNo design steps found.")

            # Display key constraints
            constraints = data.get("key_constraints", [])
            if constraints:
                print(f"\nKey Constraints ({len(constraints)}):")
                for constraint in constraints:
                    print(f"  - {constraint}")

            # Display validation approach
            validation = data.get("validation_approach")
            if validation:
                print(f"\nValidation Approach:")
                print(f"  {validation[:200]}...")

            # Display Chinese annotations
            annotations = data.get("annotations_zh")
            if annotations:
                print(f"\nChinese Annotations:")
                print(f"  {annotations[:200]}...")

            # Save results to JSON file
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            print(f"\nDesign extraction results saved to: {output_file}")
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"Design extraction failed: {error_msg}")

    except Exception as e:
        print(f"Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up resources - close database connection
        await manager.shutdown()
        print("Cleaned up resources.")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
