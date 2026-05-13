"""Unit tests for gptase.evals.runner.

Twelve cases covering the runner's three concerns:

* Filesystem resolution — agent dir lookup with dash/underscore
  tolerance, golden.yaml loading, cached-output discovery.
* The ``live=False`` path — cache miss surfacing the explicit
  ``cache_miss`` failure_reason; cache hit threading through schema
  validation + key-fact evaluation.
* The ``live=True`` path — input resolution, agent-init failures,
  text-output wrapping for markdown-only agents.

The legacy test suite shipped 4 of these (hyphen/underscore,
cache_miss, agent_init_error, text_output) and they were the highest-
value cases; ported with minor renames.
"""
import json
from unittest.mock import patch

import pytest

from gptase.evals.assertions import EvalResult
from gptase.evals.runner import EvalRunner
from gptase.evals.runner import run_eval
from gptase.utils.exceptions import AgentInitializationError


@pytest.fixture
def agents_dir(tmp_path, monkeypatch):
    """Repoint ``_AGENTS_DIR`` at ``tmp_path`` so every test gets an
    isolated, throwaway agent tree.

    Returns ``tmp_path`` so callers can build agent subdirs directly
    without re-spelling the monkeypatch line that all 9 originals
    duplicated.
    """
    monkeypatch.setattr("gptase.evals.runner._AGENTS_DIR", tmp_path)
    return tmp_path


def _write_golden(
        agent_dir,
        schema: str = "vision_analysis",
        key_facts: str = "  - field: total_images\n    condition: gte\n    value: 1\n",
        extra: str = "") -> None:
    """Create a minimal golden.yaml for an agent dir under tmp_path."""
    evals_dir = agent_dir / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)
    (evals_dir / "golden.yaml").write_text(
        f"schema: {schema}\nkey_facts:\n{key_facts}{extra}",
        encoding="utf-8",
    )


class TestResolveAgentDir:
    """Agent dir lookup with dash/underscore tolerance."""

    def test_underscore_input_resolves_to_dashed_dir(self, agents_dir):
        # Real .claude/agents/ uses dashes (vision-image-analyzer/).
        # The runner accepts the underscore form too because Python
        # callers tend to spell agent ids with underscores.
        agent_dir = agents_dir / "vision-image-analyzer"
        _write_golden(agent_dir)

        runner = EvalRunner("vision_image_analyzer")

        assert runner.resolved_agent_name == "vision-image-analyzer"
        assert runner.evals_dir == agent_dir / "evals"


class TestLoadGolden:
    """golden.yaml is a hard dependency — missing means raise immediately."""

    def test_missing_golden_raises_with_helpful_path(self, agents_dir):
        # No agent dir + no golden.yaml -> __init__ blows up with a
        # message naming the path the runner expected.
        with pytest.raises(FileNotFoundError) as exc:
            EvalRunner("missing-agent")

        assert "golden.yaml" in str(exc.value)
        assert "missing-agent" in str(exc.value)

    def test_golden_parses_into_dict(self, agents_dir):
        agent_dir = agents_dir / "agent-x"
        _write_golden(agent_dir, schema="enzyme_kinetics")

        runner = EvalRunner("agent-x")

        assert runner.golden["schema"] == "enzyme_kinetics"
        assert runner.golden["key_facts"][0]["condition"] == "gte"


class TestLoadCachedOutput:
    """Picks newest *.json in evals/output/, tolerates corrupt files."""

    def test_no_output_dir_returns_none(self, agents_dir):
        agent_dir = agents_dir / "agent-x"
        _write_golden(agent_dir)

        runner = EvalRunner("agent-x")

        assert runner._load_cached_output() is None

    def test_picks_newest_and_skips_corrupt_files(self, agents_dir):
        agent_dir = agents_dir / "agent-x"
        _write_golden(agent_dir)
        out_dir = agent_dir / "evals" / "output"
        out_dir.mkdir(parents=True)
        # Lex-sorted newest is z_*. Reversed iteration tries z first.
        # Z is corrupt -> falls back to y; y is valid.
        (out_dir / "y_old.json").write_text('{"total_images": 3}', encoding="utf-8")
        (out_dir / "z_new.json").write_text("not valid json", encoding="utf-8")

        runner = EvalRunner("agent-x")
        result = runner._load_cached_output()

        assert result == {"total_images": 3}


class TestEvalAgentCached:
    """live=False path: cache miss vs. cache hit threading through."""

    async def test_cache_miss_surfaces_explicit_failure_reason(self, agents_dir):
        agent_dir = agents_dir / "vision-image-analyzer"
        _write_golden(agent_dir)

        runner = EvalRunner("vision-image-analyzer")
        result = await runner.eval_agent(live=False)

        assert result.failure_reason == "cache_miss"
        assert result.schema_valid is False
        # The error message points users at the fix.
        assert "Run with --live" in result.schema_error
        # No facts were checked, so the failed_facts list flags the absence.
        assert result.failed_facts == ["No output available"]

    async def test_cache_hit_validates_and_passes_key_facts(self, agents_dir):
        agent_dir = agents_dir / "vision-image-analyzer"
        _write_golden(agent_dir)
        out_dir = agent_dir / "evals" / "output"
        out_dir.mkdir(parents=True)
        # Schema vision_analysis -> total_images is the asserted field.
        (out_dir / "cached.json").write_text(json.dumps({"total_images": 5}),
                                             encoding="utf-8")

        runner = EvalRunner("vision-image-analyzer")
        result = await runner.eval_agent(live=False)

        assert result.failure_reason == ""
        assert result.schema_valid is True
        assert result.passed_facts == 1
        assert result.total_facts == 1


class TestEvalAgentLive:
    """live=True path: input + agent + parse pipeline failure modes."""

    async def test_missing_input_returns_live_input_missing(self, agents_dir):
        # Golden has no input_file and no input.md sibling, no images.
        agent_dir = agents_dir / "agent-x"
        _write_golden(agent_dir)

        runner = EvalRunner("agent-x")
        result = await runner.eval_agent(live=True)

        assert result.failure_reason == "live_input_missing"
        assert result.schema_valid is False

    async def test_agent_init_error_surfaces_as_failure_reason(
            self, agents_dir, monkeypatch):
        agent_dir = agents_dir / "vision-image-analyzer"
        _write_golden(agent_dir)
        # Provide an input so we get past the input-missing guard.
        (agent_dir / "evals" / "input.md").write_text("analyze this", encoding="utf-8")

        runner = EvalRunner("vision-image-analyzer")
        # Stub out _build_model so we don't try to load llm_config.
        monkeypatch.setattr(runner, "_build_model", lambda: object())

        with patch(
                "gptase.agents.base.Agent.from_markdown",
                side_effect=AgentInitializationError("missing agent"),
        ):
            result = await runner.eval_agent(live=True)

        assert result.failure_reason == "agent_init_error"
        assert result.schema_valid is False
        assert result.schema_error == "missing agent"

    async def test_text_output_is_wrapped_for_markdown_agents(
            self, agents_dir, monkeypatch):
        # Markdown-only agents (e.g. deep-research) emit prose, not JSON.
        # The runner wraps it as {"content": <text>} so assertions
        # targeting "content" still resolve.
        agent_dir = agents_dir / "deep-research"
        evals_dir = agent_dir / "evals"
        evals_dir.mkdir(parents=True, exist_ok=True)
        (evals_dir / "golden.yaml").write_text(
            "schema: deep_research\n"
            "key_facts:\n"
            "  - field: content\n"
            "    condition: contains\n"
            "    value: not json\n",
            encoding="utf-8",
        )
        (evals_dir / "input.md").write_text("research this topic", encoding="utf-8")

        runner = EvalRunner("deep-research")
        monkeypatch.setattr(runner, "_build_model", lambda: object())

        class FakeAgent:

            async def run(self, content, image_paths=None):
                return {"status": "success", "data": {"content": "not json"}}

        with patch("gptase.agents.base.Agent.from_markdown", return_value=FakeAgent()):
            result = await runner.eval_agent(live=True)

        assert result.failure_reason == ""
        assert result.schema_valid is True
        assert result.passed_facts == 1


class TestBuildModel:
    """Custom llm_config path branch."""

    def test_missing_config_path_raises_filenotfound(self, agents_dir):
        agent_dir = agents_dir / "agent-x"
        _write_golden(agent_dir)

        runner = EvalRunner("agent-x", config_path="/no/such/llm.json")

        with pytest.raises(FileNotFoundError) as exc:
            runner._build_model()

        assert "/no/such/llm.json" in str(exc.value)


class TestRunEvalConvenience:
    """run_eval == EvalRunner(...).eval_agent(...)."""

    async def test_run_eval_returns_eval_result(self, agents_dir):
        agent_dir = agents_dir / "vision-image-analyzer"
        _write_golden(agent_dir)

        result = await run_eval("vision-image-analyzer", live=False)

        assert isinstance(result, EvalResult)
        # No cache -> cache_miss; pinning the convenience wrapper's
        # passthrough rather than re-testing the runner internals.
        assert result.failure_reason == "cache_miss"
