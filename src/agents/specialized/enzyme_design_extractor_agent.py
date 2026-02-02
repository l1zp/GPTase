"""Enzyme Design Extractor Agent for extracting enzyme design workflows.

This agent uses the EnzymeDesignExtractorTool to extract structured
enzyme design workflow data from scientific literature.
"""

import logging
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.tools.enzyme_design_extractor import EnzymeDesignExtractorTool

logger = logging.getLogger(__name__)

# Document source type
_UNKNOWN_SOURCE_FILE = "inline_text"


class EnzymeDesignExtractorAgent(BaseAgent):
    """Agent for extracting enzyme design workflow data from scientific text.

    This agent delegates to EnzymeDesignExtractorTool to extract:
    - Design objectives and goals
    - Design methodology steps (Planning, Design, Construction, Expression,
      Assay, Optimization)
    - Techniques and parameters used
    - Key constraints and requirements
    - Optimization cycles and improvements
    - Validation approaches and experimental conditions
    - Results and performance metrics

    The agent returns data in a structured JSON format with Chinese annotations.
    """

    AGENT_NAME = "enzyme_design_extractor"

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
    ):
        """Initialize EnzymeDesignExtractorAgent.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: MemoryManager instance.
            tool_registry: ToolRegistry instance.
            model_manager: ModelManager instance for LLM operations.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=[
                "extract_design_workflow",
                "extract_design_objectives",
                "extract_methodology_steps",
                "extract_optimization_cycles",
                "extract_validation_approaches",
            ],
        )
        self.model_manager = model_manager

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process enzyme design workflow extraction task.

        Args:
            task: Task dictionary containing:
                - text: Text content to extract from (required)
                - source_file: Optional source file path
            session_id: Extraction session ID for tracking.
            agent_id: Agent ID for tracking.
            step_id: Session step ID for tracking.

        Returns:
            Dictionary with:
                - status: STATUS_SUCCESS or STATUS_ERROR
                - data: Extraction results with design workflow and metadata
        """
        try:
            # Extract task parameters
            text = task.get("text", "")
            source_file = task.get("source_file", _UNKNOWN_SOURCE_FILE)

            if not text:
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": "No text provided for extraction"
                    },
                }

            logger.info(f"Extracting enzyme design workflow from: {source_file}")

            # Create tool with tracking
            extractor = EnzymeDesignExtractorTool(
                model_manager=self.model_manager,
                agent_id=agent_id or self.agent_id,
                session_id=session_id,
                step_id=step_id,
            )

            # Delegate to tool
            result = await extractor.execute(text=text, source_file=source_file)

            if result.status == "error":
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": result.error
                    },
                }

            # Return success with data
            return {
                "status": STATUS_SUCCESS,
                "data": result.data,
            }

        except Exception as e:
            logger.error(f"Enzyme design extraction failed: {e}", exc_info=True)
            return {
                "status": STATUS_ERROR,
                "data": {
                    "error": str(e)
                },
            }
