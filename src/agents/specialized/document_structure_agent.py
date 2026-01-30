"""Document Structure Analyzer Agent for analyzing document structure.

This agent analyzes scientific literature documents to identify:
- Markdown and HTML tables
- Key sections containing enzyme reaction data
- Important paragraphs with experimental details
- Images with captions for vision analysis
"""

import logging
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.tools.document_structure_analyzer import DocumentStructureAnalyzer

logger = logging.getLogger(__name__)


class DocumentStructureAnalyzerAgent(BaseAgent):
    """Agent for analyzing document structure and locating relevant sections.

    This agent processes scientific documents to intelligently identify:
    - Tables containing enzyme reaction data
    - Key paragraphs with experimental information
    - Images with captions for potential vision analysis

    The agent can operate in two modes:
    1. Basic mode: Rule-based table and paragraph extraction
    2. LLM-enhanced mode: Uses LLM to classify tables and identify key content
    """

    AGENT_NAME = "document_structure_analyzer"

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
        use_llm_enhancement: bool = True,
    ):
        """Initialize DocumentStructureAnalyzerAgent.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: MemoryManager instance for agent memory.
            tool_registry: ToolRegistry instance for tool access.
            model_manager: ModelManager instance for LLM operations.
            use_llm_enhancement: Whether to use LLM for enhanced analysis.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=[
                "analyze_document_structure",
                "extract_tables",
                "identify_key_paragraphs",
                "locate_images",
            ],
        )

        self.model_manager = model_manager
        self.use_llm_enhancement = use_llm_enhancement

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process document structure analysis task.

        Args:
            task: Task dictionary containing:
                - text: Full document text to analyze (required)
                - source_file: Optional source file path
                - use_llm_enhancement: Override default LLM enhancement setting
            session_id: Extraction session ID for tracking.
            agent_id: Agent ID for tracking.
            step_id: Session step ID for tracking.

        Returns:
            Dictionary with:
                - status: STATUS_SUCCESS or STATUS_ERROR
                - data:
                    - source_file: Source file path
                    - sections: List of document sections
                    - tables: List of tables found
                    - key_paragraphs: List of key paragraphs
                    - images: List of images with metadata
                    - total_tables: Count of tables
                    - total_key_paragraphs: Count of key paragraphs
                    - total_images: Count of images
                    - llm_enhanced: Whether LLM enhancement was used
        """
        try:
            # Extract task parameters
            text = task.get("text", "")
            source_file = task.get("source_file")
            use_llm = task.get("use_llm_enhancement", self.use_llm_enhancement)

            if not text:
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": "No text provided for analysis"
                    },
                }

            logger.info(f"Analyzing document structure (LLM enhanced: {use_llm}, "
                        f"text length: {len(text)} chars)")

            # Create analyzer tool
            analyzer = DocumentStructureAnalyzer(
                model_manager=self.model_manager if use_llm else None,
                use_llm_enhancement=use_llm,
                agent_id=agent_id or self.agent_id,
                session_id=session_id,
                step_id=step_id,
            )

            # Execute analysis
            result = await analyzer.execute(text=text, source_file=source_file)

            if result.status == "error":
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": result.error
                    },
                }

            # Extract data from tool result
            analysis_data = result.data

            logger.info(
                f"Document analysis complete: {analysis_data.get('total_tables', 0)} tables, "
                f"{analysis_data.get('total_key_paragraphs', 0)} key paragraphs, "
                f"{analysis_data.get('total_images', 0)} images")

            return {
                "status": STATUS_SUCCESS,
                "data": analysis_data,
            }

        except Exception as e:
            logger.error(f"Document structure analysis failed: {e}", exc_info=True)
            return {
                "status": STATUS_ERROR,
                "data": {
                    "error": str(e)
                },
            }
