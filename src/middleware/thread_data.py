"""Thread data management middleware.

This middleware manages thread-level directory structures for organizing
files, outputs, caches, and other data associated with conversation threads.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseMiddleware
from .base import MiddlewareContext

logger = logging.getLogger(__name__)

# Default directory structure for each thread
DEFAULT_STRUCTURE = {
    "uploads": "uploads",
    "outputs": "outputs",
    "cache": "cache",
    "logs": "logs",
}


class ThreadDataMiddleware(BaseMiddleware):
    """Middleware for managing thread-level data directories.

    Creates and manages a directory structure for each thread, providing
    organized storage for uploads, outputs, cache, and other thread-specific
    data. The paths are stored in the context metadata for use by other
    components.

    Directory structure:
        base_dir/
            thread_001/
                uploads/
                outputs/
                cache/
                logs/
            thread_002/
                ...

    Usage:
        middleware = ThreadDataMiddleware(base_dir="data/threads")
        result = await middleware.process(context, data)
        thread_paths = context.metadata.get("thread_paths")
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        structure: Optional[Dict[str, str]] = None,
        auto_create: bool = True,
    ):
        """Initialize ThreadDataMiddleware.

        Args:
            base_dir: Base directory for thread data. Defaults to "data/threads".
            structure: Directory structure mapping. Keys are logical names,
                      values are subdirectory names.
            auto_create: Whether to auto-create directories on access.
        """
        self.base_dir = Path(base_dir or "data/threads")
        self.structure = structure or DEFAULT_STRUCTURE.copy()
        self.auto_create = auto_create
        self._created_threads: Dict[str, Path] = {}

    @property
    def name(self) -> str:
        """Middleware name."""
        return "ThreadDataMiddleware"

    async def process(self, context: MiddlewareContext,
                      data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and set up thread data directory.

        Args:
            context: Middleware context with thread_id.
            data: Data being processed.

        Returns:
            Unmodified data (this middleware only affects context).
        """
        if not context.thread_id:
            logger.warning("No thread_id in context, skipping thread data setup")
            return data

        thread_dir = self._get_or_create_thread_dir(context.thread_id)

        # Build paths dictionary
        thread_paths = {}
        for name, subdir in self.structure.items():
            thread_paths[name] = str(thread_dir / subdir)

        # Store in context metadata
        context.set("thread_paths", thread_paths)
        context.set("thread_dir", str(thread_dir))

        logger.debug(f"Thread data paths set up for thread {context.thread_id}")

        return data

    def _get_or_create_thread_dir(self, thread_id: str) -> Path:
        """Get or create the thread directory.

        Args:
            thread_id: Thread identifier.

        Returns:
            Path to thread directory.
        """
        # Check cache first
        if thread_id in self._created_threads:
            return self._created_threads[thread_id]

        thread_dir = self.base_dir / thread_id

        if self.auto_create and not thread_dir.exists():
            self._create_thread_structure(thread_dir)

        self._created_threads[thread_id] = thread_dir
        return thread_dir

    def _create_thread_structure(self, thread_dir: Path) -> None:
        """Create the directory structure for a thread.

        Args:
            thread_dir: Path to thread directory.
        """
        try:
            thread_dir.mkdir(parents=True, exist_ok=True)

            for subdir in self.structure.values():
                (thread_dir / subdir).mkdir(exist_ok=True)

            logger.info(f"Created thread directory structure: {thread_dir}")
        except Exception as e:
            logger.error(f"Failed to create thread directory {thread_dir}: {e}")
            raise

    def get_thread_dir(self, thread_id: str) -> Optional[Path]:
        """Get the directory path for a thread.

        Args:
            thread_id: Thread identifier.

        Returns:
            Path to thread directory, or None if not created.
        """
        return self._created_threads.get(thread_id)

    def get_path(self, thread_id: str, path_type: str) -> Optional[Path]:
        """Get a specific path within a thread directory.

        Args:
            thread_id: Thread identifier.
            path_type: Key from structure (e.g., "uploads", "outputs").

        Returns:
            Path to the requested directory, or None if not found.
        """
        thread_dir = self.get_thread_dir(thread_id)
        if thread_dir is None:
            return None

        subdir = self.structure.get(path_type)
        if subdir is None:
            return None

        return thread_dir / subdir

    def list_threads(self) -> list:
        """List all thread directories.

        Returns:
            List of thread IDs (directory names).
        """
        if not self.base_dir.exists():
            return []

        return [
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def cleanup_thread(self, thread_id: str) -> bool:
        """Remove a thread directory and all its contents.

        Args:
            thread_id: Thread identifier.

        Returns:
            True if cleanup was successful.
        """
        import shutil

        thread_dir = self._created_threads.get(thread_id)
        if thread_dir is None:
            thread_dir = self.base_dir / thread_id

        if thread_dir and thread_dir.exists():
            try:
                shutil.rmtree(thread_dir)
                self._created_threads.pop(thread_id, None)
                logger.info(f"Cleaned up thread directory: {thread_dir}")
                return True
            except Exception as e:
                logger.error(f"Failed to cleanup thread {thread_id}: {e}")
                return False

        return False

    async def teardown(self) -> None:
        """Clear the thread directory cache."""
        self._created_threads.clear()
        logger.debug("Thread data middleware cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about managed threads.

        Returns:
            Dictionary with thread statistics.
        """
        threads = self.list_threads()
        return {
            "base_dir": str(self.base_dir),
            "total_threads": len(threads),
            "cached_threads": len(self._created_threads),
            "structure": self.structure,
        }
