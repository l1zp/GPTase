#!/usr/bin/env python3
"""Test script for MinerUTool integration."""

import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.implementations import MinerUTool

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging format and level.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main():
    """Test MinerUTool with a sample PDF."""
    setup_logging()
    logger.info("Initializing MinerUTool...")
    tool = MinerUTool()

    logger.info(f"Tool name: {tool.name}")
    logger.info(f"Tool description: {tool.description}")
    logger.info(f"Tool timeout: {tool.timeout}s")
    logger.info("")

    pdf_path = "data/Röthlisberger2008.pdf"

    logger.info(f"Converting PDF: {pdf_path}")
    result = await tool.execute(pdf_path=pdf_path)

    if result.status == "success":
        logger.info("Conversion successful!")
        logger.info(f"  PDF name: {result.data['pdf_name']}")
        logger.info(f"  Markdown file: {result.data['markdown_file']}")
        logger.info(f"  Images dir: {result.data['images_dir']}")

        md_text = result.data.get("markdown_text")
        if md_text:
            lines = md_text.split("\n")
            logger.info(f"  Content lines: {len(lines)}")
            logger.info(f"  Content chars: {len(md_text)}")
            logger.info(f"  Images: {md_text.count('![](')}")
            logger.info("")
            logger.info("First 500 characters:")
            logger.info(md_text[:500])
    else:
        logger.error(f"Conversion failed: {result.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
