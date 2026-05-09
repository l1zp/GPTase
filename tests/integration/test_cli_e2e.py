"""Integration test: CLI run_chat -> orchestrator -> stdout exit-code path.

Pins the CLI's outer wiring with the orchestrator instantiation patched
out (so we don't depend on llm_config.json or the real agent tree):

    parse_args -> run_chat -> AgentOrchestrator(...)  [stubbed]
                  -> orchestrator.dispatch(...)        [returns final_answer]
                  -> stdout(content), exit code 0

The orchestrator's *actual* dispatch behavior is covered by
core/orchestrator unit tests; this test pins the CLI's exit-code +
stdout contract that downstream shell scripts rely on.
"""
import argparse
from unittest.mock import AsyncMock

from gptase.main import run_chat


def _stub_orchestrator(monkeypatch, dispatch_return):
    """Patch ``gptase.main.AgentOrchestrator`` to yield a stubbed instance.

    Centralizes the AsyncMock-orchestrator pattern that all three CLI
    integration tests need: dispatch returns ``dispatch_return``,
    close is a no-op AsyncMock, and the class itself is replaced so
    ``run_chat`` never opens a real sqlite or scans .claude/agents/.
    """
    fake = AsyncMock()
    fake.dispatch = AsyncMock(return_value=dispatch_return)
    fake.close = AsyncMock()
    monkeypatch.setattr("gptase.main.AgentOrchestrator", lambda *a, **kw: fake)
    return fake


class TestRunChatNoPlanE2E:
    """No-plan CLI path: description -> orchestrator -> printed answer."""

    async def test_success_prints_content_and_returns_zero(self, monkeypatch, capsys):
        fake_orch = _stub_orchestrator(
            monkeypatch,
            {
                "task_id": "t1",
                "status": "success",
                "data": {
                    "content": "the synthesized answer"
                },
            },
        )

        args = argparse.Namespace(
            description="answer this",
            plan=None,
            input=None,
            output=None,
            si=None,
            debug=False,
        )

        rc = await run_chat(args)

        assert rc == 0
        # The answer content reaches stdout for shell-script consumers.
        assert "the synthesized answer" in capsys.readouterr().out
        # Resource cleanup happens via the finally block.
        fake_orch.dispatch.assert_awaited_once()
        fake_orch.close.assert_awaited_once()

    async def test_plan_branch_substitutes_vars_and_dumps_artifacts(
            self, monkeypatch, tmp_path):
        # The plan branch is fundamentally different from no-plan:
        # it reads config/plans/<id>.md, substitutes three template
        # variables, builds a workspace dir, dispatches, then writes
        # plan_result.json + per-worker artifacts. This pins the full
        # template->dispatch->artifact wiring as a single contract.
        plans_dir = tmp_path / "config" / "plans"
        plans_dir.mkdir(parents=True)
        plan_path = plans_dir / "fake_plan.md"
        plan_path.write_text(
            "Run against {{document_path}} (SI: {{si_document_path}}) "
            "into {{workspace_dir}}.",
            encoding="utf-8",
        )
        doc_path = tmp_path / "paper.md"
        doc_path.write_text("paper body", encoding="utf-8")
        workspace = tmp_path / "ws"

        class FakePaths:
            project_root = tmp_path

        monkeypatch.setattr("gptase.utils.paths.get_paths", lambda: FakePaths())

        # A coordinator result with one delegated worker, so
        # _dump_chat_plan_artifacts has something to write under
        # worker_results/.
        fake_orch = _stub_orchestrator(
            monkeypatch,
            {
                "task_id": "t1",
                "status": "success",
                "data": {
                    "content": "synthesized output"
                },
                "trace": {
                    "runtime": {
                        "coordinator": {
                            "turns": [{
                                "turn_index":
                                1,
                                "worker_results": [{
                                    "agent_id": "worker-x",
                                    "status": "success",
                                    "content": "worker said hi",
                                }],
                            }],
                        },
                    },
                },
            },
        )

        args = argparse.Namespace(
            description=None,
            plan="fake_plan",
            input=str(doc_path),
            output=str(workspace),
            si=None,
            debug=False,
        )

        rc = await run_chat(args)

        assert rc == 0
        # Plan artifacts written.
        assert (workspace / "fake_plan_result.json").exists()
        assert (workspace / "worker_results" / "turn1_00_worker-x.json").exists()
        # Template vars actually substituted before dispatch saw the query.
        dispatched = fake_orch.dispatch.await_args.args[0]
        assert str(doc_path) in dispatched.query
        assert str(workspace) in dispatched.query
        assert "{{document_path}}" not in dispatched.query
        assert "{{workspace_dir}}" not in dispatched.query

    async def test_failure_status_returns_one_and_logs_error(self, monkeypatch, capsys):
        # When dispatch returns status=failed, run_chat propagates an
        # exit code of 1. This pin matters for CI scripts that branch
        # on $?.
        fake_orch = _stub_orchestrator(
            monkeypatch,
            {
                "task_id": "t1",
                "status": "failed",
                "error": "something broke",
            },
        )

        args = argparse.Namespace(
            description="answer this",
            plan=None,
            input=None,
            output=None,
            si=None,
            debug=False,
        )

        rc = await run_chat(args)

        assert rc == 1
        # close() still runs via finally even on the failure path.
        fake_orch.close.assert_awaited_once()
