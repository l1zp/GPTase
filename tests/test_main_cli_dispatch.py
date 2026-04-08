"""Tests for CLI dispatch request wiring."""

import argparse

from gptase import main
from gptase.core.types import DispatchRequest


class TestRunChat:
    """Tests for chat CLI dispatch behavior."""

    async def test_run_chat_uses_dispatch_request(self, monkeypatch, capsys):
        captured = {}

        class FakeOrchestrator:

            def __init__(self, config):
                self.config = config

            async def dispatch(self, request):
                captured["request"] = request
                return {"status": "completed", "data": {"content": "chat output"}}

            async def close(self):
                captured["closed"] = True

        monkeypatch.setattr(main, "AgentOrchestrator", FakeOrchestrator)
        args = argparse.Namespace(description="hello", debug=False)

        exit_code = await main.run_chat(args)

        output = capsys.readouterr().out
        assert exit_code == 0
        assert output.strip() == "chat output"
        assert captured["closed"] is True
        assert isinstance(captured["request"], DispatchRequest)
        assert captured["request"].query == "hello"
        assert captured["request"].auto_execute is True


class TestPlanResume:
    """Tests for plan resume CLI dispatch behavior."""

    async def test_plan_resume_uses_dispatch_request(self, monkeypatch):
        captured = {}

        class FakeOrchestrator:

            def __init__(self, config):
                self.config = config

            async def dispatch(self, request):
                captured["request"] = request
                return {"status": "completed"}

            async def close(self):
                captured["closed"] = True

        def fake_write_harness_result(result, output_dir_arg, output_name):
            captured["result"] = result
            captured["output_dir_arg"] = output_dir_arg
            captured["output_name"] = output_name
            return 0

        monkeypatch.setattr(main, "AgentOrchestrator", FakeOrchestrator)
        monkeypatch.setattr(main, "_write_harness_result", fake_write_harness_result)
        args = argparse.Namespace(session_id="sess-123",
                                  feedback="continue",
                                  review=False,
                                  auto_replan=True)

        exit_code = await main._plan_resume(args, registry=None)

        request = captured["request"]
        assert exit_code == 0
        assert captured["closed"] is True
        assert isinstance(request, DispatchRequest)
        assert request.session_id == "sess-123"
        assert request.feedback == "continue"
        assert request.approve_plan is True
        assert request.auto_replan is True
        assert captured["output_name"] == "sess-123"


class TestPlanRun:
    """Tests for plan run CLI dispatch behavior."""

    async def test_plan_run_passes_document_path_and_text(self, monkeypatch, tmp_path):
        captured = {}
        input_path = tmp_path / "paper.md"
        input_path.write_text("paper body", encoding="utf-8")
        workspace_dir = tmp_path / "plan-workspace"

        class FakeProjectPaths:

            def get_plan_output_dir(self, document_name, plan_id):
                captured["document_name"] = document_name
                captured["plan_id"] = plan_id
                return workspace_dir

        class FakeOrchestrator:

            def __init__(self, config):
                self.config = config

            async def dispatch(self, request):
                captured["request"] = request
                return {"status": "completed"}

            async def close(self):
                captured["closed"] = True

        def fake_write_harness_result(result, output_dir_arg, output_name):
            captured["result"] = result
            captured["output_dir_arg"] = output_dir_arg
            captured["output_name"] = output_name
            return 0

        monkeypatch.setattr(main, "AgentOrchestrator", FakeOrchestrator)
        monkeypatch.setattr(main, "_write_harness_result", fake_write_harness_result)
        monkeypatch.setattr("gptase.utils.paths.ProjectPaths", FakeProjectPaths)
        args = argparse.Namespace(plan="enzyme_extraction_pipeline",
                                  output=None,
                                  review=False,
                                  auto_replan=False,
                                  input=str(input_path),
                                  debug=False)

        exit_code = await main._plan_run(args, registry=None)

        request = captured["request"]
        assert exit_code == 0
        assert captured["closed"] is True
        assert workspace_dir.exists()
        assert isinstance(request, DispatchRequest)
        assert request.plan_id == "enzyme_extraction_pipeline"
        assert request.query == "Execute draft plan enzyme_extraction_pipeline"
        assert request.input_data == {"text": "paper body"}
        assert request.document_path == str(input_path)
        assert request.workspace_dir == str(workspace_dir)
        assert request.auto_execute is True
        assert request.auto_replan is False
        assert captured["output_dir_arg"] == str(workspace_dir)
        assert captured["output_name"] == "enzyme_extraction_pipeline"

    async def test_plan_run_returns_error_for_missing_input(self, tmp_path):
        args = argparse.Namespace(plan="enzyme_extraction_pipeline",
                                  output=None,
                                  review=False,
                                  auto_replan=False,
                                  input=str(tmp_path / "missing.md"),
                                  debug=False)

        exit_code = await main._plan_run(args, registry=None)

        assert exit_code == 1
