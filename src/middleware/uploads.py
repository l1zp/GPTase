"""File uploads management middleware.

This middleware tracks and manages file uploads associated with threads,
including file validation, organization, and metadata extraction.
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from .base import BaseMiddleware
from .base import MiddlewareContext

logger = logging.getLogger(__name__)

# Supported file extensions with their categories
FILE_CATEGORIES = {
    # Documents
    "pdf": "document",
    "doc": "document",
    "docx": "document",
    "txt": "document",
    "md": "document",
    "html": "document",
    # Images
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "gif": "image",
    "svg": "image",
    "webp": "image",
    # Data
    "csv": "data",
    "json": "data",
    "xml": "data",
    "xlsx": "data",
    "xls": "data",
    # Code
    "py": "code",
    "js": "code",
    "ts": "code",
    "java": "code",
    "cpp": "code",
    "c": "code",
    # Archives
    "zip": "archive",
    "tar": "archive",
    "gz": "archive",
    "rar": "archive",
}

# Max file size in bytes (default: 50MB)
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


@dataclass
class FileInfo:
    """Information about an uploaded file.

    Attributes:
        filename: Original filename.
        path: Path where file is stored.
        size: File size in bytes.
        category: File category (document, image, data, etc.).
        content_type: MIME content type.
        hash: MD5 hash of file content.
        uploaded_at: Upload timestamp.
        metadata: Additional file metadata.
    """

    filename: str
    path: str
    size: int
    category: str
    content_type: str = "application/octet-stream"
    hash: str = ""
    uploaded_at: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if not self.uploaded_at:
            self.uploaded_at = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filename": self.filename,
            "path": self.path,
            "size": self.size,
            "category": self.category,
            "content_type": self.content_type,
            "hash": self.hash,
            "uploaded_at": self.uploaded_at,
            "metadata": self.metadata,
        }


class UploadsMiddleware(BaseMiddleware):
    """Middleware for managing file uploads.

    Tracks files uploaded to threads, validates them, and organizes
    them into the appropriate directories. File information is stored
    in the context metadata for use by other components.

    Features:
    - File type validation
    - Size limits
    - Automatic categorization
    - Content hashing for deduplication
    - Metadata extraction

    Usage:
        middleware = UploadsMiddleware(max_file_size=10*1024*1024)
        result = await middleware.process(context, {
            "files": [
                {"path": "/tmp/upload.pdf", "filename": "document.pdf"}
            ]
        })
        uploads = context.metadata.get("processed_uploads")
    """

    def __init__(
        self,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        allowed_extensions: Optional[List[str]] = None,
        blocked_extensions: Optional[List[str]] = None,
        auto_move: bool = True,
    ):
        """Initialize UploadsMiddleware.

        Args:
            max_file_size: Maximum file size in bytes.
            allowed_extensions: List of allowed extensions (None = all allowed).
            blocked_extensions: List of blocked extensions.
            auto_move: Whether to automatically move files to uploads directory.
        """
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions
        self.blocked_extensions = blocked_extensions or ["exe", "bat", "sh", "cmd"]
        self.auto_move = auto_move
        self._uploads: Dict[str, List[FileInfo]] = {}

    @property
    def name(self) -> str:
        """Middleware name."""
        return "UploadsMiddleware"

    async def process(self, context: MiddlewareContext,
                      data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and track file uploads.

        Args:
            context: Middleware context with thread_id and thread_paths.
            data: Data being processed (may contain files).

        Returns:
            Modified data with processed_files if files were present.
        """
        if not context.thread_id:
            return data

        files = data.get("files", [])
        if not files:
            return data

        # Get uploads directory from context (set by ThreadDataMiddleware)
        thread_paths = context.get("thread_paths", {})
        uploads_dir = thread_paths.get("uploads")

        processed_files = []
        errors = []

        for file_info in files:
            try:
                result = await self._process_file(file_info, uploads_dir, context)
                if result:
                    processed_files.append(result)
            except Exception as e:
                errors.append({
                    "file": file_info.get("filename", "unknown"),
                    "error": str(e),
                })
                logger.warning(f"File processing error: {e}")

        # Store results
        if processed_files:
            self._uploads[context.thread_id] = processed_files
            context.set("processed_uploads", [f.to_dict() for f in processed_files])

        if errors:
            context.set("upload_errors", errors)

        # Return modified data
        result = data.copy()
        if processed_files:
            result["processed_files"] = [f.to_dict() for f in processed_files]

        return result

    async def _process_file(
        self,
        file_info: Dict[str, Any],
        uploads_dir: Optional[str],
        context: MiddlewareContext,
    ) -> Optional[FileInfo]:
        """Process a single file.

        Args:
            file_info: File information dictionary.
            uploads_dir: Target uploads directory.
            context: Middleware context.

        Returns:
            FileInfo if processing successful, None otherwise.
        """
        source_path = file_info.get("path")
        filename = file_info.get(
            "filename",
            os.path.basename(source_path) if source_path else "unknown")

        if not source_path or not os.path.exists(source_path):
            raise ValueError(f"File not found: {source_path}")

        # Validate file
        self._validate_file(source_path, filename)

        # Get file info
        file_size = os.path.getsize(source_path)
        file_ext = os.path.splitext(filename)[1].lower().lstrip(".")
        category = FILE_CATEGORIES.get(file_ext, "other")

        # Calculate hash
        file_hash = self._calculate_hash(source_path)

        # Determine target path
        if self.auto_move and uploads_dir:
            target_path = self._get_target_path(uploads_dir, filename, file_hash)
            shutil.copy2(source_path, target_path)
        else:
            target_path = source_path

        # Create FileInfo
        return FileInfo(
            filename=filename,
            path=target_path,
            size=file_size,
            category=category,
            content_type=self._get_content_type(file_ext),
            hash=file_hash,
            metadata=file_info.get("metadata", {}),
        )

    def _validate_file(self, file_path: str, filename: str) -> None:
        """Validate file against rules.

        Args:
            file_path: Path to the file.
            filename: Original filename.

        Raises:
            ValueError: If validation fails.
        """
        # Check size
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise ValueError(
                f"File too large: {file_size} > {self.max_file_size} bytes")

        # Check extension
        ext = os.path.splitext(filename)[1].lower().lstrip(".")

        if ext in self.blocked_extensions:
            raise ValueError(f"File type not allowed: {ext}")

        if self.allowed_extensions and ext not in self.allowed_extensions:
            raise ValueError(f"File type not in allowed list: {ext}")

    def _calculate_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file.

        Args:
            file_path: Path to the file.

        Returns:
            Hexadecimal hash string.
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_target_path(self, uploads_dir: str, filename: str, file_hash: str) -> str:
        """Get target path for file.

        Args:
            uploads_dir: Base uploads directory.
            filename: Original filename.
            file_hash: File hash for deduplication.

        Returns:
            Target file path.
        """
        # Use hash-based name for deduplication
        name, ext = os.path.splitext(filename)
        target_name = f"{file_hash[:8]}_{name}{ext}"
        return os.path.join(uploads_dir, target_name)

    def _get_content_type(self, ext: str) -> str:
        """Get MIME content type for extension.

        Args:
            ext: File extension.

        Returns:
            MIME type string.
        """
        content_types = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "md": "text/markdown",
            "html": "text/html",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "json": "application/json",
            "csv": "text/csv",
            "xml": "application/xml",
            "py": "text/x-python",
            "js": "application/javascript",
        }
        return content_types.get(ext, "application/octet-stream")

    def get_uploads(self, thread_id: str) -> List[FileInfo]:
        """Get cached uploads for a thread.

        Args:
            thread_id: Thread identifier.

        Returns:
            List of FileInfo objects.
        """
        return self._uploads.get(thread_id, [])

    def clear_uploads(self, thread_id: str) -> int:
        """Clear cached uploads for a thread.

        Args:
            thread_id: Thread identifier.

        Returns:
            Number of uploads cleared.
        """
        if thread_id in self._uploads:
            count = len(self._uploads[thread_id])
            del self._uploads[thread_id]
            return count
        return 0

    async def teardown(self) -> None:
        """Clear the uploads cache."""
        self._uploads.clear()
        logger.debug("Uploads middleware cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about cached uploads.

        Returns:
            Dictionary with upload statistics.
        """
        total_files = sum(len(files) for files in self._uploads.values())
        total_size = sum(f.size for files in self._uploads.values() for f in files)

        return {
            "total_threads": len(self._uploads),
            "total_files": total_files,
            "total_size": total_size,
            "max_file_size": self.max_file_size,
        }
