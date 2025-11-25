"""Demonstration of LLM enzyme extraction using the default ModelManager."""

import asyncio
import sys
import json
from pathlib import Path

# Ensure project root is on sys.path to import local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.implementations import LLMEnzymeExtractorTool
from src.utils import default_manager


async def main() -> None:
    """Run enzyme extraction using the default ModelManager and print results."""
    try:
        # Initialize manager using default configuration
        manager = default_manager()
        print("Successfully initialized default ModelManager.")

        # Find Markdown files in data directory
        data_dir = Path(__file__).resolve().parent.parent / "data"
        md_files = sorted(data_dir.glob("*.md"))

        if not md_files:
            print("No Markdown files found in ./data. Please add .md files and re-run.")
            return

        # Initialize tool with default manager
        tool = LLMEnzymeExtractorTool(manager=manager)

        # Process listov2025.md file specifically
        target_file = data_dir / "listov2025.md"
        result = await tool.safe_execute(
            source_type="file",
            path=str(target_file),
        )

        # Display and save results
        if result.status.value == "success":
            extraction = result.data.get("extraction", {})
            reactions = extraction.get("reactions", [])
            print(f"LLM extraction succeeded with default ModelManager.")
            print(f"Reactions parsed: {len(reactions)}")
            
            # Save results to JSON file
            output_file = data_dir / "extraction" / "listov2025_extraction.json"
            output_file.parent.mkdir(exist_ok=True)  # Ensure extraction directory exists
            with open(output_file, "w") as f:
                json.dump(result.data, f, indent=2, default=str)
            print(f"Extraction results saved to: {output_file}")
        else:
            print(f"LLM extraction failed: {result.error}")

    except Exception as e:
        print(f"Demo failed: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
