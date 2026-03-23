"""Tests for memory-related CLI helpers."""

import argparse

import pytest

from gptase import main


@pytest.mark.asyncio
async def test_show_agent_memory_prints_summary(monkeypatch, capsys):
    class FakeOrchestrator:
        def __init__(self, config):
            self.config = config

        async def get_agent_working_memory(self, agent_id):
            return {
                "agent_id": agent_id,
                "working_memory": {
                    "summary": "Remember prior results",
                    "metadata": {
                        "status": "success"
                    },
                    "last_updated": "2026-03-23T12:00:00",
                },
            }

    monkeypatch.setattr(main, "AgentOrchestrator", FakeOrchestrator)
    args = argparse.Namespace(agent="memory-agent")

    exit_code = await main.show_agent_memory(args)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Agent Memory: memory-agent" in output
    assert "Remember prior results" in output


def test_parse_args_memory_command(monkeypatch):
    monkeypatch.setattr("sys.argv", ["gptase", "memory", "--agent", "memory-agent"])
    args = main.parse_args()

    assert args.command == "memory"
    assert args.agent == "memory-agent"
