"""Project root detection for GPTase.

After the L0 + integration cleanup the only contract this module owns
is ``get_paths().project_root``, consumed by ``gptase/main.py`` to
resolve ``config/plans/<plan_id>.md`` when ``chat -p`` runs.
Examples/scripts that need the ``data/`` subtree construct paths inline
from ``project_root``.
"""

from pathlib import Path
from typing import Optional


class ProjectPaths:
    """Walks up from cwd to find the project root."""

    _MARKERS = (".git", "pyproject.toml", "setup.py", ".project-root")

    def __init__(self, project_root: Optional[Path] = None):
        """Resolve and store the project root.

        Args:
            project_root: Explicit root. If None, auto-detects by walking
                up from cwd looking for a marker file.
        """
        if project_root is None:
            project_root = self._find_project_root()
        self.project_root = Path(project_root).resolve()

    @classmethod
    def _find_project_root(cls) -> Path:
        """Walk up from cwd to find a directory with any marker."""
        current = Path.cwd()
        for parent in [current, *current.parents]:
            for marker in cls._MARKERS:
                if (parent / marker).exists():
                    return parent
        return current


_global_paths: Optional[ProjectPaths] = None


def get_paths(project_root: Optional[Path] = None) -> ProjectPaths:
    """Return the module-level ProjectPaths singleton (initialized lazily)."""
    global _global_paths
    if _global_paths is None:
        _global_paths = ProjectPaths(project_root)
    return _global_paths
