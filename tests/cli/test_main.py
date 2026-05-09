"""Unit tests for gptase.main CLI entry point.

Test layers:

* ``TestDetectSupplementaryPath`` — pure filesystem-walk helper, no
  mocks needed; uses ``tmp_path`` for fixture data.
* ``TestParseArgs`` — argparse subcommand wiring; uses ``monkeypatch``
  on ``sys.argv``.
* ``TestDumpChatPlanArtifacts`` — pure JSON-dump helper, asserted by
  reading the files back.
* ``TestRunChat`` — only the early-return validation paths
  (plan-without-input, missing plan file). The orchestrator-using
  success path requires module-level patching of AgentOrchestrator
  and is already covered by core/orchestrator tests.
* ``TestRunAgent`` — early-return guard for missing description.

Heavy orchestrator wrappers (``list_agents``, ``show_status``,
``show_agent_memory``) are intentionally skipped: they're thin
forwarding to AgentOrchestrator methods that already have direct
unit tests.
"""
import argparse
import json

import pytest

from gptase.main import _detect_supplementary_path
from gptase.main import _dump_chat_plan_artifacts
from gptase.main import parse_args
from gptase.main import run_agent
from gptase.main import run_chat


class TestDetectSupplementaryPath:
    """Best-effort SI-document discovery — sibling file + SI-named subdirs."""

    def test_empty_or_missing_path_returns_none(self, tmp_path):
        assert _detect_supplementary_path("") is None
        assert _detect_supplementary_path(str(tmp_path / "no.md")) is None

    def test_sibling_si_file_takes_priority(self, tmp_path):
        # Layout: paper.md + paper_si.md side by side.
        paper = tmp_path / "paper.md"
        paper.write_text("body", encoding="utf-8")
        si = tmp_path / "paper_si.md"
        si.write_text("supplementary", encoding="utf-8")

        assert _detect_supplementary_path(str(paper)) == str(si)

    def test_si_subdir_with_main_md_resolves(self, tmp_path):
        # Layout: paper.md alone, sibling subdir SI_2024/main.md.
        paper = tmp_path / "paper.md"
        paper.write_text("body", encoding="utf-8")
        si_dir = tmp_path / "SI_2024"
        si_dir.mkdir()
        main = si_dir / "main.md"
        main.write_text("si body", encoding="utf-8")

        assert _detect_supplementary_path(str(paper)) == str(main)

    def test_si_subdir_without_main_md_is_skipped(self, tmp_path):
        # SI dir exists but no main.md inside -> not a usable SI source.
        paper = tmp_path / "paper.md"
        paper.write_text("body", encoding="utf-8")
        si_dir = tmp_path / "SI_2024"
        si_dir.mkdir()
        # Drop a non-main file so the dir isn't empty.
        (si_dir / "other.md").write_text("x", encoding="utf-8")

        assert _detect_supplementary_path(str(paper)) is None

    def test_moesm_pattern_recognized(self, tmp_path):
        # Nature/Springer's "MOESM<N>_*" subdir convention is in the
        # pattern list — must be honored.
        paper = tmp_path / "paper.md"
        paper.write_text("body", encoding="utf-8")
        si_dir = tmp_path / "MOESM1_ESM"
        si_dir.mkdir()
        main = si_dir / "main.md"
        main.write_text("si body", encoding="utf-8")

        assert _detect_supplementary_path(str(paper)) == str(main)


class TestParseArgs:
    """Sub-command argparse wiring (argv -> Namespace)."""

    def test_chat_subcommand_with_plan_and_input_and_output(self, monkeypatch):
        monkeypatch.setattr("sys.argv", [
            "gptase",
            "chat",
            "-p",
            "enzyme_extraction_pipeline",
            "-i",
            "paper.md",
            "-o",
            "out/",
        ])

        args = parse_args()

        assert args.command == "chat"
        assert args.plan == "enzyme_extraction_pipeline"
        assert args.input == "paper.md"
        assert args.output == "out/"
        assert args.description is None  # positional, defaulted

    def test_agent_subcommand_requires_name(self, monkeypatch, capsys):
        # Missing --name causes argparse to exit with code 2 and stderr.
        monkeypatch.setattr("sys.argv", ["gptase", "agent"])

        with pytest.raises(SystemExit) as exc:
            parse_args()
        assert exc.value.code == 2

    def test_eval_subcommand_optional_flags(self, monkeypatch):
        monkeypatch.setattr("sys.argv", [
            "gptase",
            "eval",
            "-a",
            "vision-image-analyzer",
            "--live",
            "--save-output",
            "--save",
            "report.json",
        ])

        args = parse_args()

        assert args.command == "eval"
        assert args.agent == "vision-image-analyzer"
        assert args.live is True
        assert args.save_output is True
        assert args.save == "report.json"


class TestDumpChatPlanArtifacts:
    """Plan-driven coordinator result -> workspace artifacts on disk."""

    def test_writes_plan_result_json_to_workspace(self, tmp_path):
        result = {
            "task_id": "t1",
            "status": "success",
            "data": {
                "content": "answer"
            },
        }
        _dump_chat_plan_artifacts(str(tmp_path), "my_plan", result)

        out = tmp_path / "my_plan_result.json"
        assert out.exists()
        round_trip = json.loads(out.read_text(encoding="utf-8"))
        assert round_trip["task_id"] == "t1"
        assert round_trip["data"]["content"] == "answer"

    def test_writes_per_worker_files_per_turn(self, tmp_path):
        # Coordinator made two delegations across two turns. Each
        # worker_result lands in its own JSON file under worker_results/.
        result = {
            "task_id": "t1",
            "status": "success",
            "trace": {
                "runtime": {
                    "coordinator": {
                        "turns": [
                            {
                                "turn_index":
                                1,
                                "worker_results": [
                                    {
                                        "agent_id": "agent-a",
                                        "status": "success",
                                        "content": "first"
                                    },
                                ],
                            },
                            {
                                "turn_index":
                                2,
                                "worker_results": [
                                    {
                                        "agent_id": "agent/b",  # slash sanitized
                                        "status": "success",
                                        "content": "second"
                                    },
                                ],
                            },
                        ],
                    },
                },
            },
        }

        _dump_chat_plan_artifacts(str(tmp_path), "p", result)

        worker_dir = tmp_path / "worker_results"
        assert worker_dir.exists()
        files = sorted(p.name for p in worker_dir.iterdir())
        # Naming: turn<N>_<idx>_<agent_id>.json with slash replaced by _.
        assert files == ["turn1_00_agent-a.json", "turn2_00_agent_b.json"]
        first = json.loads((worker_dir / files[0]).read_text(encoding="utf-8"))
        assert first["agent_id"] == "agent-a"
        assert first["content"] == "first"

    def test_no_turns_means_no_worker_dir_created(self, tmp_path):
        # Coordinator never delegated -> only the top-level result.json.
        result = {
            "task_id": "t1",
            "status": "success",
            "trace": {
                "runtime": {
                    "coordinator": {
                        "turns": []
                    }
                }
            }
        }

        _dump_chat_plan_artifacts(str(tmp_path), "p", result)

        assert (tmp_path / "p_result.json").exists()
        assert not (tmp_path / "worker_results").exists()


class TestRunChat:
    """Plan-branch validation guards — early returns, no orchestrator hit."""

    async def test_plan_without_input_returns_1(self, tmp_path):
        args = argparse.Namespace(
            description=None,
            plan="my_plan",
            input=None,
            output=None,
            si=None,
            debug=False,
        )

        rc = await run_chat(args)

        assert rc == 1

    async def test_plan_file_missing_returns_1(self, tmp_path, monkeypatch):
        # Provide a real input file so we get past the input check,
        # but point the project root at tmp_path so config/plans/<id>.md
        # doesn't resolve.
        doc = tmp_path / "paper.md"
        doc.write_text("body", encoding="utf-8")

        # Stub get_paths so plan_path lookups land under tmp_path.
        class FakePaths:
            project_root = tmp_path

        monkeypatch.setattr("gptase.utils.paths.get_paths", lambda: FakePaths())

        args = argparse.Namespace(
            description=None,
            plan="nonexistent",
            input=str(doc),
            output=None,
            si=None,
            debug=False,
        )

        rc = await run_chat(args)

        assert rc == 1


class TestRunAgent:
    """run_agent's early-return guard."""

    async def test_no_description_returns_1(self):
        args = argparse.Namespace(
            name="some-agent",
            description=None,
            debug=False,
        )

        rc = await run_agent(args)

        assert rc == 1
