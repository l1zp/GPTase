"""Tests for EnzymeDesignExtractorAgent."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.agents.specialized.enzyme_design_extractor_agent import \
    EnzymeDesignExtractorAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS


@pytest.fixture
def mock_model_manager():
    """Create a mock ModelManager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_memory_manager():
    """Create a mock MemoryManager."""
    return MagicMock()


@pytest.fixture
def mock_tool_registry():
    """Create a mock ToolRegistry."""
    return MagicMock()


@pytest.fixture
def sample_design_text():
    """Return sample enzyme design text."""
    return """
    Design of thermostable enzyme variant.
    Step 1: Computational design using Rosetta.
    Step 2: Site-directed mutagenesis.
    Step 3: Expression in E. coli.
    """


@pytest.fixture
def sample_extraction_data():
    """Return sample extraction data."""
    return {
        "design_objectives": ["Increase thermostability"],
        "design_steps": [{
            "step_id": "1",
            "category": "Design",
            "description": "Computational design using Rosetta",
            "techniques": ["Rosetta"],
            "parameters": {},
            "duration": None,
            "outcomes": []
        }],
        "key_constraints": ["Maintain activity"],
        "optimization_cycles": [],
        "validation_approach":
        "Differential scanning calorimetry",
        "experimental_conditions": {},
        "results": {},
        "annotations_zh":
        "酶设计流程提取"
    }


class TestEnzymeDesignExtractorAgent:
    """Test suite for EnzymeDesignExtractorAgent."""

    def test_initialization(self, mock_memory_manager, mock_tool_registry,
                            mock_model_manager):
        """Test agent initialization."""
        agent = EnzymeDesignExtractorAgent(
            agent_id="test_agent",
            memory_manager=mock_memory_manager,
            tool_registry=mock_tool_registry,
            model_manager=mock_model_manager,
        )

        assert agent.agent_id == "test_agent"
        assert agent.model_manager == mock_model_manager
        assert agent.AGENT_NAME == "enzyme_design_extractor"
        assert "extract_design_workflow" in agent.capabilities
        assert "extract_design_objectives" in agent.capabilities

    @pytest.mark.asyncio
    async def test_process_task_success(self, mock_memory_manager, mock_tool_registry,
                                        mock_model_manager, sample_design_text,
                                        sample_extraction_data):
        """Test successful task processing."""
        agent = EnzymeDesignExtractorAgent(
            agent_id="test_agent",
            memory_manager=mock_memory_manager,
            tool_registry=mock_tool_registry,
            model_manager=mock_model_manager,
        )

        # Mock the EnzymeDesignExtractorTool
        with patch(
                "src.agents.specialized.enzyme_design_extractor_agent.EnzymeDesignExtractorTool"
        ) as MockTool:
            mock_tool_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.data = sample_extraction_data
            mock_tool_instance.execute = AsyncMock(return_value=mock_result)
            MockTool.return_value = mock_tool_instance

            task = {"text": sample_design_text, "source_file": "test.md"}

            result = await agent.process_task(task)

            assert result["status"] == STATUS_SUCCESS
            assert "data" in result
            assert result["data"]["design_objectives"]

    @pytest.mark.asyncio
    async def test_process_task_no_text(self, mock_memory_manager, mock_tool_registry,
                                        mock_model_manager):
        """Test task processing with no text."""
        agent = EnzymeDesignExtractorAgent(
            agent_id="test_agent",
            memory_manager=mock_memory_manager,
            tool_registry=mock_tool_registry,
            model_manager=mock_model_manager,
        )

        task = {}

        result = await agent.process_task(task)

        assert result["status"] == STATUS_ERROR
        assert "error" in result["data"]
        assert "No text provided" in result["data"]["error"]

    @pytest.mark.asyncio
    async def test_process_task_tool_error(self, mock_memory_manager,
                                           mock_tool_registry, mock_model_manager,
                                           sample_design_text):
        """Test task processing when tool returns error."""
        agent = EnzymeDesignExtractorAgent(
            agent_id="test_agent",
            memory_manager=mock_memory_manager,
            tool_registry=mock_tool_registry,
            model_manager=mock_model_manager,
        )

        # Mock the EnzymeDesignExtractorTool to return error
        with patch(
                "src.agents.specialized.enzyme_design_extractor_agent.EnzymeDesignExtractorTool"
        ) as MockTool:
            mock_tool_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.status = "error"
            mock_result.error = "Extraction failed"
            mock_tool_instance.execute = AsyncMock(return_value=mock_result)
            MockTool.return_value = mock_tool_instance

            task = {"text": sample_design_text, "source_file": "test.md"}

            result = await agent.process_task(task)

            assert result["status"] == STATUS_ERROR
            assert "error" in result["data"]
            assert result["data"]["error"] == "Extraction failed"

    @pytest.mark.asyncio
    async def test_process_task_with_session_tracking(self, mock_memory_manager,
                                                      mock_tool_registry,
                                                      mock_model_manager,
                                                      sample_design_text,
                                                      sample_extraction_data):
        """Test task processing with session tracking parameters."""
        agent = EnzymeDesignExtractorAgent(
            agent_id="test_agent",
            memory_manager=mock_memory_manager,
            tool_registry=mock_tool_registry,
            model_manager=mock_model_manager,
        )

        # Mock the EnzymeDesignExtractorTool
        with patch(
                "src.agents.specialized.enzyme_design_extractor_agent.EnzymeDesignExtractorTool"
        ) as MockTool:
            mock_tool_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.data = sample_extraction_data
            mock_tool_instance.execute = AsyncMock(return_value=mock_result)
            MockTool.return_value = mock_tool_instance

            task = {"text": sample_design_text, "source_file": "test.md"}

            result = await agent.process_task(task,
                                              session_id="test_session",
                                              agent_id="custom_agent",
                                              step_id="step_1")

            assert result["status"] == STATUS_SUCCESS

            # Verify tool was called with tracking parameters
            mock_tool_instance.execute.assert_called_once()
            call_kwargs = mock_tool_instance.execute.call_args[1]
            assert call_kwargs["text"] == sample_design_text
            assert call_kwargs["source_file"] == "test.md"

    @pytest.mark.asyncio
    async def test_process_task_exception(self, mock_memory_manager, mock_tool_registry,
                                          mock_model_manager, sample_design_text):
        """Test task processing with unexpected exception."""
        agent = EnzymeDesignExtractorAgent(
            agent_id="test_agent",
            memory_manager=mock_memory_manager,
            tool_registry=mock_tool_registry,
            model_manager=mock_model_manager,
        )

        # Mock the EnzymeDesignExtractorTool to raise exception
        with patch(
                "src.agents.specialized.enzyme_design_extractor_agent.EnzymeDesignExtractorTool"
        ) as MockTool:
            mock_tool_instance = MagicMock()
            mock_tool_instance.execute = AsyncMock(
                side_effect=Exception("Unexpected error"))
            MockTool.return_value = mock_tool_instance

            task = {"text": sample_design_text, "source_file": "test.md"}

            result = await agent.process_task(task)

            assert result["status"] == STATUS_ERROR
            assert "error" in result["data"]
            assert "Unexpected error" in result["data"]["error"]
