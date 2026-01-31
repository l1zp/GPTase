"""Vision-based Image Analyzer Tool for scientific figures.

This tool uses vision models (e.g., Qwen3-VL, GPT-4V) to analyze
scientific figures and extract tabular data, charts, and other visual
information from image files.
"""

import base64
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.conversations.models import Message as ConversationMessage
from src.conversations.models import MessageRole
from src.core.constants import Timeouts
from src.models.model import Model
from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.prompts import VISION_IMAGE_ANALYSIS_PROMPT_TEMPLATE
from src.tools.tracking_mixin import TrackingMixin

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


class VisionImageAnalyzerTool(BaseTool, TrackingMixin):
    """Tool for analyzing scientific figures using vision models.

    This tool processes image files and extracts structured data including:
    - Tabular data (tables with mutation information, kinetics, etc.)
    - Chart data (plots, graphs, diagrams)
    - Figure descriptions and captions
    - Enzyme variant names and kinetic parameters

    The tool uses vision models through OpenAI-compatible APIs.
    """

    def __init__(
        self,
        model_manager=None,
        model_config=None,
        agent_id=None,
        session_id=None,
        step_id=None,
    ):
        """Initialize VisionImageAnalyzerTool.

        Args:
            model_manager: ModelManager instance for vision model access.
            model_config: Optional model configuration for vision model.
            agent_id: Optional agent ID for session tracking.
            session_id: Optional session ID for session tracking.
            step_id: Optional step ID for workflow step tracking.
        """
        BaseTool.__init__(
            self,
            name="vision_image_analyzer",
            description="Analyze scientific figures using vision models",
            timeout=Timeouts.VISION_ANALYSIS,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)

        # Store model manager and config
        self.model_manager = model_manager
        self.model_config = model_config or (model_manager.default_config
                                             if model_manager else None)

        # Create provider with agent-specific config
        if model_manager and self.model_config:
            self._provider = model_manager.create_provider(self.model_config)
        else:
            self._provider = None

    async def execute(
        self,
        images: List[Dict[str, Any]],
        base_dir: str = "",
        relevant_only: bool = True,
        max_images: Optional[int] = None,
    ) -> ToolResult:
        """Analyze images using vision model.

        Args:
            images: List of image dictionaries with:
                - image_number: Image identifier
                - image_path: Path to image file
                - caption: Figure caption (optional)
                - is_relevant: Whether image is relevant (optional)
                - topics: Related topics (optional)
                - description: Image description (optional)
            base_dir: Base directory for resolving image paths
            relevant_only: Only analyze is_relevant=True images
            max_images: Maximum number of images to analyze

        Returns:
            ToolResult with analysis results or error information.
        """
        try:
            if not images:
                return ToolResult.success({
                    "analysis_results": [],
                    "extracted_tables": [],
                    "total_images": 0,
                    "total_tokens": 0,
                    "message": "No images to analyze"
                })

            # Filter images
            images_to_analyze = self._filter_images(images, relevant_only, max_images)

            if not images_to_analyze:
                return ToolResult.success({
                    "analysis_results": [],
                    "extracted_tables": [],
                    "total_images": 0,
                    "total_tokens": 0,
                    "message": "No relevant images to analyze"
                })

            logger.info(f"Analyzing {len(images_to_analyze)} images with vision model")

            # Analyze each image
            analysis_results = []
            extracted_tables = []
            total_tokens = 0

            for i, img in enumerate(images_to_analyze, 1):
                logger.info(
                    f"[{i}/{len(images_to_analyze)}] Analyzing image "
                    f"#{img.get('image_number', '')}: {img.get('image_path', '')}")

                result = await self._analyze_single_image(img, base_dir)

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

            return ToolResult.success({
                "analysis_results": analysis_results,
                "extracted_tables": extracted_tables,
                "total_images": len(images_to_analyze),
                "total_tokens": total_tokens,
            })

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return ToolResult.error(str(e))

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

    async def _analyze_single_image(
        self,
        image_info: Dict[str, Any],
        base_dir: str,
    ) -> Dict[str, Any]:
        """Analyze a single image using vision model.

        Args:
            image_info: Image dictionary with metadata
            base_dir: Base directory for resolving paths

        Returns:
            Analysis result dictionary with content and usage info
        """
        # Resolve image path
        image_path_str = image_info.get("image_path", "")
        if not image_path_str:
            return {
                "error": "Missing image_path",
                "image_number": image_info.get("image_number", ""),
            }

        # Handle relative paths
        image_path = Path(image_path_str)
        if not image_path.is_absolute() and base_dir:
            image_path = Path(base_dir) / image_path

        # Read and encode image
        try:
            with open(image_path, "rb") as f:
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
            messages = [{
                "role":
                MessageRole.USER.value,
                "content": [{
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }, {
                    "type": "text",
                    "text": prompt
                }]
            }]

            # Use agent-specific provider for vision model
            if not self._provider:
                return {
                    "error": "No vision model provider available",
                    "image_path": str(image_path),
                    "image_number": image_info.get("image_number", ""),
                }

            response_content = ""
            usage = {}

            async for chunk in self._provider.generate_stream(messages):
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
                self.model_config.model_name if self.model_config else "unknown",
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
            }

        except Exception as e:
            logger.error(f"Vision model call failed: {e}", exc_info=True)
            return {
                "error": f"Vision model call failed: {e}",
                "image_path": str(image_path),
                "image_number": image_info.get("image_number", ""),
            }

    def _generate_analysis_prompt(self, image_info: Dict[str, Any]) -> str:
        """Generate analysis prompt for image.

        Args:
            image_info: Image dictionary with metadata

        Returns:
            Analysis prompt string
        """
        # Build optional blocks
        caption_block = ""
        caption = image_info.get("caption", "")
        if caption:
            caption_block = f"\nFigure Caption:\n{caption}"

        topics_block = ""
        topics = image_info.get("analysis", {}).get("topics", [])
        if topics:
            topics_block = f"\nRelated Topics:\n{', '.join(topics)}"

        description_block = ""
        description = image_info.get("analysis", {}).get("description", "")
        if description:
            description_block = f"\nDescription:\n{description}"

        # Format prompt with blocks
        return VISION_IMAGE_ANALYSIS_PROMPT_TEMPLATE.format(
            caption_block=caption_block,
            topics_block=topics_block,
            description_block=description_block,
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "images": {
                    "type": "array",
                    "description": "List of image dictionaries to analyze"
                },
                "base_dir": {
                    "type": "string",
                    "description": "Base directory for resolving image paths"
                },
                "relevant_only": {
                    "type": "boolean",
                    "description": "Only analyze is_relevant=True images"
                },
                "max_images": {
                    "type": "integer",
                    "description": "Maximum number of images to analyze"
                }
            },
            "required": ["images"]
        }
