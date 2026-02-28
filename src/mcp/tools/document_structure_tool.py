"""Document Structure Analysis Tool.

This tool provides high-performance regex-based scanning of scientific documents
to extract hierarchical sections, tables (Markdown/HTML), and images.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.core.constants import DocumentLimits
from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


# Model definitions for structured output
class Section(BaseModel):
    title: str
    level: int
    start_line: int
    end_line: int
    content: str


class Table(BaseModel):
    table_number: int
    type: str
    headers: List[str]
    row_count: int
    full_content: str


class ImageMetadata(BaseModel):
    image_number: int
    image_path: str
    caption: str


class DocumentStructureTool(BaseTool):
    """Tool for physical document structure scanning using regex."""

    def __init__(self):
        super().__init__(
            name="document_structure_tool",
            description=
            "Extract sections, tables, and images from Markdown documents using regex.",
            timeout=Timeouts.DOCUMENT_ANALYSIS,
        )

        # Migrated patterns
        self._html_table_pattern = r'<table>(.*?)</table>'
        self._image_pattern = r'!\[\]\((images/[^)]+)\)'
        self._min_pipe_count = DocumentLimits.MIN_PIPE_COUNT

    async def execute(self, text: str, **kwargs) -> ToolResult:
        """Execute physical scan of the document."""
        try:
            if not text:
                return ToolResult.from_error("No text provided for scanning.")

            sections = self._identify_sections(text)
            tables = self._extract_tables(text)
            images = self._extract_images(text)

            return ToolResult.success({
                "sections": [s.model_dump() for s in sections],
                "tables": [t.model_dump() for t in tables],
                "images": [i.model_dump() for i in images],
                "total_tables": len(tables),
                "total_images": len(images)
            })
        except Exception as e:
            logger.error(f"Structural scan failed: {e}")
            return ToolResult.from_error(str(e))

    def _identify_sections(self, text: str) -> List[Section]:
        sections = []
        lines = text.split('\n')
        current = None
        start_idx = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.strip('#').strip()
                if current:
                    current.end_line = i - 1
                    current.content = '\n'.join(lines[start_idx:i])
                    sections.append(current)
                current = Section(title=title,
                                  level=level,
                                  start_line=i,
                                  end_line=i,
                                  content="")
                start_idx = i

        if current:
            current.end_line = len(lines) - 1
            current.content = '\n'.join(lines[start_idx:])
            sections.append(current)
        return sections

    def _extract_tables(self, text: str) -> List[Table]:
        tables = []
        lines = text.split('\n')

        # 1. Markdown Tables
        for i in range(len(lines)):
            line = lines[i].strip()
            if '|' in line and line.count('|') >= self._min_pipe_count:
                if i + 1 < len(lines) and '|---' in lines[i + 1]:
                    table_start = i
                    rows = []
                    j = i + 2
                    while j < len(lines) and '|' in lines[j] and lines[j].count(
                            '|') >= self._min_pipe_count:
                        rows.append(lines[j])
                        j += 1

                    tables.append(
                        Table(table_number=len(tables) + 1,
                              type="markdown",
                              headers=[c.strip() for c in line.split('|')[1:-1]],
                              row_count=len(rows),
                              full_content='\n'.join(lines[table_start:j])))

        # 2. HTML Tables
        html_matches = re.finditer(self._html_table_pattern, text, re.DOTALL)
        for match in html_matches:
            content = match.group(0)
            tables.append(
                Table(
                    table_number=len(tables) + 1,
                    type="html",
                    headers=[],  # Simplified for tool
                    row_count=content.count('<tr>') - 1,
                    full_content=content))
        return tables

    def _extract_images(self, text: str) -> List[ImageMetadata]:
        images = []
        matches = re.finditer(self._image_pattern, text)
        for i, match in enumerate(matches):
            # Attempt to find caption in following line
            caption = "No caption found"
            lines = text[match.end():].split('\n')
            for line in lines:
                if line.strip() and not line.strip().startswith('!'):
                    caption = line.strip()
                    break

            images.append(
                ImageMetadata(image_number=i + 1,
                              image_path=match.group(1),
                              caption=caption))
        return images

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Document text to scan"
                }
            },
            "required": ["text"]
        }
