"""LLM-driven Enzyme Reaction Extractor (Orchestrator).

This agent coordinates multiple specialized agents to extract enzyme reaction
data from scientific literature:

Phase 1: DocumentStructureAnalyzerAgent - Analyze document structure
Phase 2.1: EnzymeKineticsExtractorAgent - Extract kinetics data
Phase 2.2: VisionImageAnalyzerAgent - Analyze figures (optional)
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.agents.specialized.document_structure_agent import \
    DocumentStructureAnalyzerAgent
from src.agents.specialized.enzyme_kinetics_extractor_agent import \
    EnzymeKineticsExtractorAgent
from src.agents.specialized.vision_image_analyzer import VisionImageAnalyzerAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.tools.document_structure_analyzer import get_relevant_content_for_extraction

logger = logging.getLogger(__name__)


class LLMEnzymeExtractorAgent(BaseAgent):
    """Orchestrator agent for coordinating enzyme reaction extraction.

    This agent manages a multi-phase extraction pipeline:
    1. Document structure analysis
    2. Parallel execution of:
       - Main kinetics extraction
       - Optional vision-based figure analysis

    The agent coordinates specialized agents and merges their results.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
        enable_vision_analysis: bool = False,
    ):
        """Initialize the LLMEnzymeExtractorAgent orchestrator.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: Manager for agent memory and message passing.
            tool_registry: Registry of available tools.
            model_manager: Model instance for LLM operations.
            enable_vision_analysis: Whether to enable vision-based image analysis.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=["orchestrate_enzyme_extraction"],
        )

        self.model_manager = model_manager
        self.enable_vision_analysis = enable_vision_analysis

        # Lazy initialization of child agents
        self.structure_agent = None
        self.kinetics_agent = None
        self.vision_agent = None

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process an enzyme extraction task by coordinating child agents.

        Args:
            task: Dictionary containing document information with optional
                  source_type, content, path, or url fields.

        Returns:
            Dictionary with status and extraction data, or error information.
        """
        from src.conversations.models import ExtractionSessionStatus
        from src.conversations.models import ExtractionStepStatus
        from src.conversations.storage import ConversationStorage

        # Initialize storage if tracking is enabled
        storage = None
        session_id = "tracking_disabled"
        if self.model_manager.enable_tracking and self.model_manager.tracking_storage:
            storage = self.model_manager.tracking_storage

        # Load document
        load_result = await self._load_document(task)
        if load_result["status"] == "error":
            return load_result

        # Start extraction session
        if storage:
            session_id = await storage.start_extraction_session(
                document_path=load_result["source_file"],
                extraction_type="kinetics",
                agent_id=self.agent_id,
                metadata={"task": task},
            )

        try:
            # Phase 1: Document structure analysis
            if storage:
                await storage.update_session_phase(session_id, "structure_analysis")
                structure_step_id = await storage.start_session_step(
                    session_id=session_id,
                    step_name="structure_analysis",
                    step_phase="phase1_structure",
                    step_order=1,
                    metadata={"description": "Analyze document structure"},
                )

            structure_result = await self._analyze_document_structure(
                load_result["text"],
                load_result["source_file"],
                session_id=session_id,
                step_id=structure_step_id if storage else None,
            )

            if storage:
                await storage.complete_session_step(structure_step_id)

            if structure_result["status"] == "error":
                if storage:
                    await storage.complete_extraction_session(
                        session_id, ExtractionSessionStatus.FAILED)
                return structure_result

            # Prepare for parallel execution
            analysis_data = structure_result.get("data", {})
            images = analysis_data.get("images", [])

            # Start parallel execution of Phase 2.1 and 2.2
            vision_task = None
            extraction_task = None
            vision_step_id = None
            extraction_step_id = None

            # Phase 2.2: Vision analysis (if enabled)
            if self.enable_vision_analysis and images:
                if storage:
                    await storage.update_session_phase(session_id,
                                                       "parallel_processing")
                    vision_step_id = await storage.start_session_step(
                        session_id=session_id,
                        step_name="vision_analysis",
                        step_phase="phase2_vision",
                        step_order=2,
                        metadata={"description": "Analyze figures with vision model"},
                    )

                vision_task = asyncio.create_task(
                    self._analyze_images_with_vision(
                        images=images,
                        base_dir=str(Path(load_result["source_file"]).parent),
                        session_id=session_id,
                        step_id=vision_step_id if storage else None,
                    ))

            # Phase 2.1: Main extraction
            if storage:
                extraction_step_id = await storage.start_session_step(
                    session_id=session_id,
                    step_name="main_extraction",
                    step_phase="phase2_extraction",
                    step_order=1,
                    metadata={"description": "Extract structured kinetics data"},
                )

            extraction_task = asyncio.create_task(
                self._extract_kinetics_data(
                    analysis_data=analysis_data,
                    source_file=load_result["source_file"],
                    session_id=session_id,
                    step_id=extraction_step_id if storage else None,
                ))

            # Run in parallel
            results = await asyncio.gather(
                vision_task if vision_task else asyncio.sleep(0),
                extraction_task,
                return_exceptions=True,
            )

            vision_result = results[0] if vision_task else (None, None)
            extraction_result = results[1]

            # Unpack results
            vision_data, vision_error = vision_result if vision_task else (None, None)
            extraction_data, extraction_error = extraction_result

            # Handle errors
            if extraction_error:
                if storage:
                    await storage.complete_extraction_session(
                        session_id, ExtractionSessionStatus.FAILED)
                return {"status": STATUS_ERROR, "data": {"error": extraction_error}}

            if vision_error:
                logger.warning(f"Vision analysis failed (continuing): {vision_error}")

            # Complete session steps
            if vision_task and storage:
                await storage.complete_session_step(vision_step_id)
            if storage:
                await storage.complete_session_step(extraction_step_id)

            # Merge results
            final_data = extraction_data
            final_data["pipeline"]["document_analysis"] = {
                "total_tables": analysis_data.get("total_tables", 0),
                "key_paragraphs": analysis_data.get("total_key_paragraphs", 0),
                "used_fallback": analysis_data.get("llm_enhanced", False),
            }

            if vision_data and vision_data.get("status") == STATUS_SUCCESS:
                vision_content = vision_data.get("data", {})
                final_data["pipeline"]["vision_analysis"] = {
                    "images_analyzed": vision_content.get("total_images", 0),
                    "tables_extracted": len(vision_content.get("extracted_tables", [])),
                }
                logger.info(
                    f"Vision analysis complete: {vision_content.get('total_images', 0)} images, "
                    f"{len(vision_content.get('extracted_tables', []))} tables")

            # Save extraction results
            if storage:
                import json
                await storage.save_extraction_result(
                    session_id=session_id,
                    result_type="reactions",
                    content=json.dumps(final_data),
                )

            # Complete session
            if storage:
                await storage.complete_extraction_session(
                    session_id, ExtractionSessionStatus.COMPLETED)

            return {
                "status": STATUS_SUCCESS,
                "data": {
                    "extraction": final_data,
                    "session_id": session_id,
                },
            }

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            if storage:
                await storage.complete_extraction_session(
                    session_id, ExtractionSessionStatus.FAILED)
            return {"status": STATUS_ERROR, "data": {"error": str(e)}}

    async def _load_document(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Load document from task parameters.

        Args:
            task: Task dictionary with document information.

        Returns:
            Dictionary with text and source_file, or error.
        """
        from src.tools.implementations import DocumentLoaderTool

        try:
            # Determine source type and load document
            source_type = task.get("document", {}).get("source_type", "file")
            source_path = task.get("document", {}).get("path")
            source_content = task.get("document", {}).get("content")

            if source_type == "text" or source_content:
                text = source_content or task.get("text", "")
                source_file = task.get("source_file", "inline_text")
            elif source_type == "file":
                loader = DocumentLoaderTool()
                result = await loader.execute(source_type="file", path=source_path)
                if result.status == "error":
                    return {"status": "error", "error": result.error}
                text = result.data.get("text", "")
                source_file = source_path
            else:
                return {
                    "status": "error",
                    "error": f"Unsupported source type: {source_type}",
                }

            if not text:
                return {"status": "error", "error": "Empty document content"}

            return {"status": "success", "text": text, "source_file": source_file}

        except Exception as e:
            logger.error(f"Failed to load document: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _get_structure_agent(self) -> DocumentStructureAnalyzerAgent:
        """Get or create document structure analyzer agent."""
        if not self.structure_agent:
            self.structure_agent = DocumentStructureAnalyzerAgent(
                agent_id=f"{self.agent_id}_structure",
                memory_manager=self.memory,
                tool_registry=self.tools,
                model_manager=self.model_manager,
                use_llm_enhancement=True,
            )
        return self.structure_agent

    def _get_kinetics_agent(self) -> EnzymeKineticsExtractorAgent:
        """Get or create enzyme kinetics extractor agent."""
        if not self.kinetics_agent:
            self.kinetics_agent = EnzymeKineticsExtractorAgent(
                agent_id=f"{self.agent_id}_kinetics",
                memory_manager=self.memory,
                tool_registry=self.tools,
                model_manager=self.model_manager,
            )
        return self.kinetics_agent

    def _get_vision_agent(self) -> VisionImageAnalyzerAgent:
        """Get or create vision image analyzer agent."""
        if not self.vision_agent:
            self.vision_agent = VisionImageAnalyzerAgent(
                agent_id=f"{self.agent_id}_vision",
                memory_manager=self.memory,
                tool_registry=self.tools,
                model_manager=self.
                model_manager,  # Use shared model_manager with agent-specific config
            )
        return self.vision_agent

    async def _analyze_document_structure(
        self,
        text: str,
        source_file: str,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze document structure using DocumentStructureAnalyzerAgent.

        Args:
            text: Document text.
            source_file: Source file path.
            session_id: Session ID for tracking.
            step_id: Step ID for tracking.

        Returns:
            Analysis result dictionary.
        """
        agent = self._get_structure_agent()
        return await agent.process_task(
            task={
                "text": text,
                "source_file": source_file
            },
            session_id=session_id,
            agent_id=self.agent_id,
            step_id=step_id,
        )

    async def _extract_kinetics_data(
        self,
        analysis_data: Dict[str, Any],
        source_file: str,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> tuple:
        """Extract kinetics data using EnzymeKineticsExtractorAgent.

        Args:
            analysis_data: Document structure analysis data.
            source_file: Source file path.
            session_id: Session ID for tracking.
            step_id: Step ID for tracking.

        Returns:
            Tuple of (extraction_data, error).
        """
        try:
            # Get relevant content from analysis
            relevant_content = get_relevant_content_for_extraction(analysis_data)

            agent = self._get_kinetics_agent()
            result = await agent.process_task(
                task={
                    "text": relevant_content,
                    "source_file": source_file
                },
                session_id=session_id,
                agent_id=self.agent_id,
                step_id=step_id,
            )

            if result["status"] == STATUS_SUCCESS:
                return result["data"], None
            else:
                return None, result.get("data", {}).get("error", "Extraction failed")

        except Exception as e:
            logger.error(f"Kinetics extraction failed: {e}", exc_info=True)
            return None, str(e)

    async def _analyze_images_with_vision(
        self,
        images: list,
        base_dir: str,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> tuple:
        """Analyze images using VisionImageAnalyzerAgent.

        Args:
            images: List of image dictionaries.
            base_dir: Base directory for image paths.
            session_id: Session ID for tracking.
            step_id: Step ID for tracking.

        Returns:
            Tuple of (result_data, error).
        """
        try:
            agent = self._get_vision_agent()
            result = await agent.process_task(
                task={
                    "images": images,
                    "base_dir": base_dir,
                    "relevant_only": True,
                },
                session_id=session_id,
                agent_id=self.agent_id,
                step_id=step_id,
            )

            if result["status"] == STATUS_SUCCESS:
                return result, None
            else:
                return None, result.get("data", {}).get("error",
                                                        "Vision analysis failed")

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return None, str(e)

    async def shutdown(self):
        """Cleanup resources when shutting down."""
        # Shutdown child agents if they own their ModelManagers
        if self.vision_agent:
            await self.vision_agent.shutdown()
        # Note: structure_agent and kinetics_agent share our model_manager,
        # so we don't shut them down separately
