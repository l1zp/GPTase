#!/usr/bin/env python3
"""Test script for MinerUTool integration."""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.implementations import MinerUTool


async def main():
    """Test MinerUTool with a sample PDF."""
    print("Initializing MinerUTool...")
    tool = MinerUTool()

    print(f"Tool name: {tool.name}")
    print(f"Tool description: {tool.description}")
    print(f"Tool timeout: {tool.timeout}s")
    print()

    # Test PDF conversion
    pdf_path = "data/Röthlisberger2008.pdf"

    print(f"Converting PDF: {pdf_path}")
    result = await tool.execute(pdf_path=pdf_path)

    if result.status == "success":
        print("Conversion successful!")
        print(f"  PDF name: {result.data['pdf_name']}")
        print(f"  Markdown file: {result.data['markdown_file']}")
        print(f"  Images dir: {result.data['images_dir']}")

        md_text = result.data.get("markdown_text")
        if md_text:
            lines = md_text.split("\n")
            print(f"  Content lines: {len(lines)}")
            print(f"  Content chars: {len(md_text)}")
            print(f"  Images: {md_text.count('![](')}")
            print()
            print("First 500 characters:")
            print(md_text[:500])
    else:
        print(f"Conversion failed: {result.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
