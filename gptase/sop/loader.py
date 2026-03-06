"""SOP definition loader for YAML and JSON formats.

This module provides the SOPLoader class for loading SOP definitions
from files in either YAML or JSON format.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from gptase.sop.exceptions import SOPNotFoundError
from gptase.sop.exceptions import SOPValidationError
from gptase.sop.types import SOPDefinition
from gptase.utils.paths import get_paths

logger = logging.getLogger(__name__)

# Default SOP directory relative to project root
_DEFAULT_SOP_DIR = "config/sops"


class SOPLoader:
    """Loader for SOP definitions from YAML or JSON files.

    Supports loading SOP definitions from files with automatic format
    detection based on file extension. Also provides discovery of
    available SOPs.

    Attributes:
        sop_dir: Directory containing SOP definition files.
    """

    def __init__(self, sop_dir: Optional[Path] = None):
        """Initialize the SOP loader.

        Args:
            sop_dir: Directory containing SOP definition files.
                    Defaults to config/sops/ under project root.
        """
        if sop_dir is None:
            # Use project paths to find config/sops
            paths = get_paths()
            sop_dir = paths.project_root / _DEFAULT_SOP_DIR

        self.sop_dir = Path(sop_dir)

        if not self.sop_dir.exists():
            logger.warning("SOP directory does not exist: %s", self.sop_dir)
            self.sop_dir.mkdir(parents=True, exist_ok=True)

    def load(self, plan_id: str) -> SOPDefinition:
        """Load an SOP definition by plan_id.

        Searches for the SOP file in order of preference:
        1. {plan_id}.yaml
        2. {plan_id}.yml
        3. {plan_id}.json

        Args:
            plan_id: The unique identifier of the SOP to load.

        Returns:
            The validated SOPDefinition.

        Raises:
            SOPNotFoundError: If the SOP file cannot be found.
            SOPValidationError: If the SOP definition is invalid.
        """
        # Try different extensions in order
        extensions = [".yaml", ".yml", ".json"]

        for ext in extensions:
            file_path = self.sop_dir / f"{plan_id}{ext}"
            if file_path.exists():
                logger.info("Loading SOP '%s' from %s", plan_id, file_path)
                return self._load_file(file_path)

        # No file found
        raise SOPNotFoundError(
            plan_id=plan_id,
            search_path=str(self.sop_dir),
        )

    def _load_file(self, file_path: Path) -> SOPDefinition:
        """Load and validate an SOP definition from a file.

        Args:
            file_path: Path to the SOP definition file.

        Returns:
            The validated SOPDefinition.

        Raises:
            SOPValidationError: If the file cannot be parsed or validated.
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Parse based on extension
            if file_path.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)

            if not isinstance(data, dict):
                raise SOPValidationError(
                    plan_id=str(file_path.stem),
                    reason="SOP definition must be a dictionary",
                )

            # Validate plan_id exists
            if "plan_id" not in data:
                data["plan_id"] = file_path.stem
                logger.debug("Using filename as plan_id: %s", data["plan_id"])

            # Create and validate the definition
            return SOPDefinition(**data)

        except yaml.YAMLError as e:
            raise SOPValidationError(
                plan_id=str(file_path.stem),
                reason=f"YAML parsing error: {e}",
            ) from e
        except json.JSONDecodeError as e:
            raise SOPValidationError(
                plan_id=str(file_path.stem),
                reason=f"JSON parsing error: {e}",
            ) from e
        except SOPValidationError:
            raise
        except Exception as e:
            raise SOPValidationError(
                plan_id=str(file_path.stem),
                reason=f"Failed to load SOP: {e}",
            ) from e

    def load_from_dict(self, data: Dict[str, Any]) -> SOPDefinition:
        """Load an SOP definition from a dictionary.

        Args:
            data: Dictionary containing the SOP definition.

        Returns:
            The validated SOPDefinition.

        Raises:
            SOPValidationError: If the definition is invalid.
        """
        try:
            return SOPDefinition(**data)
        except Exception as e:
            plan_id = data.get("plan_id", "unknown")
            raise SOPValidationError(
                plan_id=plan_id,
                reason=f"Invalid SOP definition: {e}",
            ) from e

    def list_available_sops(self) -> List[Dict[str, str]]:
        """List all available SOP definitions.

        Scans the SOP directory for definition files and extracts
        basic metadata without fully loading each SOP.

        Returns:
            List of dictionaries with plan_id, name, and description.
        """
        sops = []

        if not self.sop_dir.exists():
            return sops

        # Find all YAML and JSON files
        patterns = ["*.yaml", "*.yml", "*.json"]

        for pattern in patterns:
            for file_path in self.sop_dir.glob(pattern):
                try:
                    sop_info = self._extract_sop_info(file_path)
                    if sop_info:
                        sops.append(sop_info)
                except Exception as e:
                    logger.warning("Failed to extract info from %s: %s", file_path, e)

        # Sort by plan_id
        sops.sort(key=lambda x: x["plan_id"])
        return sops

    def _extract_sop_info(self, file_path: Path) -> Optional[Dict[str, str]]:
        """Extract basic info from an SOP file without full loading.

        Args:
            file_path: Path to the SOP definition file.

        Returns:
            Dictionary with plan_id, name, and description, or None.
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            if file_path.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)

            if not isinstance(data, dict):
                return None

            return {
                "plan_id": data.get("plan_id", file_path.stem),
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "version": data.get("version", "1.0"),
                "file": str(file_path.name),
            }
        except Exception:
            return None

    def exists(self, plan_id: str) -> bool:
        """Check if an SOP definition exists.

        Args:
            plan_id: The SOP identifier to check.

        Returns:
            True if the SOP file exists, False otherwise.
        """
        extensions = [".yaml", ".yml", ".json"]
        for ext in extensions:
            if (self.sop_dir / f"{plan_id}{ext}").exists():
                return True
        return False

    def reload(self, plan_id: str) -> SOPDefinition:
        """Reload an SOP definition (alias for load).

        Args:
            plan_id: The SOP identifier to reload.

        Returns:
            The freshly loaded SOPDefinition.
        """
        return self.load(plan_id)


class SOPRegistry:
    """Singleton registry for SOP definitions with caching.

    Provides a centralized registry for discovering and caching
    SOP definitions. Uses lazy loading - SOPs are loaded on demand
    and cached for subsequent access.

    Usage:
        registry = SOPRegistry.get_instance()
        sop = registry.get_sop("my_pipeline")
        available = registry.list_sops()
    """

    _instance: Optional["SOPRegistry"] = None

    def __init__(self, sop_dir: Optional[Path] = None):
        """Initialize the registry.

        Args:
            sop_dir: Directory containing SOP definition files.
        """
        self._loader = SOPLoader(sop_dir)
        self._cache: Dict[str, SOPDefinition] = {}

    @classmethod
    def get_instance(cls, sop_dir: Optional[Path] = None) -> "SOPRegistry":
        """Get the singleton registry instance.

        Args:
            sop_dir: Optional SOP directory (only used on first call).

        Returns:
            The SOPRegistry singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls(sop_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None

    def get_sop(self, plan_id: str, use_cache: bool = True) -> SOPDefinition:
        """Get an SOP definition by plan_id.

        Args:
            plan_id: The SOP identifier.
            use_cache: Whether to use cached definition if available.

        Returns:
            The SOPDefinition.

        Raises:
            SOPNotFoundError: If the SOP cannot be found.
        """
        if use_cache and plan_id in self._cache:
            return self._cache[plan_id]

        sop = self._loader.load(plan_id)
        self._cache[plan_id] = sop
        return sop

    def list_sops(self) -> List[Dict[str, str]]:
        """List all available SOP definitions.

        Returns:
            List of dictionaries with SOP metadata.
        """
        return self._loader.list_available_sops()

    def exists(self, plan_id: str) -> bool:
        """Check if an SOP exists.

        Args:
            plan_id: The SOP identifier.

        Returns:
            True if the SOP exists.
        """
        return plan_id in self._cache or self._loader.exists(plan_id)

    def clear_cache(self) -> None:
        """Clear the SOP cache."""
        self._cache.clear()

    def refresh(self, plan_id: str) -> SOPDefinition:
        """Refresh an SOP definition from disk.

        Args:
            plan_id: The SOP identifier to refresh.

        Returns:
            The freshly loaded SOPDefinition.
        """
        self._cache.pop(plan_id, None)
        return self.get_sop(plan_id, use_cache=False)
