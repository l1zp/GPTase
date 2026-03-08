#!/usr/bin/env python3
"""
Vision Image Analyzer - Analyze image content using Vision Model

This example demonstrates how to:
1. Use MarkdownAgent with multimodal support for image analysis
2. Leverage agent configuration for model settings and system prompts
3. Extract tabular data and insights from scientific figures
"""

import argparse
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path

from gptase.agents import Agent
from gptase.agents import AgentTask
from gptase.models.model import Model
from gptase.utils.paths import get_paths

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_tables_from_content(content: str) -> list:
    """Extract CSV data from analysis content.

    Handles multiple formats:
    1. Markdown code blocks (```csv ... ```)
    2. JSON output with extracted_tables field
    3. Generic code blocks that look like tables

    Args:
        content: Analysis text response

    Returns:
        List of CSV strings
    """
    import re
    csv_blocks = []

    # Try to parse as JSON first (agent's structured output)
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            # Check for extracted_tables in agent output format
            if "extracted_tables" in data:
                for table in data["extracted_tables"]:
                    if isinstance(table, dict) and "csv_data" in table:
                        csv_blocks.append(table["csv_data"])
                    elif isinstance(table, str):
                        csv_blocks.append(table)
            # Check for analysis_results with content
            if "analysis_results" in data and not csv_blocks:
                for result in data["analysis_results"]:
                    if isinstance(result, dict) and "content" in result:
                        # Recursively check nested content
                        nested = extract_tables_from_content(result["content"])
                        csv_blocks.extend(nested)
        if csv_blocks:
            return csv_blocks
    except json.JSONDecodeError:
        pass

    # Try markdown code blocks with csv tag
    csv_blocks = re.findall(r'```csv\s*(.*?)\s*```', content, re.DOTALL)

    # Also try generic code blocks that look like tables
    generic_blocks = re.findall(r'```\s*(.*?)\s*```', content, re.DOTALL)
    for block in generic_blocks:
        if block.strip() and ',' in block and '\n' in block:
            if block not in csv_blocks:
                csv_blocks.append(block)

    return csv_blocks


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Vision Image Analyzer - Analyze images using Vision Model',
        epilog='Examples:\n'
        '  python vision_image_analyzer.py\n'
        '  python vision_image_analyzer.py path/to/image.jpg\n'
        '  python vision_image_analyzer.py path/to/image.jpg --agent vision_image_analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'image_path',
        type=str,
        nargs='*',
        default=[
            'data/listov2025/images/e3bf399245fcb3278f61290fd7222520e502ef5e1fd64024ff9eff070de9cc4c.jpg'
        ],
        help='Path(s) to the image file(s) to analyze')
    parser.add_argument('--config',
                        '-c',
                        type=str,
                        default=None,
                        help='Path to LLM config file (JSON format)')
    parser.add_argument(
        '--agent',
        '-a',
        type=str,
        default='vision_image_analyzer',
        choices=['vision_image_analyzer', 'vision_image_analyzer_react'],
        help='Agent config to use for analysis')

    args = parser.parse_args()

    # Note: Model() internally loads FrameworkConfig from config/llm_config.template.json
    # Custom config can be specified via --config for advanced use cases
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"[ERROR] Config file not found: {args.config}")
            return
        # For custom config, set environment variable before Model() initialization
        import os
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        if 'llm_api_key' in config_data:
            os.environ['OPENAI_API_KEY'] = config_data['llm_api_key']

    paths = get_paths()

    # Validate image paths
    valid_paths = []
    for img_path in args.image_path:
        path = Path(img_path)
        if path.exists():
            valid_paths.append(str(path))
        else:
            logger.warning(f"[WARNING] Image file not found: {img_path}")

    if not valid_paths:
        logger.error("[ERROR] No valid image files found")
        return

    # Setup output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    first_image = Path(valid_paths[0])
    output_dir = paths.output_dir / first_image.stem / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[INFO] Initializing Vision Analyzer...")
    logger.info(f"[INFO] Using agent: {args.agent}")

    # Initialize model manager
    model_manager = Model()

    # Create agent from markdown definition
    agent = Agent.from_markdown(args.agent, model_manager=model_manager)

    logger.info(f"[INFO] Analyzing {len(valid_paths)} image(s)...")
    for p in valid_paths:
        logger.info(f"  - {p}")
    logger.info("=" * 60)

    # Build task with image paths for multimodal processing
    task = AgentTask(
        description=
        "Analyze the scientific figure(s) in detail. Extract any tabular data into CSV format, identify key findings and trends.",
        image_paths=valid_paths,
        output_dir=str(output_dir),
    )

    # Execute task (agent will use multimodal messages if images are present)
    result = await agent.process_task(task)

    # Process results
    if result.get("status") == "success":
        data = result.get("data", {})
        content = data.get("content", "") if isinstance(data, dict) else str(data)

        print(f"\n[ANALYSIS RESULT]")
        print(content)

        # Extract tables
        tables = extract_tables_from_content(content)

        # Save results
        analysis_results = {
            "image_paths": valid_paths,
            "agent": args.agent,
            "content": content,
            "output_dir": str(output_dir),
        }

        output_file = output_dir / "analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        logger.info(f"\n[OK] Results saved to: {output_file}")

        # Save CSV tables if any
        if tables:
            csv_output_path = output_dir / "extracted_tables.csv"
            with open(csv_output_path, "w", encoding="utf-8") as f:
                for img_path in valid_paths:
                    f.write(f"# Image: {img_path}\n")
                f.write(f"# Agent: {args.agent}\n\n")
                for i, table in enumerate(tables, 1):
                    f.write(f"# Table {i}\n")
                    f.write(table.strip())
                    f.write("\n\n")
            logger.info(
                f"[OK] Extracted {len(tables)} table(s) saved to: {csv_output_path}")

        # Summary
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        total_tokens = usage.get("total_tokens") or usage.get(
            "prompt_tokens", 0) + usage.get("completion_tokens", 0)
        logger.info("\n[SUMMARY]")
        logger.info(f"  Agent: {args.agent}")
        logger.info(f"  Images Analyzed: {len(valid_paths)}")
        logger.info(f"  Tables Extracted: {len(tables)}")
        logger.info(f"  Total Tokens: {total_tokens}")
        logger.info(f"  Output: {output_dir}")
    else:
        logger.error(f"[ERROR] Analysis failed: {result.get('error')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[INFO] Operation cancelled by user.")
    except Exception as e:
        logger.exception(f"[ERROR] Unexpected error: {e}")
