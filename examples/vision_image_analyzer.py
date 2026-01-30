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
import sys
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.specialized.vision_image_analyzer import VisionImageAnalyzerAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry
from src.utils import default_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Simplified format for CLI output
    datefmt='[%X]')
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
    parser.add_argument(
        '--csv-path',
        type=str,
        default='data/analysis/listov2025_structure_analysis_images.csv',
        help='Path to CSV file with image information')
    parser.add_argument('--relevant-only',
                        action='store_true',
                        default=False,
                        help='Only process images marked as relevant')

    args = parser.parse_args()

    # 1. Initialize Agent Dependencies
    logger.info("Initializing Vision Agent...")

    # We use a memory manager (even if not strictly needed for single-pass vision)
    memory_manager = MemoryManager()

    # Tool registry (empty for now, as vision agent uses direct model calls)
    tool_registry = ToolRegistry()

    # Create the Agent
    # If config file is provided, pass it to the agent to create its own ModelManager
    # Otherwise use the default manager
    try:
        if args.config and os.path.exists(args.config):
            agent = VisionImageAnalyzerAgent(agent_id="vision_demo",
                                             memory_manager=memory_manager,
                                             tool_registry=tool_registry,
                                             vision_config_path=args.config)
        else:
            # Fallback to default manager if no specific config
            if args.config:
                logger.warning(
                    f"Config file not found: {args.config}, using default environment settings"
                )

            manager = default_manager(enable_tracking=True)
            await manager.initialize_tracking()
            agent = VisionImageAnalyzerAgent(agent_id="vision_demo",
                                             memory_manager=memory_manager,
                                             tool_registry=tool_registry,
                                             model_manager=manager)
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        return

    # 2. Prepare Data
    logger.info(f"Loading image info from {args.csv_path}...")
    all_images = load_images_from_csv(args.csv_path, relevant_only=args.relevant_only)
    logger.info(f"Found {len(all_images)} images.")

    # 3. Filter Images (Script Logic)
    images_to_process = []

    if args.all:
        images_to_process = all_images
        if args.max_images:
            images_to_process = images_to_process[:args.max_images]
        logger.info(f"Processing all {len(images_to_process)} images...")
    elif args.image_number:
        target = str(args.image_number)
        images_to_process = [img for img in all_images if img["image_number"] == target]
        if not images_to_process:
            logger.error(f"Image #{target} not found in CSV.")
            return
        logger.info(f"Processing image #{target}...")
    else:
        # Default behavior: Image 7
        target = "7"
        images_to_process = [img for img in all_images if img["image_number"] == target]
        if not images_to_process:
            logger.error(f"Default image #7 not found in CSV.")
            return
        logger.info(f"Processing image #7 (Fig 3a) by default...")

    # 4. Construct Task
    # Note: We set relevant_only=False in the task because we've already filtered
    # the list `images_to_process` based on the args.
    task = {
        "images": images_to_process,
        "base_dir": "data/listov2025",
        "relevant_only": False
    }

    # 5. Run Agent
    logger.info("\n--- Starting Analysis ---")
    result = await agent.process_task(task)

    # 6. Handle Results
    if result["status"] == STATUS_SUCCESS:
        data = result["data"]
        analysis_results = data.get("analysis_results", [])
        extracted_tables = data.get("extracted_tables", [])

        # Save JSON results
        output_path = "data/image_analysis_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        logger.info(f"\nAnalysis results saved to: {output_path}")

        # Save CSV tables
        if extracted_tables:
            csv_output_path = "data/image_analysis_extracted_tables.csv"
            with open(csv_output_path, "w", encoding="utf-8") as f:
                for item in extracted_tables:
                    f.write(f"# Image {item['image_number']}: {item['image_path']}\n")
                    f.write(item["csv_data"])
                    f.write("\n\n")
            logger.info(f"Extracted CSV data saved to: {csv_output_path}")

        # Print Summary
        success_count = sum(1 for r in analysis_results if "error" not in r)
        logger.info(f"\nSummary:")
        logger.info(f"  Processed: {data.get('total_images', 0)}")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Tables Extracted: {len(extracted_tables)}")
        logger.info(f"  Total Tokens: {data.get('total_tokens', 0)}")

    else:
        logger.error(f"Agent execution failed: {result.get('data', {}).get('error')}")

    # Cleanup
    await agent.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
