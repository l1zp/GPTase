#!/usr/bin/env python3
"""
Vision Image Analyzer - Analyze image content using Qwen3-VL model
Refactored to use GPTase Agent Architecture (Provider -> Model -> Agent)

This example demonstrates how to:
1. Use the VisionImageAnalyzerAgent for structured image analysis
2. Configure the agent with custom model settings
3. Process batches of images from CSV
4. Extract tabular data automatically
"""

import argparse
import asyncio
import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from src.agents.specialized.vision_image_analyzer import VisionImageAnalyzerAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry
from src.utils import default_manager

logging.basicConfig(level=logging.INFO, format='%(message)s', datefmt='[%X]')
logger = logging.getLogger("vision_analyzer_demo")


def extract_image_path_from_markdown(markdown_path: str) -> str:
    """Extract actual path from Markdown image path format

    Example: ![](images/abc.jpg) -> images/abc.jpg
    """
    if markdown_path.startswith("![]("):
        return markdown_path[4:-1]  # Remove ![]( and )
    return markdown_path


def load_images_from_csv(csv_path: str,
                         relevant_only: bool = True) -> List[Dict[str, Any]]:
    """Load image information from CSV file

    Args:
        csv_path: Path to CSV file
        relevant_only: Whether to only load relevant images

    Returns:
        List of image information dictionaries
    """
    images = []
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter: Process only relevant images if requested
            if relevant_only and row.get("is_relevant", "false").lower() != "true":
                continue

            # Extract image path
            image_markdown = row.get("image_path", "")
            if not image_markdown or image_markdown == "![]()":
                continue

            actual_path = extract_image_path_from_markdown(image_markdown)

            # Structure matches what Agent expects, plus some metadata
            images.append({
                "image_number": row.get("image_number", ""),
                "figure_number": row.get("figure_number", ""),
                "caption": row.get("caption", ""),
                "image_path": actual_path,
                # Store analysis metadata in a nested dict if we wanted to use
                # agent's internal filtering, but we'll filter here.
                "analysis": {
                    "topics": row.get("topics", "").split(", "),
                    "description": row.get("description", ""),
                    "is_relevant": row.get("is_relevant", "false").lower() == "true"
                }
            })

    return images


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Vision Image Analyzer - Analyze images using Qwen3-VL via Agent',
        epilog='Examples:\n'
        '  python vision_image_analyzer.py --all\n'
        '  python vision_image_analyzer.py --image-number 7\n'
        '  python vision_image_analyzer.py --config config/llm_config.qwen_vl.example.json',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config',
                        type=str,
                        default='config/llm_config.qwen_vl.example.json',
                        help='Path to LLM configuration JSON file')
    parser.add_argument('--image-number',
                        type=int,
                        default=None,
                        help='Specific image number to analyze (default: 7 for Fig 3a)')
    parser.add_argument('--all',
                        action='store_true',
                        help='Analyze all relevant images')
    parser.add_argument('--max-images',
                        type=int,
                        default=None,
                        help='Maximum number of images to analyze')
    parser.add_argument('--csv-path',
                        type=str,
                        default=None,
                        help='Path to CSV file with image information')
    parser.add_argument('--relevant-only',
                        action='store_true',
                        default=False,
                        help='Only process images marked as relevant')

    args = parser.parse_args()
    paths = get_paths()

    logger.info("Initializing Vision Agent...")

    memory_manager = MemoryManager()
    tool_registry = ToolRegistry()

    try:
        if args.config and os.path.exists(args.config):
            agent = VisionImageAnalyzerAgent(agent_id="vision_demo",
                                             memory_manager=memory_manager,
                                             tool_registry=tool_registry,
                                             vision_config_path=args.config)
        else:
            if args.config:
                logger.warning(
                    f"Config file not found: {args.config}, using default settings")
            manager = default_manager(enable_tracking=True)
            await manager.initialize_tracking()
            agent = VisionImageAnalyzerAgent(agent_id="vision_demo",
                                             memory_manager=memory_manager,
                                             tool_registry=tool_registry,
                                             model_manager=manager)
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        return

    # Determine CSV path
    if args.csv_path:
        csv_path = Path(args.csv_path)
        if not csv_path.is_absolute():
            csv_path = paths.data_dir / args.csv_path
    else:
        csv_path = paths.get_structure_analysis_images_csv_path("listov2025")

    logger.info(f"Loading image info from {csv_path}...")
    all_images = load_images_from_csv(str(csv_path), relevant_only=args.relevant_only)
    logger.info(f"Found {len(all_images)} images.")

    # Filter images based on arguments
    if args.all:
        images_to_process = all_images[:args.
                                       max_images] if args.max_images else all_images
        logger.info(f"Processing all {len(images_to_process)} images...")
    elif args.image_number:
        target = str(args.image_number)
        images_to_process = [img for img in all_images if img["image_number"] == target]
        if not images_to_process:
            logger.error(f"Image #{target} not found in CSV.")
            return
        logger.info(f"Processing image #{target}...")
    else:
        target = "7"
        images_to_process = [img for img in all_images if img["image_number"] == target]
        if not images_to_process:
            logger.error(f"Default image #7 not found in CSV.")
            return
        logger.info("Processing image #7 (Fig 3a) by default...")

    task = {
        "images": images_to_process,
        "base_dir": "data/listov2025",
        "relevant_only": False
    }

    logger.info("\n--- Starting Analysis ---")
    result = await agent.process_task(task)

    if result["status"] == STATUS_SUCCESS:
        data = result["data"]
        analysis_results = data.get("analysis_results", [])
        extracted_tables = data.get("extracted_tables", [])

        # Save JSON results
        output_path = paths.get_vision_analysis_path()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        logger.info(f"\nAnalysis results saved to: {output_path}")

        # Save CSV tables
        if extracted_tables:
            csv_output_path = paths.get_vision_tables_path()
            with open(csv_output_path, "w", encoding="utf-8") as f:
                for item in extracted_tables:
                    f.write(f"# Image {item['image_number']}: {item['image_path']}\n")
                    f.write(item["csv_data"])
                    f.write("\n\n")
            logger.info(f"Extracted CSV data saved to: {csv_output_path}")

        success_count = sum(1 for r in analysis_results if "error" not in r)
        logger.info(f"\nSummary:")
        logger.info(f"  Processed: {data.get('total_images', 0)}")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Tables Extracted: {len(extracted_tables)}")
        logger.info(f"  Total Tokens: {data.get('total_tokens', 0)}")
    else:
        logger.error(f"Agent execution failed: {result.get('data', {}).get('error')}")

    await agent.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
