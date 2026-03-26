"""Tests for the eval framework."""

import json
from pathlib import Path
from unittest.mock import patch

from gptase.evals.assertions import _check_condition
from gptase.evals.assertions import EvalResult
from gptase.evals.assertions import extract_field
from gptase.evals.report import print_eval_report
from gptase.evals.report import save_eval_report
from gptase.evals.runner import EvalRunner
from gptase.utils.exceptions import AgentInitializationError


def _write_golden(agent_dir: Path, schema: str = "vision_analysis") -> None:
    """Create a minimal golden.yaml for eval tests."""
    evals_dir = agent_dir / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)
    (evals_dir / "golden.yaml").write_text(
        f"schema: {schema}\nkey_facts:\n  - field: total_images\n    condition: gte\n    value: 1\n",
        encoding="utf-8",
    )


class TestExtractField:
    """Tests for the field extraction DSL."""

    def test_extracts_dotted_path(self):
        """Test dotted field traversal."""
        data = {"statistics": {"total_variants": 13}}

        result = extract_field(data, "statistics.total_variants")

        assert result == 13

    def test_extracts_wildcard_path(self):
        """Test wildcard list traversal."""
        data = {"reactions": [{"enzyme_name": "Des27"}, {"enzyme_name": "Des27.7"}]}

        result = extract_field(data, "reactions[*].enzyme_name")

        assert result == ["Des27", "Des27.7"]

    def test_extracts_filter_path(self):
        """Test filtered list traversal."""
        data = {
            "reactions": [
                {"enzyme_name": "Des27", "kinetics": {"kcat/KM": 131}},
                {"enzyme_name": "Des27.7", "kinetics": {"kcat/KM": 150}},
            ]
        }

        result = extract_field(data, "reactions[enzyme_name=Des27].kinetics.kcat/KM")

        assert result == 131

    def test_extracts_index_path(self):
        """Test indexed list traversal."""
        data = {"reactions": [{"enzyme_name": "Des27"}, {"enzyme_name": "Des27.7"}]}

        result = extract_field(data, "reactions[1].enzyme_name")

        assert result == "Des27.7"

    def test_extracts_keys_containing_dots(self):
        """Test dotted_get can resolve literal keys that contain dots."""
        data = {"statistics": {"kcat.KM": 42}}

        result = extract_field(data, "statistics.kcat.KM")

        assert result == 42


class TestAssertionConditions:
    """Tests for eval assertion condition semantics."""

    def test_contains_all_matches_substrings_across_list_items(self):
        """Test contains_all uses substring matching for list items."""
        actual = ["variant,score\nDes27.2,1\nDes27.7,2", "variant,score\nDes27.9,3"]

        ok, reason = _check_condition(
            actual,
            "contains_all",
            {"values": ["Des27.2", "Des27.7", "Des27.9"]},
        )

        assert ok is True
        assert reason == ""

    def test_contains_any_matches_substrings_across_list_items(self):
        """Test contains_any uses substring matching for list items."""
        actual = ["KM = 0.21 mM", "kcat = 2.85 s-1"]

        ok, reason = _check_condition(
            actual,
            "contains_any",
            {"values": ["12,696", "2.85"]},
        )

        assert ok is True
        assert reason == ""

    def test_contains_all_reports_missing_values(self):
        """Test contains_all failure message includes missing values."""
        actual = ["Des27.2", "Des27.7"]

        ok, reason = _check_condition(
            actual,
            "contains_all",
            {"values": ["Des27.2", "Des27.9"]},
        )

        assert ok is False
        assert "Des27.9" in reason


class TestEvalRunner:
    """Tests for EvalRunner behavior."""

    def test_resolves_hyphen_and_underscore_agent_names(self, tmp_path, monkeypatch):
        """Test eval runner accepts underscore names for hyphenated agent dirs."""
        agent_dir = tmp_path / "vision-image-analyzer"
        _write_golden(agent_dir)
        monkeypatch.setattr("gptase.evals.runner._AGENTS_DIR", tmp_path)

        runner = EvalRunner("vision_image_analyzer")

        assert runner.resolved_agent_name == "vision-image-analyzer"
        assert runner.evals_dir == agent_dir / "evals"

    async def test_cached_eval_reports_cache_miss(self, tmp_path, monkeypatch):
        """Test cache miss is surfaced as an explicit failure reason."""
        agent_dir = tmp_path / "vision-image-analyzer"
        _write_golden(agent_dir)
        monkeypatch.setattr("gptase.evals.runner._AGENTS_DIR", tmp_path)

        runner = EvalRunner("vision-image-analyzer")

        result = await runner.eval_agent(live=False)

        assert result.failure_reason == "cache_miss"
        assert result.schema_valid is False
        assert "Run with --live" in result.schema_error

    async def test_live_eval_returns_agent_init_error(self, tmp_path, monkeypatch):
        """Test live eval converts agent init failures into EvalResult failures."""
        agent_dir = tmp_path / "vision-image-analyzer"
        _write_golden(agent_dir)
        evals_dir = agent_dir / "evals"
        (evals_dir / "input.md").write_text("analyze this figure", encoding="utf-8")
        monkeypatch.setattr("gptase.evals.runner._AGENTS_DIR", tmp_path)

        runner = EvalRunner("vision-image-analyzer")
        monkeypatch.setattr(runner, "_build_model", lambda: object())

        with patch(
            "gptase.agents.base.Agent.from_markdown",
            side_effect=AgentInitializationError("missing agent"),
        ):
            result = await runner.eval_agent(live=True)

        assert result.failure_reason == "agent_init_error"
        assert result.schema_valid is False
        assert result.schema_error == "missing agent"

    async def test_live_eval_returns_parse_error(self, tmp_path, monkeypatch):
        """Test live eval distinguishes JSON parse failures from other errors."""
        agent_dir = tmp_path / "vision-image-analyzer"
        _write_golden(agent_dir)
        evals_dir = agent_dir / "evals"
        (evals_dir / "input.md").write_text("analyze this figure", encoding="utf-8")
        monkeypatch.setattr("gptase.evals.runner._AGENTS_DIR", tmp_path)

        runner = EvalRunner("vision-image-analyzer")
        monkeypatch.setattr(runner, "_build_model", lambda: object())

        class FakeAgent:
            async def run(self, content, image_paths=None):
                return {"status": "success", "data": {"content": "not json"}}

        with patch("gptase.agents.base.Agent.from_markdown", return_value=FakeAgent()):
            result = await runner.eval_agent(live=True)

        assert result.failure_reason == "parse_error"
        assert result.schema_valid is False
        assert result.schema_error == "Could not parse JSON from agent output"


class TestEvalReport:
    """Tests for eval report generation."""

    def test_save_eval_report_includes_failure_reason(self, tmp_path):
        """Test JSON report contains the failure_reason field."""
        output_path = tmp_path / "report.json"

        save_eval_report(
            [
                EvalResult(
                    agent_name="vision-image-analyzer",
                    schema_valid=False,
                    schema_error="Could not parse JSON from agent output",
                    total_facts=1,
                    passed_facts=0,
                    failure_reason="parse_error",
                    failed_facts=["No output available"],
                )
            ],
            str(output_path),
        )

        report = json.loads(output_path.read_text(encoding="utf-8"))

        assert report["agents"][0]["failure_reason"] == "parse_error"

    def test_print_eval_report_shows_failure_reason(self, capsys):
        """Test console report prints explicit failure reasons."""
        result = EvalResult(
            agent_name="vision-image-analyzer",
            schema_valid=False,
            schema_error="Could not parse JSON from agent output",
            total_facts=1,
            passed_facts=0,
            failure_reason="parse_error",
            failed_facts=[],
        )

        print_eval_report([result])
        output = capsys.readouterr().out

        assert "parse_error" in output
        assert "Could not parse JSON from agent output" in output
