"""Vision-based Image Analyzer Agent for scientific figures.

This agent uses vision models (e.g., Qwen3-VL, GPT-4V) to analyze
scientific figures and extract tabular data, charts, and other visual
information from image files.
"""

import base64
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.conversations.models import Message as ConversationMessage
from src.conversations.models import MessageRole
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.models.model import Model
from src.models.types import ModelRole

logger = logging.getLogger(__name__)


def _extract_csv_from_content(content: str) -> str:
    """Extract CSV data from markdown code blocks.

    Args:
        content: Analysis content that may contain CSV in code blocks

    Returns:
        CSV string if found, empty string otherwise
    """
    # Look for CSV code blocks: ```csv ... ```
    pattern = r'```csv\s*\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)

    if matches:
        return matches[0]
    return ""


class VisionImageAnalyzerAgent(BaseAgent):
    """Agent for analyzing scientific figures using vision models.

    This agent processes image files and extracts structured data including:
    - Tabular data (tables with mutation information, kinetics, etc.)
    - Chart data (plots, graphs, diagrams)
    - Figure descriptions and captions
    - Enzyme variant names and kinetic parameters

    The agent uses vision models through OpenAI-compatible APIs.
    """

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
            capabilities=[
                "analyze_scientific_figures",
                "extract_tabular_data",
                "extract_chart_data",
                "generate_figure_descriptions",
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

            # Filter images
            images_to_analyze = self._filter_images(images, relevant_only, max_images)

            if not images_to_analyze:
                return {
                    "status": STATUS_SUCCESS,
                    "data": {
                        "analysis_results": [],
                        "extracted_tables": [],
                        "total_images": 0,
                        "total_tokens": 0,
                        "message": "No relevant images to analyze"
                    }
                }

            logger.info(f"Analyzing {len(images_to_analyze)} images with vision model")

            # Analyze each image
            analysis_results = []
            extracted_tables = []
            total_tokens = 0

            for i, img in enumerate(images_to_analyze, 1):
                logger.info(
                    f"[{i}/{len(images_to_analyze)}] Analyzing image "
                    f"#{img.get('image_number', '')}: {img.get('image_path', '')}")

                result = await self._analyze_single_image(img, base_dir, session_id,
                                                          agent_id, step_id)

                if "error" in result:
                    logger.warning(f"  [ERROR] {result['error']}")
                    analysis_results.append(result)
                else:
                    logger.info(
                        f"  [OK] Success - "
                        f"Tokens: {result.get('usage', {}).get('total_tokens', 0)}")
                    analysis_results.append(result)
                    total_tokens += result.get("usage", {}).get("total_tokens", 0)

                    # Extract CSV if present
                    csv_data = _extract_csv_from_content(result.get("content", ""))
                    if csv_data:
                        logger.info(f"  [CSV] Table data extracted")
                        extracted_tables.append({
                            "image_number":
                            img.get("image_number", ""),
                            "image_path":
                            img.get("image_path", ""),
                            "csv_data":
                            csv_data
                        })

            logger.info(f"Vision analysis complete: {len(analysis_results)} images, "
                        f"{len(extracted_tables)} tables extracted, "
                        f"{total_tokens} total tokens")

            return {
                "status": STATUS_SUCCESS,
                "data": {
                    "analysis_results": analysis_results,
                    "extracted_tables": extracted_tables,
                    "total_images": len(images_to_analyze),
                    "total_tokens": total_tokens,
                }
            }

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return {"status": STATUS_ERROR, "data": {"error": str(e)}}

    def _filter_images(self, images: List[Dict[str, Any]], relevant_only: bool,
                       max_images: Optional[int]) -> List[Dict[str, Any]]:
        """Filter images based on relevance and count.

        Args:
            images: List of image dictionaries
            relevant_only: Only include is_relevant=True images
            max_images: Maximum number of images to return

        Returns:
            Filtered list of images
        """
        filtered = images

        if relevant_only:
            filtered = [
                img for img in filtered
                if img.get("analysis", {}).get("is_relevant", False)
            ]

        if max_images:
            filtered = filtered[:max_images]

        return filtered

    async def _analyze_single_image(self,
                                    image_info: Dict[str, Any],
                                    base_dir: str,
                                    session_id: Optional[str] = None,
                                    agent_id: Optional[str] = None,
                                    step_id: Optional[str] = None) -> Dict[str, Any]:
        """Analyze a single image using vision model.

        Args:
            image_info: Image dictionary with metadata
            base_dir: Base directory for resolving paths
            session_id: Session ID for tracking
            agent_id: Agent ID for tracking
            step_id: Step ID for tracking

        Returns:
            Analysis result dictionary
        """
        # Extract image path
        image_path = image_info.get("image_path", "")
        if image_path.startswith("![]("):
            image_path = image_path[4:-1]

        full_path = Path(base_dir) / image_path

        if not full_path.exists():
            return {
                "error": f"Image file not found: {full_path}",
                "image_path": str(image_path),
                "image_number": image_info.get("image_number", ""),
            }

        # Encode image to base64
        try:
            with open(full_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return {
                "error": f"Failed to read image: {e}",
                "image_path": str(image_path),
                "image_number": image_info.get("image_number", ""),
            }

        # Generate prompt
        prompt = self._generate_analysis_prompt(image_info)

        # Call vision model
        try:
            messages = [
                ConversationMessage(role=MessageRole.USER,
                                    content=[{
                                        "type": "image_url",
                                        "image_url": {
                                            "url":
                                            f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }, {
                                        "type": "text",
                                        "text": prompt
                                    }])
            ]

            # Use general role for vision (model_roles not yet supported in config)
            response_content = ""
            usage = {}

            async for chunk in self.model_manager.generate_stream(
                    messages=messages, role=ModelRole.GENERAL):
                if chunk.content:
                    response_content += chunk.content
                if chunk.is_complete and chunk.metadata:
                    usage = chunk.metadata.get("usage", {})

            return {
                "image_path": str(image_path),
                "image_number": image_info.get("image_number", ""),
                "prompt": prompt,
                "content": response_content,
                "model":
                self.model_manager.get_role_config(ModelRole.GENERAL).model_name,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
            }

        except Exception as e:
            logger.error(f"Vision model call failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "image_path": str(image_path),
                "image_number": image_info.get("image_number", ""),
            }

    def _generate_analysis_prompt(self, image_info: Dict[str, Any]) -> str:
        """Generate analysis prompt for scientific figures.

        Args:
            image_info: Image dictionary with metadata

        Returns:
            Analysis prompt string
        """
        prompt_parts = [
            "Please analyze this scientific figure in detail and extract the following information:",
        ]

        # Add caption if available
        caption = image_info.get("caption", "")
        if caption:
            prompt_parts.append(f"\nFigure Caption:\n{caption}")

        # Add topics if available
        topics = image_info.get("analysis", {}).get("topics", [])
        if topics:
            prompt_parts.append(f"\nRelated Topics:\n{', '.join(topics)}")

        # Add description if available
        description = image_info.get("analysis", {}).get("description", "")
        if description:
            prompt_parts.append(f"\nDescription:\n{description}")

        prompt_parts.extend([
            "\nPlease extract and provide structured output for:",
            "1. **Figure Type** (e.g., flowchart, data plot, structural diagram, table, etc.)",
            "2. **Main Content and Key Elements**",
            "3. **Data Information** (if the figure contains data tables or plots, extract ALL numerical values)",
            "4. **Experimental Methods or Technical Details**",
            "5. **Conclusions or Key Findings**",
            "6. **Enzyme Variant Names** (if mentioned)",
            "7. **Kinetic Parameters** (if available, such as kcat, KM, kcat/KM, Tm, Vmax, etc.)",
            "8. **PDB IDs** (if mentioned)",
            "",
            "**IMPORTANT - For table or data chart images:**",
            "- If the figure is a TABLE or contains TABULAR DATA, you MUST output the data in CSV format",
            "- Format the CSV as a code block with ```csv ... ```",
            "- Include column headers and all data rows",
            "- Preserve numerical values with units (e.g., '1.5 +/- 0.2', 'n.d.', 'n.c.')",
            "- If the table contains enzyme variants and kinetic parameters, ensure each variant is a separate row",
            "",
            "Example CSV format for enzyme kinetics:",
            "```csv",
            "Variant,kcat (s^-1),KM (mM),kcat/KM (M^-1s^-1),Tm (C)",
            "Des27,1.2,0.5,2400,55",
            "Des27.7,3.5,0.3,11667,60",
            "```",
            "",
            "**For tables with amino acid substitutions:**",
            "- Include columns for EACH mutation position shown in the table",
            "- Use single-letter amino acid codes (e.g., H, F, L, W, V)",
        ])

        return "\n".join(prompt_parts)

    async def shutdown(self):
        """Cleanup resources when shutting down."""
        if self.model_manager:
            await self.model_manager.close()
