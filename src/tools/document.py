"""
Document loading and processing tools.
"""

import asyncio
import logging
import math
import os
import re
from typing import Any, Dict

from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# Document tokenization constants
_TOKENS_PER_CHAR_ESTIMATE = 4.0

# Source type constants
_SOURCE_TYPES = ["text", "file", "url"]


class DocumentLoaderTool(BaseTool):
    """Load documents from text, file path, or URL and return plain text."""

    def __init__(self):
        super().__init__(
            name="document_loader",
            description="Load PDF/HTML/Text from file or URL and return plain text",
            timeout=Timeouts.DOCUMENT_LOADER,
        )

    async def execute(
        self,
        source_type: str,
        content: str = None,
        path: str = None,
        url: str = None,
    ) -> ToolResult:
        """Load document from specified source.

        Args:
            source_type: Type of source (text, file, url).
            content: Inline text content.
            path: File path.
            url: URL to fetch.

        Returns:
            ToolResult with document text and metrics.
        """
        try:
            text = await self._load_content(source_type, content, path, url)
            metrics = self._calculate_metrics(text)

            logger.info("Document loaded: %s", metrics)
            return ToolResult.success({
                "text": text,
                "length": len(text),
                "metrics": metrics
            })

        except Exception as e:
            return ToolResult.from_error(str(e))

    async def _load_content(self, source_type: str, content: str, path: str,
                            url: str) -> str:
        """Load content based on source type.

        Args:
            source_type: Type of source to load from.
            content: Inline text content.
            path: File path.
            url: URL to fetch.

        Returns:
            Loaded text content.

        Raises:
            ValueError: If required parameters are missing.
        """
        source_type = (source_type or "").lower()

        if source_type == "text":
            return content or ""

        if source_type == "file":
            if not path:
                raise ValueError("Missing file path")
            return self._load_from_file(path)

        if source_type == "url":
            if not url:
                raise ValueError("Missing URL")
            return self._load_from_url(url)

        raise ValueError(f"Unsupported source_type: {source_type}")

    def _load_from_file(self, path: str) -> str:
        """Load content from a file path.

        Args:
            path: Path to the file.

        Returns:
            File content as text.
        """
        ext = os.path.splitext(path)[1].lower()

        with open(path, "rb") as f:
            data = f.read()

        if ext == ".pdf":
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(path)
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                raise ValueError(f"PDF parsing failed: {e}")

        return data.decode("utf-8", errors="ignore")

    def _load_from_url(self, url: str) -> str:
        """Load content from a URL.

        Args:
            url: URL to fetch.

        Returns:
            URL content as text.
        """
        import urllib.request
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _calculate_metrics(self, text: str) -> Dict[str, Any]:
        """Calculate document metrics for context estimation.

        Args:
            text: Document text.

        Returns:
            Dictionary with various metrics.
        """
        char_length = len(text)
        word_count = len(re.findall(r"\w+", text))
        line_count = (text.count("\n") + 1) if text else 0
        approx_tokens = int(math.ceil(char_length / _TOKENS_PER_CHAR_ESTIMATE))

        # Try to get precise token count using tiktoken
        precise_tokens = None
        try:
            import tiktoken
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = tiktoken.get_encoding("p50k_base")
            precise_tokens = len(enc.encode(text))
        except Exception as e:
            logger.warning("Tiktoken tokenization failed: %s", e)

        return {
            "char_length": char_length,
            "word_count": word_count,
            "line_count": line_count,
            "approx_tokens": approx_tokens,
            "tokens_precise": precise_tokens,
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": _SOURCE_TYPES
                },
                "content": {
                    "type": "string"
                },
                "path": {
                    "type": "string"
                },
                "url": {
                    "type": "string"
                },
            },
            "required": ["source_type"],
        }


class MinerUTool(BaseTool):
    """PDF to Markdown conversion tool using MinerU."""

    DEFAULT_OUTPUT_DIR = "data/mineru_output"
    DEFAULT_BACKEND = "pipeline"
    DEFAULT_PARSE_METHOD = "auto"

    def __init__(self):
        super().__init__(
            name="mineru",
            description="Convert PDF to Markdown using MinerU",
            timeout=Timeouts.MINERU,
        )

    async def execute(
        self,
        pdf_path: str,
        output_dir: str = None,
        read_markdown: bool = True,
    ) -> ToolResult:
        """Convert PDF to Markdown using MinerU.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Optional output directory override.
            read_markdown: Whether to read and return markdown text content.

        Returns:
            ToolResult with conversion results.
        """
        if not os.path.exists(pdf_path):
            return ToolResult.from_error(f"PDF file not found: {pdf_path}")

        output_dir = output_dir or self.DEFAULT_OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        try:
            result = await asyncio.to_thread(
                self._run_mineru,
                pdf_path,
                output_dir,
            )
        except Exception as e:
            logger.exception("MinerU conversion failed")
            return ToolResult.from_error(str(e))

        if not result["success"]:
            return ToolResult.from_error(result["error"])

        markdown_text = None
        if read_markdown and result.get("markdown_file"):
            markdown_text = self._read_markdown_file(result["markdown_file"])

        return ToolResult.success({
            "pdf_path": pdf_path,
            "pdf_name": result["pdf_name"],
            "markdown_file": result["markdown_file"],
            "images_dir": result["images_dir"],
            "output_dir": result["output_dir"],
            "markdown_text": markdown_text,
        })

    def _run_mineru(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """Run MinerU do_parse API (blocking call, run in thread pool).

        Args:
            pdf_path: Path to PDF file.
            output_dir: Output directory.

        Returns:
            Dictionary with conversion results.
        """
        from mineru.cli.common import do_parse
        from mineru.cli.common import read_fn

        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_bytes = read_fn(pdf_path)

        do_parse(
            output_dir=output_dir,
            pdf_file_names=[pdf_name],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=["en"],
            backend=self.DEFAULT_BACKEND,
            parse_method=self.DEFAULT_PARSE_METHOD,
            formula_enable=True,
            table_enable=True,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_middle_json=False,
            f_dump_model_output=False,
            f_dump_content_list=False,
        )

        parse_method_dir = os.path.join(output_dir, pdf_name, self.DEFAULT_PARSE_METHOD)
        markdown_file = os.path.join(parse_method_dir, f"{pdf_name}.md")
        images_dir = os.path.join(parse_method_dir, "images")

        if not os.path.exists(markdown_file):
            return {
                "success": False,
                "error": f"Markdown file not generated at {markdown_file}",
            }

        return {
            "success": True,
            "pdf_name": pdf_name,
            "markdown_file": markdown_file,
            "images_dir": images_dir,
            "output_dir": parse_method_dir,
        }

    def _read_markdown_file(self, markdown_path: str) -> str | None:
        """Read markdown file content.

        Args:
            markdown_path: Path to markdown file.

        Returns:
            Markdown content, or None if read fails.
        """
        try:
            with open(markdown_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            logger.warning("Failed to read markdown file: %s", e)
            return None

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "Path to the PDF file to convert"
                },
                "output_dir": {
                    "type": "string",
                    "description": "Output directory for converted files",
                    "default": MinerUTool.DEFAULT_OUTPUT_DIR,
                },
                "read_markdown": {
                    "type": "boolean",
                    "description": "Whether to read and return markdown text content",
                    "default": True,
                },
            },
            "required": ["pdf_path"],
        }
