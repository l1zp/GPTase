"""Vision Image Analysis Functions.

Simple, thin functions for multi-modal image analysis.
These can be referenced in MD tool definitions for inline registration.
"""

import base64
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def analyze_image(
    image_info: Dict[str, Any],
    base_dir: str = "",
    prompt: str = "Analyze this image.",
    provider: Any = None,
) -> Dict[str, Any]:
    """Analyze a single image using vision model.

    Args:
        image_info: Dict with 'image_path' and optionally 'image_number'.
        base_dir: Base directory for relative image paths.
        prompt: Analysis prompt for the vision model.
        provider: Vision model provider with generate_stream method.

    Returns:
        Dict with 'image_number', 'content', and 'usage'.
    """
    if not provider:
        raise ValueError("No vision provider supplied")

    # Resolve and encode image
    image_path_str = image_info.get("image_path", "")
    if not image_path_str:
        raise ValueError("Missing image_path in image_info")

    image_path = Path(image_path_str)
    if not image_path.is_absolute() and base_dir:
        image_path = Path(base_dir) / image_path

    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")

    # Build multi-modal message
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

    # Stream analysis
    response_content = ""
    usage = {}
    async for chunk in provider.generate_stream(messages):
        if chunk.content:
            response_content += chunk.content
        if chunk.is_complete and chunk.metadata:
            usage = chunk.metadata.get("usage", {})

    return {
        "image_number": image_info.get("image_number", ""),
        "content": response_content,
        "usage": usage
    }
