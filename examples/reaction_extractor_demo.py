"""Demonstration of LLM enzyme extraction using the default Model."""

import asyncio
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path to import local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.markdown_factory import MarkdownAgentFactory
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry
from src.utils import default_manager


async def main() -> None:
    """Run enzyme extraction using the default Model and print results."""
    try:
        # Initialize manager using default configuration
        manager = default_manager()
        print("Successfully initialized default Model.")

        # Find Markdown files in data directory
        data_dir = Path(__file__).resolve().parent.parent / "data"
        md_files = sorted(data_dir.glob("*.md"))

        if not md_files:
            print("No Markdown files found in ./data. Please add .md files and re-run.")
            return

        # Process listov2025.md file specifically
        target_file = data_dir / "listov2025.md"
        tool_registry = ToolRegistry()
        tool_registry.register_tools([DocumentLoaderTool()])
        memory_manager = MemoryManager()

        # Use MarkdownAgentFactory to create agent from markdown definition
        factory = MarkdownAgentFactory()
        agent = factory.create_agent("enzyme_kinetics_extractor",
                                     memory_manager,
                                     tool_registry,
                                     model_manager=manager)
        result = await agent.process_task(
            {"document": {
                "source_type": "file",
                "path": str(target_file)
            }})

        # Display and save results
        if result["status"] == "success":
            # MarkdownAgent returns data directly, not nested in "extraction"
            data = result.get("data", {})
            reactions = data.get("reactions", [])
            print(f"LLM extraction succeeded with default Model.")
            print(f"Reactions parsed: {len(reactions)}")

            # Save results to JSON file
            output_file = data_dir / "extraction" / "listov2025_extraction.json"
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
    asyncio.run(main())
