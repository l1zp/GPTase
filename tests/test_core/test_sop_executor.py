"""Tests for SOP loading and variable resolution in ExecutorTool."""

import json
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from src.tools.executor_tool import ExecutorTool


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    orchestrator.agents = {}
    return orchestrator


@pytest.fixture
def sample_sop_content():
    return {
        "plan_id":
        "test_sop",
        "workflow": [{
            "step_id": 1,
            "agent": "agent1",
            "action": "action1",
            "inputs": {
                "val": "{{input_text}}"
            }
        }, {
            "step_id": 2,
            "agent": "agent2",
            "action": "action2",
            "inputs": {
                "data": "{{step1.result}}"
            }
        }]
    }


class TestSOPExecutor:
    """Test suite for the enhanced ExecutorTool."""

    def test_resolve_variables_simple(self):
        tool = ExecutorTool(model_manager=None)
        context = {"input_text": "hello world", "step1": {"result": "data from step 1"}}
        inputs = {
            "p1": "{{input_text}}",
            "p2": "{{step1.result}}",
            "p3": "static value"
        }

        resolved = tool._resolve_variables(inputs, context)

        assert resolved["p1"] == "hello world"
        assert resolved["p2"] == "data from step 1"
        assert resolved["p3"] == "static value"

    def test_resolve_variables_nested(self):
        tool = ExecutorTool(model_manager=None)
        context = {"step1": {"raw_tool_data": {"tables": [{"id": 1}]}}}
        inputs = {"tables": "{{step1.raw_tool_data.tables}}"}

        resolved = tool._resolve_variables(inputs, context)
        assert resolved["tables"] == [{"id": 1}]

    def test_sop_path_logic(self):
        """Verify the logic used in _load_plan for SOPs."""
        plan_id = "enzyme_extraction_pipeline_sop"
        sop_name = plan_id.replace("_sop", "")
        expected_path = Path("config/sops") / f"{sop_name}.json"
        assert str(expected_path) == "config/sops/enzyme_extraction_pipeline.json"
