"""Title generation middleware.

This middleware auto-generates titles for conversation threads based on
the first message or task description.
"""

import hashlib
import logging
from typing import Any, Dict, Optional

from .base import BaseMiddleware
from .base import MiddlewareContext

logger = logging.getLogger(__name__)

# Default title length limits
DEFAULT_MAX_TITLE_LENGTH = 50
DEFAULT_MIN_TITLE_LENGTH = 3


class TitleMiddleware(BaseMiddleware):
    """Middleware for auto-generating thread titles.

    Generates a title for a thread based on the first message or task
    description. The title is stored in the context metadata and can be
    used by other components (e.g., for display or storage).

    Title generation strategy:
    1. If a title is already set, keep it
    2. If description/message is available, use first meaningful line
    3. Otherwise, generate a title based on thread_id

    Usage:
        middleware = TitleMiddleware()
        result = await middleware.process(context, {"description": "My task"})
        title = context.metadata.get("thread_title")
    """

    def __init__(
        self,
        max_length: int = DEFAULT_MAX_TITLE_LENGTH,
        min_length: int = DEFAULT_MIN_TITLE_LENGTH,
        llm_enabled: bool = False,
        model_manager=None,
    ):
        """Initialize TitleMiddleware.

        Args:
            max_length: Maximum title length in characters.
            min_length: Minimum title length (titles shorter than this
                       will be extended or regenerated).
            llm_enabled: Whether to use LLM for title generation.
            model_manager: ModelManager instance for LLM-based generation.
        """
        self.max_length = max_length
        self.min_length = min_length
        self.llm_enabled = llm_enabled
        self.model_manager = model_manager
        self._titles: Dict[str, str] = {}

    @property
    def name(self) -> str:
        """Middleware name."""
        return "TitleMiddleware"

    async def process(self, context: MiddlewareContext,
                      data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and generate thread title.

        Args:
            context: Middleware context with thread_id.
            data: Data being processed (may contain description/message).

        Returns:
            Unmodified data (this middleware only affects context).
        """
        if not context.thread_id:
            return data

        # Skip if title already exists
        if context.thread_id in self._titles:
            context.set("thread_title", self._titles[context.thread_id])
            return data

        # Generate title
        title = await self._generate_title(context, data)

        # Store in cache and context
        self._titles[context.thread_id] = title
        context.set("thread_title", title)

        logger.debug(f"Generated title for thread {context.thread_id}: {title}")

        return data

    async def _generate_title(self, context: MiddlewareContext, data: Dict[str,
                                                                           Any]) -> str:
        """Generate a title for the thread.

        Args:
            context: Middleware context.
            data: Data being processed.

        Returns:
            Generated title string.
        """
        # Try LLM-based generation first if enabled
        if self.llm_enabled and self.model_manager:
            title = await self._generate_title_with_llm(context, data)
            if title:
                return self._normalize_title(title)

        # Try to extract from description/message
        description = data.get("description") or data.get("message") or data.get(
            "task_description") or ""

        if description:
            return self._extract_title_from_text(description)

        # Fallback: generate from thread_id
        return self._generate_title_from_thread_id(context.thread_id)

    async def _generate_title_with_llm(self, context: MiddlewareContext,
                                       data: Dict[str, Any]) -> Optional[str]:
        """Generate title using LLM.

        Args:
            context: Middleware context.
            data: Data being processed.

        Returns:
            Generated title or None if generation failed.
        """
        try:
            description = data.get("description") or data.get("message") or data.get(
                "task_description") or ""

            if not description:
                return None

            prompt = f"""Generate a concise title (max {self.max_length} chars) for this conversation:
{description[:500]}

Return only the title, nothing else."""

            response = await self.model_manager.generate(
                prompt,
                max_tokens=50,
                temperature=0.3,
            )

            if response and response.strip():
                return response.strip()

        except Exception as e:
            logger.warning(f"LLM title generation failed: {e}")

        return None

    def _extract_title_from_text(self, text: str) -> str:
        """Extract a title from text content.

        Uses heuristics to find a meaningful first line or sentence.

        Args:
            text: Text to extract title from.

        Returns:
            Extracted title.
        """
        # Get first non-empty line
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if not lines:
            return "Untitled"

        first_line = lines[0]

        # If it's a question, use it directly
        if "?" in first_line:
            return self._normalize_title(first_line)

        # Try to get first sentence
        for end_char in [".", "!", "?"]:
            if end_char in first_line:
                sentence = first_line.split(end_char)[0] + end_char
                return self._normalize_title(sentence)

        # Use first line directly
        return self._normalize_title(first_line)

    def _generate_title_from_thread_id(self, thread_id: str) -> str:
        """Generate a title from thread_id.

        Args:
            thread_id: Thread identifier.

        Returns:
            Generated title.
        """
        # Create a short hash for uniqueness
        hash_part = hashlib.md5(thread_id.encode()).hexdigest()[:6]
        return f"Thread {hash_part}"

    def _normalize_title(self, title: str) -> str:
        """Normalize title to meet length requirements.

        Args:
            title: Raw title string.

        Returns:
            Normalized title.
        """
        # Clean up whitespace
        title = " ".join(title.split())

        # Truncate if too long
        if len(title) > self.max_length:
            title = title[:self.max_length - 3] + "..."

        # Ensure minimum length
        if len(title) < self.min_length:
            title = title + "..." if len(title) + 3 >= self.min_length else "Untitled"

        return title

    def get_title(self, thread_id: str) -> Optional[str]:
        """Get cached title for a thread.

        Args:
            thread_id: Thread identifier.

        Returns:
            Cached title or None if not found.
        """
        return self._titles.get(thread_id)

    def set_title(self, thread_id: str, title: str) -> None:
        """Set title for a thread manually.

        Args:
            thread_id: Thread identifier.
            title: Title to set.
        """
        self._titles[thread_id] = self._normalize_title(title)

    def clear_title(self, thread_id: str) -> bool:
        """Clear cached title for a thread.

        Args:
            thread_id: Thread identifier.

        Returns:
            True if title was cleared, False if not found.
        """
        if thread_id in self._titles:
            del self._titles[thread_id]
            return True
        return False

    async def teardown(self) -> None:
        """Clear the title cache."""
        self._titles.clear()
        logger.debug("Title middleware cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about cached titles.

        Returns:
            Dictionary with title statistics.
        """
        return {
            "total_titles": len(self._titles),
            "llm_enabled": self.llm_enabled,
            "max_length": self.max_length,
            "min_length": self.min_length,
        }
