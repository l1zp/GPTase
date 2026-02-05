"""Vision Image Analysis Tool.

This tool handles multi-modal interaction with vision models, including:
- Image loading and Base64 encoding
- Multi-modal message construction (image + text)
- Streaming response parsing and usage tracking
"""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


class VisionTool(BaseTool):
    """Tool for analyzing images using multi-modal vision models."""

    def __init__(self):
        super().__init__(
            name="vision_tool",
            description=
            "Encode images and analyze them using vision LLMs. Supports tabular data extraction.",
        )

    async def execute(self,
                      image_info: Dict[str, Any],
                      base_dir: str = "",
                      provider: Any = None,
                      **kwargs) -> ToolResult:
        """Analyze a single image."""
        try:
            if not provider:
                return ToolResult.error("No vision provider supplied.")

            # 1. Resolve and encode image
            image_path_str = image_info.get("image_path", "")
            if not image_path_str:
                return ToolResult.error("Missing image_path")

            image_path = Path(image_path_str)
            if not image_path.is_absolute() and base_dir:
                image_path = Path(base_dir) / image_path

            with open(image_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")

            # 2. Build multi-modal prompt
            prompt = kwargs.get("prompt", "Analyze this image.")
            messages = [{
                "role":
                "user",
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

            # 3. Stream analysis
            response_content = ""
            usage = {}
            async for chunk in provider.generate_stream(messages):
                if chunk.content:
                    response_content += chunk.content
                if chunk.is_complete and chunk.metadata:
                    usage = chunk.metadata.get("usage", {})

            return ToolResult.success({
                "image_number": image_info.get("image_number", ""),
                "content": response_content,
                "usage": usage
            })
        except Exception as e:
            logger.error(f"Vision tool failed: {e}")
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_info": {
                    "type": "object",
                    "description": "Metadata for the image"
                },
                "base_dir": {
                    "type": "string",
                    "description": "Base directory for images"
                },
                "prompt": {
                    "type": "string",
                    "description": "Expert guidance prompt"
                }
            },
            "required": ["image_info"]
        }
