"""Unit tests for gptase.evals.report.

Six cases covering both formatters:

* ``print_eval_report`` — stdout formatter; assertions use capsys.
* ``save_eval_report`` — JSON file with overall summary + per-agent
  details; assertions parse the JSON back.

The legacy suite shipped two cases (failure_reason in JSON +
failure_reason in stdout); both ported.
"""
import json

from gptase.evals.assertions import EvalResult
from gptase.evals.report import print_eval_report
from gptase.evals.report import save_eval_report


def _ok_result(name: str = "agent-x", passed: int = 3, total: int = 3) -> EvalResult:
    return EvalResult(
        agent_name=name,
        schema_valid=True,
        schema_error="",
        total_facts=total,
        passed_facts=passed,
    )


def _failed_result(name: str = "agent-x", reason: str = "parse_error") -> EvalResult:
    return EvalResult(
        agent_name=name,
        schema_valid=False,
        schema_error="Could not parse JSON from agent output",
        total_facts=1,
        passed_facts=0,
        failure_reason=reason,
        failed_facts=["No output available"],
    )


class TestPrintEvalReport:
    """stdout formatter — verified via capsys."""

    def test_empty_results_short_circuits_with_message(self, capsys):
        print_eval_report([])

        out = capsys.readouterr().out
        assert "No results to report" in out

    def test_table_includes_schema_status_facts_and_score(self, capsys):
        print_eval_report([_ok_result(name="vision", passed=3, total=4)])

        out = capsys.readouterr().out
        # Status flag, fraction, and 2-decimal score all present on one row.
        assert "vision" in out
        assert "[OK]" in out
        assert "3/4" in out
        assert "0.75" in out
        # Overall summary line.
        assert "Overall: 3/4 key facts passed (0.75)" in out

    def test_failure_section_includes_failure_reason_when_present(self, capsys):
        # When schema_valid is False AND failure_reason is set, the
        # [WARNING] line embeds the reason between agent name and error.
        print_eval_report([_failed_result(reason="cache_miss")])

        out = capsys.readouterr().out
        assert "[FAIL]" in out  # failed schema status flag
        assert "cache_miss" in out
        assert "[WARNING]" in out


class TestSaveEvalReport:
    """JSON file output — round-trip via json.loads."""

    def test_saves_json_with_overall_and_per_agent_sections(self, tmp_path):
        path = tmp_path / "report.json"

        save_eval_report(
            [
                _ok_result(name="agent-a", passed=2, total=2),
                _ok_result(name="agent-b", passed=1, total=2),
            ],
            str(path),
        )

        report = json.loads(path.read_text(encoding="utf-8"))
        # Top-level agent_name comes from the first result.
        assert report["agent_name"] == "agent-a"
        # Overall aggregates across all agents.
        assert report["overall"]["total_facts"] == 4
        assert report["overall"]["passed_facts"] == 3
        assert report["overall"]["score"] == 0.75
        # Per-agent rows preserve order + carry their own scores.
        assert [a["agent_name"] for a in report["agents"]] == ["agent-a", "agent-b"]
        assert report["agents"][1]["score"] == 0.5

    def test_failure_reason_included_in_per_agent(self, tmp_path):
        # Legacy contract: the failure_reason field must round-trip
        # through the JSON report so downstream tooling can route on it.
        path = tmp_path / "report.json"

        save_eval_report([_failed_result(reason="parse_error")], str(path))

        report = json.loads(path.read_text(encoding="utf-8"))
        assert report["agents"][0]["failure_reason"] == "parse_error"
        assert report["agents"][0]["schema_valid"] is False
        assert report["agents"][0]["failed_facts"] == ["No output available"]

    def test_creates_parent_directories_on_demand(self, tmp_path):
        # Save into a path whose parent doesn't exist — the function
        # should mkdir(parents=True) rather than crash.
        path = tmp_path / "deep" / "nested" / "report.json"

        save_eval_report([_ok_result()], str(path))

        assert path.exists()
        # Round-trips cleanly.
        json.loads(path.read_text(encoding="utf-8"))
