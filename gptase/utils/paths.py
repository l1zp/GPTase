"""
Centralized path management for GPTase framework.

This module provides a single source of truth for all file paths and directories
used throughout the framework, ensuring consistency and making it easy to
reorganize the project structure.

Directory Structure:
    data/
    ├── input/              # Input documents (markdown, pdf, etc.)
    │   └── {doc_name}/     # Organized by document name
    │       ├── {name}.md   # Markdown text
    │       ├── {name}.pdf  # Original PDF (optional)
    │       └── images/     # Extracted images
    ├── output/             # All output organized by document name
    │   └── {doc_name}/
    │       └── {plan_id}_{timestamp}/  # Plan execution results
    │           ├── analysis/       # Structure analysis results
    │           ├── extraction/     # Extracted enzyme data
    │           ├── vision/         # Vision analysis results
    │           └── summary/        # Summary report
    ├── cache/              # Cached intermediate results
    └── logs/               # Application logs

Example for document "listov2025":
    data/output/listov2025/enzyme_extraction_pipeline_20260202/
    ├── analysis/
    │   ├── structure_analysis.json
    │   └── structure_analysis.csv
    ├── extraction/
    │   ├── extraction.json
    │   └── combined_data.csv
    ├── vision/
    │   ├── vision_analysis.json
    │   └── extracted_tables.csv
    └── summary/
        ├── summary.json
        └── summary.md
"""

from pathlib import Path
from typing import Optional


class ProjectPaths:
    """Centralized path management for GPTase project."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize project paths.

        Args:
            project_root: Root directory of the project. If None, auto-detects
                         by finding the directory containing .git or pyproject.toml.
        """
        if project_root is None:
            project_root = self._find_project_root()

        self.project_root = Path(project_root).resolve()
        self.data_dir = self.project_root / "data"

        # Create all data subdirectories
        self._setup_directories()

    def _find_project_root(self) -> Path:
        """Auto-detect project root by looking for .git or pyproject.toml."""
        current = Path.cwd()

        # Look for project markers
        markers = [".git", "pyproject.toml", "setup.py", ".project-root"]

        for parent in [current, *current.parents]:
            for marker in markers:
                if (parent / marker).exists():
                    return parent

        # Fallback: assume we're in the project directory
        return current

    def _setup_directories(self) -> None:
        """Define all standard directories."""
        # Input data directories
        self.input_dir = self.data_dir / "input"
        self.documents_dir = self.input_dir / "documents"

        # Output directory (organized by document name)
        self.output_dir = self.data_dir / "output"

        # Cache and logs
        self.cache_dir = self.data_dir / "cache"
        self.logs_dir = self.data_dir / "logs"

        # Database directory
        self.db_dir = self.data_dir
        self.conversation_db_path = self.db_dir / "conversations.db"

    def ensure_directories(self) -> None:
        """Ensure all standard directories exist."""
        directories = [
            self.data_dir,
            self.input_dir,
            self.documents_dir,
            self.output_dir,
            self.cache_dir,
            self.logs_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_document_output_dir(self, document_name: str) -> Path:
        """Get output directory for a specific document.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to document's output directory
        """
        doc_dir = self.output_dir / document_name
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    def get_document_analysis_dir(self, document_name: str) -> Path:
        """Get analysis subdirectory for a specific document.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to document's analysis directory
        """
        analysis_dir = self.get_document_output_dir(document_name) / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        return analysis_dir

    def get_document_extraction_dir(self, document_name: str) -> Path:
        """Get extraction subdirectory for a specific document.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to document's extraction directory
        """
        extraction_dir = self.get_document_output_dir(document_name) / "extraction"
        extraction_dir.mkdir(parents=True, exist_ok=True)
        return extraction_dir

    def get_document_vision_dir(self, document_name: str) -> Path:
        """Get vision subdirectory for a specific document.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to document's vision directory
        """
        vision_dir = self.get_document_output_dir(document_name) / "vision"
        vision_dir.mkdir(parents=True, exist_ok=True)
        return vision_dir

    # Analysis file paths

    def get_structure_analysis_path(self, document_name: str) -> Path:
        """Get path for document structure analysis JSON file.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to structure analysis JSON file in document's output directory
        """
        analysis_dir = self.get_document_analysis_dir(document_name)
        return analysis_dir / "structure_analysis.json"

    def get_structure_analysis_csv_path(self, document_name: str) -> Path:
        """Get path for document structure analysis CSV file.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to structure analysis CSV file in document's output directory
        """
        analysis_dir = self.get_document_analysis_dir(document_name)
        return analysis_dir / "structure_analysis.csv"

    def get_structure_analysis_images_csv_path(self, document_name: str) -> Path:
        """Get path for image information CSV file from structure analysis.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to images CSV file in document's output directory
        """
        analysis_dir = self.get_document_analysis_dir(document_name)
        return analysis_dir / "structure_analysis_images.csv"

    # Extraction file paths

    def get_extraction_path(self, document_name: str) -> Path:
        """Get path for enzyme extraction JSON file.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to extraction JSON file in document's output directory
        """
        extraction_dir = self.get_document_extraction_dir(document_name)
        return extraction_dir / "extraction.json"

    def get_extraction_csv_path(self, document_name: str) -> Path:
        """Get path for enzyme extraction CSV file.

        Args:
            document_name: Name of the document (without extension)

        Returns:
            Path to extraction CSV file in document's output directory
        """
        extraction_dir = self.get_document_extraction_dir(document_name)
        return extraction_dir / "extraction.csv"

    # Vision analysis file paths

    def get_vision_analysis_path(self, document_name: Optional[str] = None) -> Path:
        """Get path for vision analysis JSON file.

        Args:
            document_name: Name of the document (without extension).
                          If None, returns generic path in output root.

        Returns:
            Path to vision analysis JSON file
        """
        if document_name:
            vision_dir = self.get_document_vision_dir(document_name)
            return vision_dir / "vision_analysis.json"
        # Generic path for backward compatibility
        return self.output_dir / "vision_analysis_results.json"

    def get_vision_tables_path(self, document_name: Optional[str] = None) -> Path:
        """Get path for extracted tables CSV from vision analysis.

        Args:
            document_name: Name of the document (without extension).
                          If None, returns generic path in output root.

        Returns:
            Path to extracted tables CSV file
        """
        if document_name:
            vision_dir = self.get_document_vision_dir(document_name)
            return vision_dir / "extracted_tables.csv"
        # Generic path for backward compatibility
        return self.output_dir / "extracted_tables.csv"

    # Input file paths

    def get_document_path(self, document_name: str) -> Path:
        """Get path for input document.

        Args:
            document_name: Name of the document (can include .md extension)

        Returns:
            Path to the document file
        """
        # Add .md extension if not present
        if not document_name.endswith(".md"):
            document_name = f"{document_name}.md"
        return self.documents_dir / document_name

    # Utility methods

    def resolve_input_path(self, path: str) -> Path:
        """Resolve a user-provided input path.

        If the path is relative, it's resolved relative to the documents directory.
        If the path is absolute, it's used as-is.

        Args:
            path: User-provided path (relative or absolute)

        Returns:
            Resolved absolute path
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return self.documents_dir / path

    def resolve_output_path(self,
                            path: str,
                            default_subdir: str = "extraction") -> Path:
        """Resolve a user-provided output path.

        If the path is relative, it's resolved relative to the data directory.
        If the path is absolute, it's used as-is.

        Args:
            path: User-provided path (relative or absolute)
            default_subdir: Default subdirectory under data/ (default: "extraction")

        Returns:
            Resolved absolute path
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return self.data_dir / path

    def get_cache_path(self, cache_key: str) -> Path:
        """Get path for a cached file.

        Args:
            cache_key: Unique identifier for the cached item

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{cache_key}.json"

    def get_log_path(self, log_name: str) -> Path:
        """Get path for a log file.

        Args:
            log_name: Name of the log file (without .log extension)

        Returns:
            Path to log file
        """
        return self.logs_dir / f"{log_name}.log"

    def get_plan_output_dir(
        self,
        document_name: str,
        plan_id: str,
        timestamp: Optional[str] = None,
    ) -> Path:
        """Get output directory for a specific plan execution.

        Args:
            document_name: Name of the document being processed
            plan_id: Plan identifier (e.g., "enzyme_extraction_pipeline")
            timestamp: Optional timestamp string. If None, uses current time.

        Returns:
            Path to plan output directory
        """
        if timestamp is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        plan_dir = self.output_dir / document_name / f"{plan_id}_{timestamp}"
        plan_dir.mkdir(parents=True, exist_ok=True)
        return plan_dir


# Global singleton instance
_global_paths: Optional[ProjectPaths] = None


def get_paths(project_root: Optional[Path] = None) -> ProjectPaths:
    """Get the global ProjectPaths instance.

    Args:
        project_root: Optional project root path. Only used on first call.

    Returns:
        ProjectPaths instance
    """
    global _global_paths
    if _global_paths is None:
        _global_paths = ProjectPaths(project_root)
        _global_paths.ensure_directories()
    return _global_paths


def reset_paths() -> None:
    """Reset the global ProjectPaths instance (useful for testing)."""
    global _global_paths
    _global_paths = None
