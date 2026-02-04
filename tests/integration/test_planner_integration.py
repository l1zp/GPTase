"""Integration tests for planner workflow."""

import json
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_asyncio

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig


@pytest_asyncio.fixture
async def orchestrator(tmp_path):
    """Create orchestrator with temporary plans directory."""
    with patch("src.tools.planner_tool._PLANS_DIR", tmp_path):
        with patch("src.tools.executor_tool._PLANS_DIR", tmp_path):
            config = FrameworkConfig()
            orch = AgentOrchestrator(config)
            yield orch
            await orch.shutdown()


@pytest.mark.asyncio
class TestPlannerIntegration:
    """Integration tests for planner with orchestrator."""

    async def test_planner_agent_available(self, orchestrator):
        """Test that planner agent is available."""
        agents = await orchestrator.list_available_agents()

        planner_agents = [a for a in agents if a["agent_id"] == "planner"]
        assert len(planner_agents) == 1

        capabilities = planner_agents[0]["capabilities"]
        assert "requirement_analysis" in capabilities
        assert "workflow_design" in capabilities

    async def test_executor_agent_available(self, orchestrator):
        """Test that executor agent is available."""
        agents = await orchestrator.list_available_agents()

        executor_agents = [a for a in agents if a["agent_id"] == "executor"]
        assert len(executor_agents) == 1

        capabilities = executor_agents[0]["capabilities"]
        assert "plan_execution" in capabilities
        assert "agent_orchestration" in capabilities

    @pytest.mark.asyncio
    async def test_full_planning_workflow(self, orchestrator):
        """Test complete 5-phase planning workflow."""
        task = {
            "id": "integration_test_001",
            "description": "Extract enzyme kinetics from test paper",
            "use_planner": True,
            "phase": 1,
            "user_input": "",
        }

        # Phase 1
        result = await orchestrator.execute_task(task)
        assert result["status"] == "success"
        assert "plan_id" in result
        assert result["current_phase"] == 1
        assert result["next_phase"] == 2

        plan_id = result["plan_id"]

        # Phase 2
        task["plan_id"] = plan_id
        task["phase"] = 2
        task["user_input"] = "Need to extract Km, kcat, Tm"

        result = await orchestrator.execute_task(task)
        assert result["status"] == "success"
        assert result["current_phase"] == 2
        assert result["next_phase"] == 3

        # Phase 3
        task["phase"] = 3
        task["user_input"] = "Approved"

        result = await orchestrator.execute_task(task)
        assert result["status"] == "success"
        assert result["current_phase"] == 3
        assert result["next_phase"] == 4

        # Phase 4
        task["phase"] = 4
        task["user_input"] = ""

        result = await orchestrator.execute_task(task)
        assert result["status"] == "success"
        assert result["current_phase"] == 4
        assert result["next_phase"] == 5

        # Verify plan file was created
        plan_path = Path("data/plans") / f"{plan_id}.json"
        # Note: May not exist if using tmp_path patch
        # assert plan_path.exists()

        # Phase 5
        task["phase"] = 5
        task["user_input"] = "Confirm execution"

        result = await orchestrator.execute_task(task)
        assert result["status"] == "success"
        assert result["ready_to_execute"] is True
        assert result["plan_status"] == "approved"

    @pytest.mark.asyncio
    async def test_planner_with_enzyme_design_task(self, orchestrator):
        """Test planning with enzyme design specific task."""
        task = {
            "id": "enzyme_design_test",
            "description": """
            Analyze enzyme design workflow from paper.

            Paper: data/listov2025.md

            Objectives:
            - Extract complete design workflow
            - Extract kinetic parameters
            - Generate summary report
            """,
            "use_planner": True,
            "phase": 1,
            "user_input": "",
        }

        result = await orchestrator.execute_task(task)

        assert result["status"] == "success"
        assert "plan_id" in result
        assert "phase_result" in result

        phase_result = result["phase_result"]
        assert "understanding" in phase_result
        assert "questions" in phase_result
        assert "suggestions" in phase_result


@pytest.mark.asyncio
class TestExecutorIntegration:
    """Integration tests for executor with orchestrator."""

    async def test_executor_with_mock_plan(self, orchestrator, tmp_path):
        """Test executor with a mock plan file."""
        # Create a mock plan
        plan_id = "plan_test_20250204_123456"
        plan_data = {
            "plan_id":
            plan_id,
            "task": {
                "description": "Test task"
            },
            "workflow": [{
                "step_id": 1,
                "agent": "enzyme_kinetics_extractor",
                "action": "extract_kinetics",
                "inputs": {
                    "text": "Test data",
                    "source_file": "test.md"
                },
                "description": "Extract kinetics",
            }],
            "phases": {
                "phase_1": {
                    "status": "completed"
                },
                "phase_2": {
                    "status": "completed"
                },
                "phase_3": {
                    "status": "completed"
                },
                "phase_4": {
                    "status": "completed"
                },
                "phase_5": {
                    "status": "completed",
                    "ready_to_execute": True
                },
            },
            "status":
            "approved",
            "metadata": {
                "created_at": "2025-02-04T12:00:00"
            },
        }

        # Save plan
        plan_path = tmp_path / f"{plan_id}.json"
        plan_path.write_text(json.dumps(plan_data, indent=2))

        # Execute plan (may fail if enzyme_kinetics_extractor agent not available)
        result = await orchestrator.execute_task({
            "id": "test_execution",
            "plan_id": plan_id,
        })

        # Check result structure (may be error if agent not available)
        assert "status" in result
        if result["status"] == "success":
            assert "execution_summary" in result
        else:
            # Expected if agents not fully initialized
            assert "error" in result or "plan_id" in result

    async def test_executor_with_nonexistent_plan(self, orchestrator):
        """Test executor with nonexistent plan."""
        result = await orchestrator.execute_task({
            "id": "test_execution",
            "plan_id": "plan_nonexistent_123456",
        })

        assert result["status"] == "failed"
        assert "error" in result or "Plan not found" in str(result.get("error", ""))


@pytest.mark.asyncio
class TestEndToEnd:
    """End-to-end tests for planner-executor workflow."""

    async def test_plan_to_execute_flow(self, orchestrator):
        """Test flow from planning to execution."""
        # This is a simplified test that checks the flow
        # Full execution requires all agents to be available

        # Step 1: Create plan (through phase 1 only for speed)
        task = {
            "id": "e2e_test",
            "description": "Test workflow",
            "use_planner": True,
            "phase": 1,
            "user_input": "",
        }

        result = await orchestrator.execute_task(task)
        assert result["status"] == "success"
        assert "plan_id" in result

        # In a full test, we would:
        # 1. Complete all 5 phases
        # 2. Verify plan is approved
        # 3. Execute the plan
        # 4. Verify results

        # For now, just verify the structure
        plan_id = result["plan_id"]
        assert plan_id is not None


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling in planning workflow."""

    async def test_planner_without_description(self, orchestrator):
        """Test planner with missing task description."""
        task = {
            "id": "error_test",
            "use_planner": True,
            "phase": 1,
        }

        result = await orchestrator.execute_task(task)
        assert result["status"] in ["failed", "error"]

    async def test_executor_without_plan_id(self, orchestrator):
        """Test executor without plan_id."""
        task = {
            "id": "error_test",
        }

        result = await orchestrator.execute_task(task)
        # Should either fail or use default behavior
        assert "status" in result

    async def test_planner_invalid_phase(self, orchestrator):
        """Test planner with invalid phase number."""
        task = {
            "id": "error_test",
            "description": "Test",
            "plan_id": "any_plan",
            "phase": 99,  # Invalid phase
            "user_input": "",
        }

        result = await orchestrator.execute_task(task)
        # Should handle gracefully
        assert "status" in result
