#!/usr/bin/env python3
"""
Vision Image Analyzer - Analyze image content using Vision Model

This example demonstrates how to:
1. Use MarkdownAgent with vision model for image analysis
2. Encode images as base64 for multi-modal LLMs
3. Extract tabular data and insights from scientific figures
"""

import asyncio
import base64
import json
import logging
import os

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig
from src.core.logging import setup_logging
from src.core.paths import get_paths

# Configure logging
setup_logging("INFO")
logger = logging.getLogger(__name__)


async def analyze_image_direct(image_path: str, model_manager) -> dict:
    """Analyze image directly using vision model.

    Args:
        image_path: Path to image file
        model_manager: Model manager instance

    Returns:
        Dict with analysis content and usage
    """
    # Get config for vision agent
    vision_config = model_manager.get_config_for_agent("vision_image_analyzer")
    provider = model_manager.create_provider(vision_config)

    # Read and encode image
    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")

    # Build prompt for scientific figure analysis
    prompt = """Analyze this scientific figure in detail:
1. Describe what type of figure it is (plot, diagram, table, etc.)
2. Extract all tabular data into CSV format
3. Identify key findings and trends
4. Note any relevant numerical values, labels, or annotations

If you see a table or plot, extract the data as CSV code block."""

    # Build multi-modal message
    messages = [{
        "role":
        "user",
        "content": [{
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        }, {
            "type": "text",
            "text": prompt
        }]
    }]

    # Stream analysis
    response_content = ""
    usage = {}
    async for chunk in provider.generate_stream(messages):
        if chunk.content:
            response_content += chunk.content
        if chunk.is_complete and chunk.metadata:
            usage = chunk.metadata.get("usage", {})

    return {"content": response_content, "usage": usage}


def extract_tables_from_content(content: str) -> list:
    """Extract CSV code blocks from analysis content.

    Args:
        content: Analysis text response

    Returns:
        List of CSV strings
    """
    import re
    csv_blocks = re.findall(r'```csv\s*(.*?)\s*```', content, re.DOTALL)
    # Also try generic code blocks
    csv_blocks.extend(re.findall(r'```\s*(.*?)\s*```', content, re.DOTALL))
    return csv_blocks


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Vision Image Analyzer - Analyze images using Vision Model',
        epilog='Examples:\n'
        '  python vision_image_analyzer.py\n'
        '  python vision_image_analyzer.py path/to/image.jpg\n'
        '  python vision_image_analyzer.py path/to/image.jpg --config config/llm_config.qwen_vl.example.json',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'image_path',
        type=str,
        nargs='?',
        default=
        'data/listov2025/images/e3bf399245fcb3278f61290fd7222520e502ef5e1fd64024ff9eff070de9cc4c.jpg',
        help='Path to the image file to analyze')
    parser.add_argument('--config',
                        '-c',
                        type=str,
                        default=None,
                        help='Path to LLM config file (JSON format)')

    args = parser.parse_args()

    # Load custom config if provided
    if args.config:
        if not os.path.exists(args.config):
            logger.error(f"[ERROR] Config file not found: {args.config}")
            return

        with open(args.config, 'r') as f:
            config_data = json.load(f)

        config = FrameworkConfig(**config_data)
    else:
        config = FrameworkConfig()

    paths = get_paths()

    # Validate image path
    if not os.path.exists(args.image_path):
        logger.error(f"[ERROR] Image file not found: {args.image_path}")
        return

    logger.info("[INFO] Initializing Vision Analyzer...")

    # Initialize orchestrator to get model manager
    orchestrator = AgentOrchestrator(config)
    model_manager = orchestrator.model_manager

    logger.info(f"[INFO] Analyzing: {args.image_path}")
    logger.info("=" * 60)

    # Analyze image
    result = await analyze_image_direct(args.image_path, model_manager)

    # Display and save results
    print(f"\n[ANALYSIS RESULT]")
    print(result.get("content", ""))

    # Extract tables
    tables = extract_tables_from_content(result.get("content", ""))

    # Save JSON results
    analysis_results = [{
        "image_path": args.image_path,
        "content": result.get("content", ""),
        "usage": result.get("usage", {})
    }]

    output_path = paths.get_vision_analysis_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)
    logger.info(f"\n[OK] Results saved to: {output_path}")

    # Save CSV tables if any
    if tables:
        csv_output_path = paths.get_vision_tables_path()
        with open(csv_output_path, "w", encoding="utf-8") as f:
            f.write(f"# Image: {args.image_path}\n")
            for i, table in enumerate(tables, 1):
                f.write(f"# Table {i}\n")
                f.write(table.strip())
                f.write("\n\n")
        logger.info(
            f"[OK] Extracted {len(tables)} table(s) saved to: {csv_output_path}")

    # Summary
    usage = result.get("usage", {})
    total_tokens = usage.get("total_tokens") or usage.get(
        "prompt_tokens", 0) + usage.get("completion_tokens", 0)
    logger.info("\n[SUMMARY]")
    logger.info(f"  Tables Extracted: {len(tables)}")
    logger.info(f"  Total Tokens: {total_tokens}")

    await orchestrator.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[INFO] Operation cancelled by user.")
    except Exception as e:
        logger.exception(f"[ERROR] Unexpected error: {e}")
