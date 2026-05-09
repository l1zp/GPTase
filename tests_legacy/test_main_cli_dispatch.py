"""Tests for CLI dispatch request wiring."""

import argparse
from pathlib import Path

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
