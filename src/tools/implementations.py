"""
Tool implementations for various tasks
"""

import asyncio
import logging
import math
import os
import re
import tempfile
from typing import Any, Dict, List

from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.simple import tool

logger = logging.getLogger(__name__)

# Use centralized timeout constants
_CODE_WRITER_TIMEOUT = Timeouts.CODE_WRITER
_CODE_EXECUTOR_TIMEOUT = Timeouts.CODE_EXECUTOR
_FILE_MANAGER_TIMEOUT = Timeouts.FILE_MANAGER
_WEB_SEARCH_TIMEOUT = Timeouts.WEB_SEARCH
_CALCULATOR_TIMEOUT = Timeouts.CALCULATOR
_DOCUMENT_LOADER_TIMEOUT = Timeouts.DOCUMENT_LOADER
_MINERU_TIMEOUT = Timeouts.MINERU

# Calculator constants
_CALC_ALLOWED_CHARS = set("0123456789+-*/.() ")


# Simple tools using @tool decorator
@tool(
    name="calculator",
    description="Perform mathematical calculations safely",
    timeout=Timeouts.CALCULATOR,
)
async def calculate(expression: str) -> Dict[str, Any]:
    """Evaluate a safe mathematical expression.

    Args:
        expression: Mathematical expression to evaluate (e.g., '2+2', '3*4/2').

    Returns:
        Dictionary with expression, result, and result type.

    Raises:
        ValueError: If expression contains invalid characters.
    """
    if not all(c in _CALC_ALLOWED_CHARS for c in expression):
        raise ValueError(f"Invalid characters in expression: {expression}")

    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {
            "expression": expression,
            "result": float(result) if isinstance(result, int) else result,
            "type": type(result).__name__,
        }
    except Exception as e:
        raise ValueError(f"Failed to evaluate expression: {e}")


# Backward compatibility: create wrapper classes
class CalculatorTool:
    """Wrapper class for backward compatibility."""

    def __init__(self):
        # The tool instance is created by the decorator
        self._tool = calculate

    def __getattr__(self, name):
        # Delegate all attribute access to the wrapped tool
        return getattr(self._tool, name)

    # Allow direct callable access
    async def execute(self, **kwargs):
        return await self._tool.execute(**kwargs)

    def get_schema(self):
        return self._tool.get_schema()

    @property
    def name(self):
        return self._tool.name

    @property
    def description(self):
        return self._tool.description

    @property
    def timeout(self):
        return self._tool.timeout


# Document tokenization constants
_TOKENS_PER_CHAR_ESTIMATE = 4.0

# File action constants
_FILE_ACTIONS = ["read", "list", "create_dir", "delete", "exists"]

# Source type constants
_SOURCE_TYPES = ["text", "file", "url"]


class CodeWriterTool(BaseTool):
    """Tool for writing code to files."""

    def __init__(self):
        super().__init__(
            name="code_writer",
            description="Write code content to a specified file path",
            timeout=_CODE_WRITER_TIMEOUT,
        )

    async def execute(self,
                      file_path: str,
                      content: str,
                      overwrite: bool = False) -> ToolResult:
        """Write code to a file.

        Args:
            file_path: Path where to write the file.
            content: Code content to write.
            overwrite: Whether to overwrite existing file.

        Returns:
            ToolResult with file path and size.
        """
        try:
            file_path = file_path if os.path.isabs(file_path) else os.path.abspath(
                file_path)

            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            if os.path.exists(file_path) and not overwrite:
                return ToolResult.error(
                    f"File {file_path} already exists and overwrite=False")

            with open(file_path, "w") as f:
                f.write(content)

            return ToolResult.success({
                "file_path": file_path,
                "size": len(content),
                "created": True
            })

        except Exception as e:
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path where to write the file"
                },
                "content": {
                    "type": "string",
                    "description": "Code content to write"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing file",
                    "default": False
                },
            },
            "required": ["file_path", "content"],
        }


class CodeExecutorTool(BaseTool):
    """Tool for executing Python code."""

    def __init__(self):
        super().__init__(
            name="code_executor",
            description="Execute Python code and return results",
            timeout=_CODE_EXECUTOR_TIMEOUT,
        )

    async def execute(self, code: str, working_dir: str = None) -> ToolResult:
        """Execute Python code safely.

        Args:
            code: Python code to execute.
            working_dir: Optional working directory for execution.

        Returns:
            ToolResult with output or error message.
        """
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name

            if working_dir:
                os.chdir(working_dir)

            process = await asyncio.create_subprocess_exec(
                "python3",
                temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return ToolResult.success({
                    "output": stdout.decode("utf-8"),
                    "return_code": process.returncode,
                })

            return ToolResult.error(
                f"Code execution failed: {stderr.decode('utf-8')}",
                metadata={"return_code": process.returncode},
            )

        except Exception as e:
            return ToolResult.error(str(e))
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for code execution",
                    "default": None
                },
            },
            "required": ["code"],
        }


class FileManagerTool(BaseTool):
    """Tool for file system operations."""

    def __init__(self):
        super().__init__(
            name="file_manager",
            description="Manage files and directories",
            timeout=_FILE_MANAGER_TIMEOUT,
        )

    async def execute(self, action: str, path: str, **kwargs) -> ToolResult:
        """Perform file system operations.

        Args:
            action: File operation to perform (read, list, create_dir, delete, exists).
            path: File or directory path.

        Returns:
            ToolResult with operation result.
        """
        try:
            if action == "read":
                with open(path, "r") as f:
                    content = f.read()
                return ToolResult.success({"content": content, "size": len(content)})

            if action == "list":
                items = os.listdir(path)
                return ToolResult.success({"items": items, "count": len(items)})

            if action == "create_dir":
                os.makedirs(path, exist_ok=True)
                return ToolResult.success({"created": path})

            if action == "delete":
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
                return ToolResult.success({"deleted": path})

            if action == "exists":
                return ToolResult.success({
                    "exists": os.path.exists(path),
                    "is_file": os.path.isfile(path),
                    "is_dir": os.path.isdir(path),
                })

            return ToolResult.error(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _FILE_ACTIONS,
                    "description": "File operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
            },
            "required": ["action", "path"],
        }


# Simple tools using @tool decorator
@tool(
    name="web_search",
    description="Search the web for information (mock implementation)",
    timeout=Timeouts.WEB_SEARCH,
)
async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Mock web search - integrate with search APIs in production.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default: 5).

    Returns:
        Dictionary with query, mock results, and total count.
    """
    query_slug = query.replace(" ", "-")
    mock_results = [{
        "title": f"Result {i + 1} for '{query}'",
        "url": f"https://example.com/search/{query_slug}-{i + 1}",
        "snippet": f"This is a mock search result snippet for {query}...",
    } for i in range(max_results)]

    return {"query": query, "results": mock_results, "total_found": len(mock_results)}


# Backward compatibility: create wrapper classes
class WebSearchTool:
    """Wrapper class for backward compatibility."""

    def __init__(self):
        # The tool instance is created by the decorator
        self._tool = web_search

    def __getattr__(self, name):
        # Delegate all attribute access to the wrapped tool
        return getattr(self._tool, name)

    # Allow direct callable access
    async def execute(self, **kwargs):
        return await self._tool.execute(**kwargs)

    def get_schema(self):
        return self._tool.get_schema()

    @property
    def name(self):
        return self._tool.name

    @property
    def description(self):
        return self._tool.description

    @property
    def timeout(self):
        return self._tool.timeout


class DocumentLoaderTool(BaseTool):
    """Load documents from text, file path, or URL and return plain text."""

    def __init__(self):
        super().__init__(
            name="document_loader",
            description="Load PDF/HTML/Text from file or URL and return plain text",
            timeout=_DOCUMENT_LOADER_TIMEOUT,
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
            return ToolResult.error(str(e))

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
            timeout=_MINERU_TIMEOUT,
        )
        self._check_mineru_installation()

    def _check_mineru_installation(self) -> None:
        """Check if MinerU is installed.

        Raises:
            ImportError: If MinerU is not installed.
        """
        try:
            import mineru
            logger.info("MinerU version: %s", getattr(mineru, "__version__", "unknown"))
        except ImportError as e:
            raise ImportError(
                "MinerU is not installed. Please install it using:\n"
                "  pip install mineru\n"
                "Or for development version:\n"
                "  pip install git+https://github.com/opendatalab/MinerU.git") from e

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
            return ToolResult.error(f"PDF file not found: {pdf_path}")

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
            return ToolResult.error(str(e))

        if not result["success"]:
            return ToolResult.error(result["error"])

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
