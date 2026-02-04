"""Tests for MinerUTool."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.tools.base import ToolStatus


@pytest.fixture
def mock_mineru_module():
    """Mock MinerU module as being installed."""
    mock_mineru = MagicMock()
    mock_mineru.__version__ = "0.1.0"

    # Patch sys.modules to have mineru available
    import sys
    sys.modules["mineru"] = mock_mineru
    sys.modules["mineru.cli"] = MagicMock()
    sys.modules["mineru.cli.common"] = MagicMock()
    sys.modules["mineru.cli.common"].do_parse = MagicMock()
    sys.modules["mineru.cli.common"].read_fn = MagicMock()

    yield mock_mineru

    # Clean up
    for module in ["mineru", "mineru.cli", "mineru.cli.common"]:
        sys.modules.pop(module, None)


@pytest.fixture
def mineru_tool(mock_mineru_module):
    """Create a MinerUTool instance with mocked dependencies."""
    # Import after mocking to avoid import error
    from src.tools.document import MinerUTool
    return MinerUTool()


class TestMinerUTool:
    """Test suite for MinerUTool."""

    def test_initialization(self, mineru_tool):
        """Test MinerUTool initialization."""
        assert mineru_tool.name == "mineru"
        assert mineru_tool.description == "Convert PDF to Markdown using MinerU"
        assert mineru_tool.timeout == 300
        assert mineru_tool.DEFAULT_OUTPUT_DIR == "data/mineru_output"
        assert mineru_tool.DEFAULT_BACKEND == "pipeline"
        assert mineru_tool.DEFAULT_PARSE_METHOD == "auto"

    def test_initialization_checks_mineru_installation(self):
        """Test that initialization checks for MinerU installation."""
        import builtins
        import sys

        # Ensure mineru is not in sys.modules
        for module in ["mineru", "mineru.cli", "mineru.cli.common"]:
            sys.modules.pop(module, None)

        # Patch __import__ to only fail on 'mineru'
        original_import = builtins.__import__

        def selective_import(name, *args, **kwargs):
            if name == "mineru":
                raise ImportError("No module named 'mineru'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            from src.tools.document import MinerUTool
            with pytest.raises(ImportError) as exc_info:
                MinerUTool()

            assert "MinerU is not installed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_nonexistent_pdf(self, mineru_tool):
        """Test execute with non-existent PDF file."""
        result = await mineru_tool.execute(pdf_path="/nonexistent/file.pdf")

        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    @patch("src.tools.document.asyncio.to_thread")
    @patch("src.tools.document.os.path.exists")
    async def test_execute_success(self, mock_exists, mock_to_thread, mineru_tool):
        """Test successful PDF conversion."""
        mock_exists.return_value = True
        mock_to_thread.return_value = {
            "success": True,
            "pdf_name": "test",
            "markdown_file": "data/mineru_output/test/auto/test.md",
            "images_dir": "data/mineru_output/test/auto/images",
            "output_dir": "data/mineru_output/test/auto",
        }

        from src.tools.document import MinerUTool
        with patch.object(MinerUTool, "_read_markdown_file", return_value="# Test"):
            result = await mineru_tool.execute(pdf_path="test.pdf")

            assert result.status == ToolStatus.SUCCESS
            assert result.data["pdf_name"] == "test"
            assert result.data["markdown_text"] == "# Test"

    @pytest.mark.asyncio
    @patch("src.tools.document.asyncio.to_thread")
    @patch("src.tools.document.os.path.exists")
    async def test_execute_mineru_failure(self, mock_exists, mock_to_thread,
                                          mineru_tool):
        """Test when MinerU conversion fails."""
        mock_exists.return_value = True
        mock_to_thread.return_value = {
            "success": False,
            "error": "MinerU conversion failed",
        }

        result = await mineru_tool.execute(pdf_path="test.pdf")

        assert result.status == ToolStatus.ERROR
        assert "MinerU conversion failed" in result.error_message

    @pytest.mark.asyncio
    @patch("src.tools.document.asyncio.to_thread")
    @patch("src.tools.document.os.path.exists")
    async def test_execute_without_reading_markdown(self, mock_exists, mock_to_thread,
                                                    mineru_tool):
        """Test execute with read_markdown=False."""
        mock_exists.return_value = True
        mock_to_thread.return_value = {
            "success": True,
            "pdf_name": "test",
            "markdown_file": "data/mineru_output/test/auto/test.md",
            "images_dir": "data/mineru_output/test/auto/images",
            "output_dir": "data/mineru_output/test/auto",
        }

        result = await mineru_tool.execute(pdf_path="test.pdf", read_markdown=False)

        assert result.status == ToolStatus.SUCCESS
        assert result.data["markdown_text"] is None

    def test_get_schema(self, mineru_tool):
        """Test tool schema definition."""
        schema = mineru_tool.get_schema()

        assert schema["type"] == "object"
        assert "pdf_path" in schema["properties"]
        assert "output_dir" in schema["properties"]
        assert "read_markdown" in schema["properties"]
        assert "pdf_path" in schema["required"]

        assert schema["properties"]["pdf_path"]["type"] == "string"
        assert schema["properties"]["output_dir"]["type"] == "string"
        assert schema["properties"]["read_markdown"]["type"] == "boolean"
        assert schema["properties"]["output_dir"]["default"] == "data/mineru_output"
        assert schema["properties"]["read_markdown"]["default"] is True

    def test_read_markdown_file_success(self, mineru_tool, tmp_path):
        """Test successful markdown file reading."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test Content")

        content = mineru_tool._read_markdown_file(str(test_file))
        assert content == "# Test Content"

    def test_read_markdown_file_failure(self, mineru_tool):
        """Test markdown file reading failure."""
        content = mineru_tool._read_markdown_file("/nonexistent/file.md")
        assert content is None
