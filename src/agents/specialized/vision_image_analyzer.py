"""Vision-based Image Analyzer Agent for scientific figures.

This agent uses the VisionImageAnalyzerTool to analyze scientific figures
and extract tabular data, charts, and other visual information from image files.
"""

import logging
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.tools.vision_image_analyzer import VisionImageAnalyzerTool

logger = logging.getLogger(__name__)


class VisionImageAnalyzerAgent(BaseAgent):
    """Agent for analyzing scientific figures using vision models.

    This agent delegates to VisionImageAnalyzerTool to process:
    - Tabular data (tables with mutation information, kinetics, etc.)
    - Chart data (plots, graphs, diagrams)
    - Figure descriptions and captions
    - Enzyme variant names and kinetic parameters

    The agent uses vision models through OpenAI-compatible APIs.
    """

    AGENT_NAME = "vision_image_analyzer"  # Agent name for model config lookup

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
    ):
        """Initialize VisionImageAnalyzerAgent.

        Args:
            agent_id: Unique identifier for this agent
            memory_manager: MemoryManager instance
            tool_registry: ToolRegistry instance
            model_manager: ModelManager instance for vision model access
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=[
                "analyze_scientific_figures",
                "extract_tabular_data",
                "extract_chart_data",
                "generate_figure_descriptions",
            ],
        )

        # Get agent-specific model configuration
        self.model_config = model_manager.get_config_for_agent(
            self.AGENT_NAME, default_config=model_manager.default_config)

        # Store model_manager for tool creation
        self.model_manager = model_manager

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process image analysis task.

        Args:
            task: Task dictionary containing:
                - images: List of image dictionaries with:
                    - image_number: Image identifier
                    - image_path: Path to image file
                    - caption: Figure caption (optional)
                    - is_relevant: Whether image is relevant (optional)
                    - topics: Related topics (optional)
                    - description: Image description (optional)
                - base_dir: Base directory for resolving image paths
                - relevant_only: Only analyze is_relevant=True images (default: True)
                - max_images: Maximum number of images to analyze (optional)
            session_id: Extraction session ID for tracking
            agent_id: Agent ID for tracking
            step_id: Session step ID for tracking

        Returns:
            Dictionary with:
                - status: STATUS_SUCCESS or STATUS_ERROR
                - data:
                    - analysis_results: List of vision analysis outputs
                    - extracted_tables: List of CSV data extracted from images
                    - total_images: Total images processed
                    - total_tokens: Total tokens used
        """
        try:
            images = task.get("images", [])
            base_dir = task.get("base_dir", "")
            relevant_only = task.get("relevant_only", True)
            max_images = task.get("max_images")

            if not images:
                return {
                    "status": STATUS_SUCCESS,
                    "data": {
                        "analysis_results": [],
                        "extracted_tables": [],
                        "total_images": 0,
                        "total_tokens": 0,
                        "message": "No images to analyze"
                    }
                }

            logger.info(f"Processing {len(images)} images for vision analysis")

            # Create tool with tracking and agent-specific config
            analyzer = VisionImageAnalyzerTool(
                model_manager=self.model_manager,
                model_config=self.model_config,
                agent_id=agent_id or self.agent_id,
                session_id=session_id,
                step_id=step_id,
            )

            # Delegate to tool
            result = await analyzer.execute(
                images=images,
                base_dir=base_dir,
                relevant_only=relevant_only,
                max_images=max_images,
            )

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
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return {
                "status": STATUS_ERROR,
                "data": {
                    "error": str(e)
                },
            }

    async def shutdown(self):
        """Cleanup resources when shutting down."""
        # Tool manages its own resources, nothing to clean up here
        pass
