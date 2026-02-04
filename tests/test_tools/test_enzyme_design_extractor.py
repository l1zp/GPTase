"""Tests for EnzymeDesignExtractorTool."""

import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from src.tools.base import ToolResult
from src.tools.enzyme_design_extractor import EnzymeDesignExtractorTool


@pytest.fixture
def mock_model_manager():
    """Create a mock ModelManager."""
    manager = MagicMock()
    manager.generate = AsyncMock()
    return manager


@pytest.fixture
def sample_design_text():
    """Return sample enzyme design text."""
    return """
    Design of Thermostable PETase

    Objective: Increase thermostability of PETase for industrial plastic degradation.

    Design Process:
    Step 1: Computational Design
    - Used molecular dynamics simulations to identify flexible regions
    - Applied Rosetta design for stabilizing mutations
    - Parameters: temperature=50C, pH=7.5

    Step 2: Library Construction
    - Site-directed mutagenesis at positions 12, 45, and 78
    - Created 24 variants with single and double mutations

    Step 3: Expression and Purification
    - Expressed in E. coli BL21(DE3)
    - Purified using Ni-NTA chromatography
    - Verified by SDS-PAGE

    Step 4: Activity Assay
    - Measured PET hydrolysis at pH 8.0, 50C
    - Substrate: PET film
    - Monitored release of terephthalic acid

    Optimization:
    - Directed evolution for 3 rounds
    - High-throughput screening of 1000+ variants
    - Improved thermostability from 45C to 65C

    Validation:
    - Differential scanning calorimetry (DSC) for Tm
    - Circular dichroism for secondary structure
    - Crystal structure determination (PDB: 9ABC)

    Results:
    - Best variant: DesD12 with 5 mutations
    - Tm increased by 20C
    - Activity maintained at 60C for 24h
    """


@pytest.fixture
def sample_extraction_result():
    """Return sample extraction result JSON."""
    return {
        "design_objectives":
        ["Increase thermostability of PETase for industrial plastic degradation"],
        "design_steps": [{
            "step_id": "1",
            "category": "Design",
            "description": "Computational design using molecular dynamics and Rosetta",
            "techniques": ["molecular dynamics", "Rosetta design"],
            "parameters": {
                "temperature": "50C",
                "pH": "7.5"
            },
            "duration": None,
            "outcomes": []
        }, {
            "step_id": "2",
            "category": "Construction",
            "description": "Site-directed mutagenesis at positions 12, 45, and 78",
            "techniques": ["site-directed mutagenesis"],
            "parameters": {},
            "duration": None,
            "outcomes": []
        }],
        "key_constraints": ["Maintain activity", "Preserve stability"],
        "optimization_cycles": [{
            "cycle_id":
            "1",
            "method":
            "directed evolution",
            "rounds":
            3,
            "improvements": ["Improved thermostability from 45C to 65C"]
        }],
        "validation_approach":
        "Differential scanning calorimetry (DSC), circular dichroism, crystal structure",
        "experimental_conditions": {
            "temperature": "50C",
            "pH": "8.0",
            "buffer": None,
            "notes": None
        },
        "results": {
            "final_variants": ["DesD12"],
            "performance_metrics": {
                "Tm_increase": "20C",
                "activity": "maintained at 60C for 24h"
            },
            "success_rate": None
        },
        "annotations_zh":
        "提取到的步骤含保留英文术语,并提供中文标签说明。"
    }


class TestEnzymeDesignExtractorTool:
    """Test suite for EnzymeDesignExtractorTool."""

    def test_initialization(self, mock_model_manager):
        """Test tool initialization."""
        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)

        assert tool.name == "enzyme_design_extractor"
        assert tool.model_manager == mock_model_manager
        assert "enzyme design" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_model_manager, sample_design_text,
                                   sample_extraction_result):
        """Test successful extraction."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps(sample_extraction_result)
        mock_model_manager.generate.return_value = mock_response

        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)
        result = await tool.execute(text=sample_design_text, source_file="test.md")

        assert result.status == "success"
        assert result.data["design_objectives"]
        assert result.data["design_steps"]
        assert len(result.data["design_steps"]) == 2

    @pytest.mark.asyncio
    async def test_execute_empty_text(self, mock_model_manager):
        """Test extraction with empty text."""
        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)
        result = await tool.execute(text="")

        assert result.status == "error"
        assert "No text provided" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_missing_model_manager(self, sample_design_text):
        """Test extraction without model manager."""
        tool = EnzymeDesignExtractorTool(model_manager=None)
        result = await tool.execute(text=sample_design_text)

        assert result.status == "error"
        assert "missing Model" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_empty_response(self, mock_model_manager, sample_design_text):
        """Test extraction with empty LLM response."""
        mock_response = MagicMock()
        mock_response.content = None
        mock_model_manager.generate.return_value = mock_response

        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)
        result = await tool.execute(text=sample_design_text)

        assert result.status == "error"
        assert "empty response" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_invalid_json(self, mock_model_manager, sample_design_text):
        """Test extraction with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        mock_model_manager.generate.return_value = mock_response

        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)
        result = await tool.execute(text=sample_design_text)

        assert result.status == "error"
        assert "invalid JSON" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_markdown_wrapped_json(self, mock_model_manager,
                                                 sample_design_text,
                                                 sample_extraction_result):
        """Test extraction with markdown-wrapped JSON response."""
        # Mock LLM response with markdown wrapper
        json_str = json.dumps(sample_extraction_result)
        mock_response = MagicMock()
        mock_response.content = f"```json\n{json_str}\n```"
        mock_model_manager.generate.return_value = mock_response

        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)
        result = await tool.execute(text=sample_design_text)

        assert result.status == "success"
        assert result.data["design_steps"]

    @pytest.mark.asyncio
    async def test_post_process_data(self, mock_model_manager, sample_design_text):
        """Test data post-processing with CoT format."""
        # Mock LLM response with incomplete data
        incomplete_data = {
            "design_objectives": ["Objective 1"],
            # Missing required fields
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(incomplete_data)
        mock_model_manager.generate.return_value = mock_response

        tool = EnzymeDesignExtractorTool(model_manager=mock_model_manager)
        result = await tool.execute(text=sample_design_text)

        assert result.status == "success"
        # Check that missing CoT fields were added with defaults
        assert "task" in result.data
        assert "chain_of_thought" in result.data
        assert "design_steps" in result.data
        assert "key_constraints" in result.data
        assert "optimization_cycles" in result.data
        assert "final_answer" in result.data
        # Verify final_answer has required sub-fields
        assert "summary" in result.data["final_answer"]
        assert "success_metrics" in result.data["final_answer"]
        assert "key_innovations" in result.data["final_answer"]

    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown code blocks."""
        tool = EnzymeDesignExtractorTool()

        # Test with ```json wrapper
        json_str = '{"key": "value"}'
        content = f"```json\n{json_str}\n```"
        result = tool._extract_json_from_markdown(content)
        assert result == json_str

        # Test with ``` wrapper (no language)
        content = f"```\n{json_str}\n```"
        result = tool._extract_json_from_markdown(content)
        assert result == json_str

        # Test with plain JSON (no wrapper)
        result = tool._extract_json_from_markdown(json_str)
        assert result == json_str

        # Test with empty string
        result = tool._extract_json_from_markdown("")
        assert result == ""

    def test_build_user_prompt(self):
        """Test user prompt building."""
        tool = EnzymeDesignExtractorTool()
        prompt = tool._build_user_prompt("Sample text", "test.md")

        assert "Sample text" in prompt
        assert "test.md" in prompt
        assert "Extract enzyme design workflow" in prompt

    def test_get_schema(self):
        """Test schema definition."""
        tool = EnzymeDesignExtractorTool()
        schema = tool.get_schema()

        assert schema["type"] == "object"
        assert "text" in schema["properties"]
        assert "source_file" in schema["properties"]
        assert "text" in schema["required"]
