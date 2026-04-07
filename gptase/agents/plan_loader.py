"""Plan definition loader for YAML and JSON formats.

This module provides the PlanLoader class for loading Plan definitions
from files. It also maps legacy workflow sequences into the Plan's
DAG dependency model automatically.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import yaml

from gptase.agents.types import Plan
from gptase.agents.types import Task
from gptase.utils.paths import get_paths

logger = logging.getLogger(__name__)

# Default config directory for plans
_DEFAULT_PLAN_DIR = "config/plans"


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

    def load_path(self, file_path: Path) -> Plan:
        """Load a Plan from an explicit file path."""
        resolved = Path(file_path)
        if not resolved.exists():
            raise PlanNotFoundError(plan_id=str(file_path),
                                    search_path=str(resolved.parent))
        return self._load_file(resolved)

    def load_data(self,
                  data: Dict[str, Any],
                  fallback_plan_id: str = "inline_plan") -> Plan:
        """Load a Plan from an in-memory dict."""
        if not isinstance(data, dict):
            raise PlanValidationError(fallback_plan_id, "Definition must be a dict")

        plan_id = data.get("plan_id", fallback_plan_id)

        tasks: List[Task] = []
        if "workflow" in data:
            tasks = self._parse_legacy_workflow(data["workflow"])
        elif "tasks" in data:
            for td in data["tasks"]:
                tasks.append(Task(**td))

        return Plan(
            plan_id=plan_id,
            goal=data.get("description", ""),
            summary=data.get("name", ""),
            tasks=tasks,
            max_parallel=data.get("max_parallel", 10),
            default_retry_count=data.get("default_retry_count", 0),
        )

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

            return self.load_data(data, fallback_plan_id=file_path.stem)

        except yaml.YAMLError as e:
            raise PlanValidationError(str(file_path.stem),
                                      f"YAML parsing error: {e}") from e
        except json.JSONDecodeError as e:
            raise PlanValidationError(str(file_path.stem),
                                      f"JSON parsing error: {e}") from e
        except Exception as e:
            raise PlanValidationError(str(file_path.stem),
                                      f"Failed to load Plan: {e}") from e

    def _parse_legacy_workflow(self, workflow: List[Any]) -> List[Task]:
        """Convert a legacy sequential/parallel workflow into a list of Tasks."""
        tasks: List[Task] = []
        prev_dependencies = []

        for item in workflow:
            current_group_ids = []
            if "parallel" in item:
                # Parallel group: everyone depends on prev_dependencies
                for p_step in item["parallel"]:
                    expanded = self._expand_replicated_step(p_step, prev_dependencies)
                    tasks.extend(expanded)
                    current_group_ids.extend(t.task_id for t in expanded)
            else:
                # Single step (may expand to N replicas)
                expanded = self._expand_replicated_step(item, prev_dependencies)
                tasks.extend(expanded)
                current_group_ids.extend(t.task_id for t in expanded)

            prev_dependencies = current_group_ids

        return tasks

    def _expand_replicated_step(self, step_data: dict,
                                dependencies: List[str]) -> List[Task]:
        """Expand a step with replicate: N into N parallel tasks.

        A step with ``replicate: 3`` and ``step_id: "2a"`` produces three tasks
        with IDs ``2a_r1``, ``2a_r2``, ``2a_r3``, all sharing the same dependencies
        and inputs.  Downstream steps referencing ``{{step2a}}`` receive a list of
        all replica results (resolved in TaskDispatcher).
        """
        replicate = int(step_data.get("replicate", 1))
        if replicate <= 1:
            return [self._build_task(step_data, dependencies)]

        base_id = str(step_data.get("step_id", uuid4().hex[:8]))
        expanded = []
        for i in range(1, replicate + 1):
            replica_data = dict(step_data)
            replica_data["step_id"] = f"{base_id}_r{i}"
            expanded.append(self._build_task(replica_data, dependencies))
        return expanded

    def _build_task(self, step_data: dict, dependencies: List[str]) -> Task:
        return Task(
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
