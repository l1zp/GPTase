"""Enzyme design agent for extracting enzyme design information."""

from typing import Any, Dict

from src.agents.base import BaseAgent
from src.core.constants import (
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_SUCCESS,
    STATUS_WORKING,
)
from src.memory.manager import MemoryManager
from src.tools.enzyme_extractor import extract_from_html, extract_steps
from src.tools.registry import ToolRegistry

# Source types
SOURCE_TYPE_TEXT = "text"
SOURCE_TYPE_HTML = "html"
SOURCE_TYPE_DEFAULT = SOURCE_TYPE_TEXT

# Tool names
TOOL_DOCUMENT_LOADER = "document_loader"

# Capability descriptions
CAPABILITY_ENZYME_DESIGN_EXTRACTION = "enzyme_design_extraction"
CAPABILITY_NLP_PARSING = "nlp_parsing"
CAPABILITY_PDF_HTML_TEXT_SUPPORT = "pdf_html_text_support"

# Response annotations
ANNOTATIONS_ZH = "提取到的步骤含保留英文术语，并提供中文标签说明。"


class EnzymeDesignAgent(BaseAgent):
    """Agent for extracting enzyme design information from documents.

    The EnzymeDesignAgent processes various document types (text, HTML, PDF)
    to extract enzyme design steps and related information using NLP parsing.

    Attributes:
        agent_id: Unique identifier for this agent instance.
        memory_manager: Manager for persistent storage and messaging.
        tool_registry: Registry of available tools.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
    ) -> None:
        super().__init__(
            agent_id,
            memory_manager,
            tool_registry,
            [
                CAPABILITY_ENZYME_DESIGN_EXTRACTION,
                CAPABILITY_NLP_PARSING,
                CAPABILITY_PDF_HTML_TEXT_SUPPORT,
            ],
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract enzyme design information from a document.

        Args:
            task: Task dictionary containing a 'document' field with keys:
                - source_type: Type of document ("text", "html", "pdf")
                - content: Direct text content (for text source type)
                - path: File path (for file-based source types)
                - url: URL (for web-based source types)

        Returns:
            Dictionary with status and extracted data.
        """
        await self.update_status(STATUS_WORKING)

        doc = task.get("document", {})
        source_type = (doc.get("source_type") or SOURCE_TYPE_DEFAULT).lower()
        loaded = await self._load_document(doc, source_type)

        if loaded.get("status") != STATUS_SUCCESS:
            await self.update_status(STATUS_IDLE)
            return {"status": STATUS_ERROR, "error": loaded.get("error", "load_failed")}

        text = loaded["data"].get("text", "")
        result = self._extract_content(text, source_type)
        result["annotations_zh"] = ANNOTATIONS_ZH

        await self.update_status(STATUS_IDLE)
        return {"status": STATUS_SUCCESS, "data": result}

    async def _load_document(self, doc: Dict[str, Any],
                             source_type: str) -> Dict[str, Any]:
        """Load document content using appropriate method.

        Args:
            doc: Document dictionary with content/path/url.
            source_type: Type of document source.

        Returns:
            Dictionary with status and data fields.
        """
        if source_type == SOURCE_TYPE_TEXT:
            content = doc.get("content") or ""
            return {"status": STATUS_SUCCESS, "data": {"text": content}}

        res = await self.tools.execute_tool(
            TOOL_DOCUMENT_LOADER,
            {
                "source_type": source_type,
                "content": doc.get("content"),
                "path": doc.get("path"),
                "url": doc.get("url"),
            },
        )
        return res.model_dump()

    def _extract_content(self, text: str, source_type: str) -> Dict[str, Any]:
        """Extract enzyme design information from text.

        Args:
            text: Document text content.
            source_type: Type of document source.

        Returns:
            Extracted information dictionary.
        """
        if source_type == SOURCE_TYPE_HTML:
            return extract_from_html(text)
        return extract_steps(text)
