"""EvalRunner: loads golden data, evaluates agents using cache or live API.

Cache layout (as written by PlanManager workspace output):
    {cache_dir}/
        document_structure_analyzer/   1_parsed.json
        enzyme_kinetics_extractor/      2a_parsed.json
        vision_image_analyzer/          2b_parsed.json
        enzyme_extraction_summary/      3_parsed.json

The runner scans the agent subdirectory for any *_parsed.json file,
so it is not coupled to specific step IDs.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from gptase.evals.assertions import EvalResult
from gptase.evals.assertions import evaluate_key_facts
from gptase.evals.assertions import validate_schema

logger = logging.getLogger(__name__)

# Root directories resolved relative to this file's location (package root)
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent
_EVALS_DATA_DIR = _PACKAGE_ROOT / "data" / "evals"
_OUTPUT_DATA_DIR = _PACKAGE_ROOT / "data" / "output"


class EvalRunner:
    """Load golden data and evaluate agent outputs for a paper.

    Args:
        paper_id: Identifier matching a subdirectory in data/evals/.
        cache_dir: Path to a specific pipeline run directory. If None,
                   the latest run directory for the paper is used.
    """

    def __init__(self, paper_id: str, cache_dir: Optional[str] = None):
        self.paper_id = paper_id
        self.golden = self._load_golden(paper_id)
        self.cache_dir = Path(cache_dir) if cache_dir else self._find_latest_cache(paper_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def eval_agent(self, agent_name: str, live: bool = False) -> EvalResult:
        """Evaluate a single agent.

        Args:
            agent_name: Agent identifier matching a key in golden.yaml agents section.
            live: If True, run the agent live against the LLM API.

        Returns:
            EvalResult for this agent.
        """
        agent_spec = self.golden.get("agents", {}).get(agent_name)
        if agent_spec is None:
            logger.warning("[WARNING] No golden spec for agent: %s", agent_name)
            return EvalResult(
                agent_name=agent_name,
                paper_id=self.paper_id,
                schema_valid=False,
                schema_error=f"No golden spec for agent '{agent_name}'",
                total_facts=0,
                passed_facts=0,
                failed_facts=[f"No golden spec for agent '{agent_name}'"],
            )

        if live:
            output = await self._run_agent_live(agent_name)
        else:
            output = self._load_cached_output(agent_name)

        if output is None:
            return EvalResult(
                agent_name=agent_name,
                paper_id=self.paper_id,
                schema_valid=False,
                schema_error="No output available (cache miss and live=False)",
                total_facts=len(agent_spec.get("key_facts", [])),
                passed_facts=0,
                failed_facts=["No output available"],
            )

        schema_name = agent_spec.get("schema", "")
        schema_valid, schema_error = validate_schema(output, schema_name)

        result = evaluate_key_facts(
            data=output,
            key_facts=agent_spec.get("key_facts", []),
            agent_name=agent_name,
            paper_id=self.paper_id,
        )
        result.schema_valid = schema_valid
        result.schema_error = schema_error

        return result

    async def eval_all(self, live: bool = False) -> List[EvalResult]:
        """Evaluate all agents defined in golden.yaml.

        Args:
            live: If True, run each agent live against the LLM API.

        Returns:
            List of EvalResult, one per agent in golden.yaml.
        """
        agent_names = list(self.golden.get("agents", {}).keys())
        results = []
        for agent_name in agent_names:
            result = await self.eval_agent(agent_name, live=live)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Cache loading
    # ------------------------------------------------------------------

    def _load_cached_output(self, agent_name: str) -> Optional[dict]:
        """Load the *_parsed.json from cache_dir/{agent_name}/.

        Scans for any file matching *_parsed.json in the agent subdirectory.
        """
        if self.cache_dir is None:
            logger.warning("[WARNING] No cache directory found for paper: %s", self.paper_id)
            return None

        agent_dir = self.cache_dir / agent_name
        if not agent_dir.exists():
            logger.warning("[WARNING] Cache dir not found: %s", agent_dir)
            return None

        parsed_files = sorted(agent_dir.glob("*_parsed.json"))
        if not parsed_files:
            logger.warning("[WARNING] No *_parsed.json found in %s", agent_dir)
            return None

        parsed_path = parsed_files[0]
        try:
            with open(parsed_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("[ERROR] Failed to load %s: %s", parsed_path, exc)
            return None

    def _find_latest_cache(self, paper_id: str) -> Optional[Path]:
        """Find the most recent pipeline run directory in data/output/{paper_id}/.

        Returns the lexicographically last subdirectory (timestamp-based names
        sort correctly as strings: YYYYMMDD_HHMMSS).
        """
        output_dir = _OUTPUT_DATA_DIR / paper_id
        if not output_dir.exists():
            return None

        candidates = [
            d for d in output_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        if not candidates:
            return None

        latest = max(candidates, key=lambda d: d.name)
        logger.info("[INFO] Using cache: %s", latest)
        return latest

    # ------------------------------------------------------------------
    # Live execution
    # ------------------------------------------------------------------

    async def _run_agent_live(self, agent_name: str) -> Optional[dict]:
        """Run an agent live against the LLM API and return parsed JSON output.

        Reads input from paths specified in golden.yaml (input_file /
        input_images_dir).
        """
        from gptase.agents.base import Agent
        from gptase.models.model import Model

        golden = self.golden
        input_file = golden.get("input_file")
        images_dir = golden.get("input_images_dir")

        # Resolve relative to project root
        input_text = None
        if input_file:
            input_path = _PACKAGE_ROOT / input_file
            if input_path.exists():
                input_text = input_path.read_text(encoding="utf-8")
            else:
                logger.warning("[WARNING] Input file not found: %s", input_path)

        image_paths = None
        if images_dir:
            images_path = _PACKAGE_ROOT / images_dir
            if images_path.exists():
                exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
                image_paths = [
                    str(p) for p in sorted(images_path.iterdir())
                    if p.suffix.lower() in exts
                ]

        if input_text is None and not image_paths:
            logger.error("[ERROR] No input available for live run of %s", agent_name)
            return None

        model = Model()
        try:
            agent = Agent.from_markdown(agent_name, model_manager=model)
        except FileNotFoundError:
            logger.error("[ERROR] Agent definition not found: %s", agent_name)
            return None

        result = await agent.run(
            content=input_text or "",
            image_paths=image_paths,
        )

        if result.get("status") == "error":
            logger.error("[ERROR] Agent %s failed: %s", agent_name, result.get("error"))
            return None

        content = result.get("data", {}).get("content", "")
        return _parse_json_content(content)

    # ------------------------------------------------------------------
    # Golden data loading
    # ------------------------------------------------------------------

    def _load_golden(self, paper_id: str) -> dict:
        """Load golden.yaml for a paper.

        Args:
            paper_id: Subdirectory name under data/evals/.

        Returns:
            Parsed YAML as a dict.

        Raises:
            FileNotFoundError: If golden.yaml does not exist.
        """
        golden_path = _EVALS_DATA_DIR / paper_id / "golden.yaml"
        if not golden_path.exists():
            raise FileNotFoundError(
                f"Golden file not found: {golden_path}\n"
                f"Create data/evals/{paper_id}/golden.yaml to add eval data."
            )
        with open(golden_path, encoding="utf-8") as f:
            return yaml.safe_load(f)


def list_eval_papers() -> List[str]:
    """Return all paper IDs that have a golden.yaml in data/evals/."""
    if not _EVALS_DATA_DIR.exists():
        return []
    return [
        d.name for d in sorted(_EVALS_DATA_DIR.iterdir())
        if d.is_dir() and (d / "golden.yaml").exists()
    ]


def _parse_json_content(content: str) -> Optional[dict]:
    """Parse JSON from agent content string (handles markdown code blocks)."""
    if not content:
        return None

    content = content.strip()

    if "```json" in content:
        parts = content.split("```json")
        if len(parts) > 1:
            json_part = parts[1].split("```")[0].strip()
            try:
                return json.loads(json_part)
            except (json.JSONDecodeError, ValueError):
                pass
    elif content.startswith("```"):
        parts = content.split("```")
        if len(parts) > 1:
            json_part = parts[1].strip()
            if "\n" in json_part:
                json_part = json_part.split("\n", 1)[1]
            try:
                return json.loads(json_part)
            except (json.JSONDecodeError, ValueError):
                pass

    if content.startswith("{") or content.startswith("["):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass

    return None
