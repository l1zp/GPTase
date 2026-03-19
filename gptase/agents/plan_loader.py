"""Plan definition loader for YAML and JSON formats.

This module provides the PlanLoader class for loading Plan definitions
from files. It also maps legacy SOP workflow sequences into the Plan's
DAG dependency model automatically.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import yaml

from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
from gptase.utils.paths import get_paths

logger = logging.getLogger(__name__)

# Default config directory for plans
_DEFAULT_PLAN_DIR = "config/plans"  # Keep loading from sops for backward compatibility for now


class PlanNotFoundError(Exception):

    def __init__(self, plan_id: str, search_path: str):
        super().__init__(f"Plan '{plan_id}' not found in {search_path}")


class PlanValidationError(Exception):

    def __init__(self, plan_id: str, reason: str):
        super().__init__(f"Invalid plan '{plan_id}': {reason}")


class PlanLoader:
    """Loader for predefined Plans from YAML or JSON files.

    Supports translating legacy sequence/parallel steps into
    Explicit DAG dependencies.
    """

    def __init__(self, plan_dir: Optional[Path] = None):
        """Initialize the plan loader."""
        if plan_dir is None:
            paths = get_paths()
            plan_dir = paths.project_root / _DEFAULT_PLAN_DIR

        self.plan_dir = Path(plan_dir)
        if not self.plan_dir.exists():
            logger.warning("Plan directory does not exist: %s", self.plan_dir)
            self.plan_dir.mkdir(parents=True, exist_ok=True)

    def load(self, plan_id: str) -> Plan:
        """Load a Plan by plan_id."""
        extensions = [".yaml", ".yml", ".json"]
        for ext in extensions:
            file_path = self.plan_dir / f"{plan_id}{ext}"
            if file_path.exists():
                logger.info("Loading Plan '%s' from %s", plan_id, file_path)
                return self._load_file(file_path)

        raise PlanNotFoundError(plan_id=plan_id, search_path=str(self.plan_dir))

    def _load_file(self, file_path: Path) -> Plan:
        try:
            content = file_path.read_text(encoding="utf-8")
            if file_path.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)

            if not isinstance(data, dict):
                raise PlanValidationError(str(file_path.stem),
                                          "Definition must be a dict")

            plan_id = data.get("plan_id", file_path.stem)

            # Extract tasks
            tasks: List[PlannedTask] = []

            # The YAML might define a Plan directly or use legacy SOP format
            if "workflow" in data:
                # Legacy SOP parsing mapping to DAG
                tasks = self._parse_legacy_workflow(data["workflow"])
            elif "tasks" in data:
                # Direct planned task list
                for td in data["tasks"]:
                    tasks.append(PlannedTask(**td))

            return Plan(
                plan_id=plan_id,
                goal=data.get("description", ""),
                summary=data.get("name", ""),
                tasks=tasks,
                max_parallel=data.get("max_parallel", 10),
                default_retry_count=data.get("default_retry_count", 0),
            )

        except yaml.YAMLError as e:
            raise PlanValidationError(str(file_path.stem),
                                      f"YAML parsing error: {e}") from e
        except json.JSONDecodeError as e:
            raise PlanValidationError(str(file_path.stem),
                                      f"JSON parsing error: {e}") from e
        except Exception as e:
            raise PlanValidationError(str(file_path.stem),
                                      f"Failed to load Plan: {e}") from e

    def _parse_legacy_workflow(self, workflow: List[Any]) -> List[PlannedTask]:
        """Convert a legacy sequential/parallel workflow into a list of PlannedTasks."""
        tasks: List[PlannedTask] = []
        prev_dependencies = []

        for item in workflow:
            current_group_ids = []
            if "parallel" in item:
                # Parallel group: everyone depends on prev_dependencies
                for p_step in item["parallel"]:
                    t = self._build_task(p_step, prev_dependencies)
                    tasks.append(t)
                    current_group_ids.append(t.task_id)
            else:
                # Single step
                t = self._build_task(item, prev_dependencies)
                tasks.append(t)
                current_group_ids.append(t.task_id)

            prev_dependencies = current_group_ids

        return tasks

    def _build_task(self, step_data: dict, dependencies: List[str]) -> PlannedTask:
        return PlannedTask(
            task_id=str(step_data.get("step_id",
                                      uuid4().hex[:8])),
            description=step_data.get("description", "No description"),
            dependencies=dependencies.copy(),
            agent_id=step_data.get("agent"),
            action=step_data.get("action", "process"),
            inputs=step_data.get("inputs", {}),
            retry_count=step_data.get("retry_count", 0),
            optional=step_data.get("optional", False),
        )

    def list_available_plans(self) -> List[Dict[str, str]]:
        plans = []
        if not self.plan_dir.exists():
            return plans

        patterns = ["*.yaml", "*.yml", "*.json"]
        for pattern in patterns:
            for file_path in self.plan_dir.glob(pattern):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if file_path.suffix in [".yaml", ".yml"]:
                        data = yaml.safe_load(content)
                    else:
                        data = json.loads(content)

                    if isinstance(data, dict):
                        plans.append({
                            "plan_id": data.get("plan_id", file_path.stem),
                            "name": data.get("name", ""),
                            "description": data.get("description", ""),
                            "file": str(file_path.name),
                        })
                except Exception:
                    pass

        plans.sort(key=lambda x: x["plan_id"])
        return plans


class PlanRegistry:
    """Singleton registry for Plan definitions with caching."""
    _instance: Optional["PlanRegistry"] = None

    def __init__(self, plan_dir: Optional[Path] = None):
        self._loader = PlanLoader(plan_dir)
        self._cache: Dict[str, Plan] = {}

    @classmethod
    def get_instance(cls, plan_dir: Optional[Path] = None) -> "PlanRegistry":
        if cls._instance is None:
            cls._instance = cls(plan_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def get_plan(self, plan_id: str, use_cache: bool = True) -> Plan:
        if use_cache and plan_id in self._cache:
            return self._cache[plan_id]
        plan = self._loader.load(plan_id)
        self._cache[plan_id] = plan
        return plan

    def list_plans(self) -> List[Dict[str, str]]:
        return self._loader.list_available_plans()

    def clear_cache(self) -> None:
        self._cache.clear()

    def refresh(self, plan_id: str) -> Plan:
        self._cache.pop(plan_id, None)
        return self.get_plan(plan_id, use_cache=False)
