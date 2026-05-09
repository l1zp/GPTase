# GPTase Test Suite

This directory contains the complete test suite for the GPTase multi-agent framework.

## Test Structure

```
tests/
├── README.md                      # This file
├── conftest.py                    # Pytest fixtures (model config, sample images)
├── __init__.py                    # Test package initialization
├── integration/                   # Integration tests
│   ├── test_enzyme_agent.py       # Enzyme extraction agent tests
│   └── test_orchestrator.py       # Agent orchestrator tests
├── test_agents/                   # Agent-specific tests
│   ├── test_markdown_agents_integration.py
│   └── test_markdown_agent_multimodal.py
├── test_agent_multimodal.py       # Agent multimodal support tests
├── test_models.py                 # Model management and multimodal types
├── test_streaming_logic.py        # Async streaming functionality
└── test_thinking_config.py        # Extended thinking mode
```

## Quick Start

### Run All Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=gptase --cov-report=term-missing

# Run specific test file
pytest tests/test_agent_multimodal.py -v

# Run specific test
pytest tests/test_models.py::TestMultimodalTypes::test_text_content_creation -v
```

### Test Categories

| Category | Test File | Description | Tests |
|----------|-----------|-------------|-------|
| **Agent Multimodal** | test_agent_multimodal.py | Agent multimodal support (images, prompts) | 16 |
| **Markdown Agent Multimodal** | test_agents/test_markdown_agent_multimodal.py | MarkdownAgent multimodal handling | 12 |
| **Models** | test_models.py | LLM model management and multimodal types | 14 |
| **Streaming Logic** | test_streaming_logic.py | Async streaming functionality | 1 |
| **Thinking Config** | test_thinking_config.py | Extended thinking mode | 3 |
| **Markdown Agents** | test_agents/test_markdown_agents_integration.py | Agent loading and tools | 2 |
| **Integration** | integration/*.py | End-to-end and orchestrator tests | 10 |

**Total**: 58 tests across 7 categories

## Test Coverage by Feature

### Multimodal Support (28 tests)

**Agent Multimodal** ([test_agent_multimodal.py](./test_agent_multimodal.py)):
- Agent initialization with config
- Model name resolution
- Claude model detection
- TextContent and ImageUrlContent types
- Image loading (PNG, JPEG)
- Error handling for missing images
- `run(image_paths=...)` with single/multiple images
- System prompt building with skills

**MarkdownAgent Multimodal** ([test_agents/test_markdown_agent_multimodal.py](./test_agents/test_markdown_agent_multimodal.py)):
- Image path extraction (single, multiple, list, combined)
- Deduplication of image paths
- User prompt building (with/without images)
- Process task routing (text vs multimodal)

**Model Types** ([test_models.py](./test_models.py)):
- TextContent creation and serialization
- ImageUrlContent creation and serialization
- MultimodalContent union type

### Core Framework (31 tests)

**Models** ([test_models.py](./test_models.py)):
- Model manager initialization
- Mock provider
- Agent-specific role configuration
- Health checks
- Usage statistics
- LLM config validation
- Chat completions

**Integration** ([integration/](./integration/)):
- Enzyme agent text processing
- Orchestrator initialization
- System status
- Agent listing
- Memory operations
- Task execution
- Health monitoring
- Graceful shutdown

## Running Specific Tests

### By Feature

```bash
# Multimodal tests (28 tests)
pytest tests/test_agent_multimodal.py tests/test_agents/test_markdown_agent_multimodal.py tests/test_models.py::TestMultimodalTypes -v

# Core framework tests
pytest tests/test_models.py tests/integration/ -v

# Agent tests
pytest tests/test_agents/ -v
```

### By Pattern

```bash
# Run all tests matching a pattern
pytest tests/ -k "multimodal" -v
pytest tests/ -k "image" -v
pytest tests/ -k "agent" -v
```

### With Coverage

```bash
# Generate coverage report
pytest tests/ --cov=gptase --cov-report=html

# View in browser
open htmlcov/index.html
```

## Test Fixtures

Shared fixtures are defined in [conftest.py](./conftest.py):

| Fixture | Description |
|---------|-------------|
| `framework_config` | Standard FrameworkConfig instance |
| `mock_model_config` | Mock ModelConfig for testing |
| `sample_image_png` | Minimal valid PNG image (1x1 pixel) |
| `sample_image_jpeg` | Minimal valid JPEG image |
| `sample_images_dir` | Directory with multiple test images |

## Writing New Tests

### Test Template

```python
"""Tests for [feature]."""

import pytest
from pathlib import Path

from gptase.module import YourModule


class TestFeature:
    """Test [feature description]."""

    def test_basic_functionality(self):
        """Test that basic functionality works."""
        # Arrange
        input_data = {...}

        # Act
        result = YourModule.process(input_data)

        # Assert
        assert result.expected == "value"
```

### Multimodal Test Template

```python
"""Tests for multimodal functionality."""

import pytest
from gptase.agents.agent import Agent
from gptase.models.types import ModelConfig, ModelProvider


class TestMultimodalFeature:
    """Test multimodal feature."""

    def test_image_loading(self, sample_image_png):
        """Test loading image as multimodal content."""
        agent = Agent(system_prompt="Test")
        result = agent._load_image_as_content(sample_image_png)

        assert result is not None
        assert result["type"] == "image_url"
```

### Best Practices

1. **Descriptive names**: `test_extract_image_paths_from_task` (good)
2. **One assertion per test**: When possible
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Use fixtures**: For common setup/teardown
5. **Mock external APIs**: Don't make real network calls
6. **Test edge cases**: Empty inputs, null values, errors
7. **Use tmp_path**: For temporary file creation

## CI/CD Integration

Tests run automatically on GitHub Actions (`.github/workflows/ci.yml`):

```yaml
- Format check: isort and yapf
- Type checking: mypy
- Testing: pytest across Python 3.8-3.12
- Coverage reporting
```

## Test Data

Test data files are located in:
- Sample markdown: `data/listov2025.md`
- Sample images: `data/listov2025/images/`
- Extraction results: `data/extraction/`
- Output files: `data/output/`

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Ensure package is installed
pip install -e .

# Run tests
pytest tests/ -v
```

### Integration Tests Fail

Integration tests may require:
- API keys (set `API_KEY` environment variable)
- Network access

Skip if needed:
```bash
pytest tests/ -v -m "not requires_api_key"
```

### Slow Tests

Run in parallel:
```bash
pytest tests/ -n auto
```

## Test Metrics

Current test status (as of 2026-03-02):

| Metric | Value |
|--------|-------|
| Total tests | 55 |
| Passing | 54 |
| Skipped | 1 |
| Coverage | ~85% (gptase/) |
| Runtime | ~5 seconds |

## Recent Changes

### 2026-03-02
- Added multimodal test suite
  - `test_agent_multimodal.py` - Agent class multimodal support
  - `test_agents/test_markdown_agent_multimodal.py` - MarkdownAgent multimodal handling
- Added multimodal type tests in `test_models.py`
- Updated `conftest.py` with image fixtures
- Removed outdated tests for deleted modules

## Related Documentation

- [Main README](../README.md) - Project overview
- [Architecture Overview](../docs/architecture.md) - Architecture with multimodal support
- [Vision Image Analyzer](../docs/tools/vision_image_analyzer.md) - Multimodal agent docs

## Contributing

**MANDATORY**: Every new feature, tool, or agent MUST have corresponding tests added to the `tests/` directory before the feature can be merged.

### When Adding New Features

1. **Write tests first** (TDD approach when possible)
2. **Cover edge cases**: Empty inputs, null values, errors
3. **Use fixtures**: Use existing fixtures from `conftest.py`
4. **Update this README** if adding new test categories
5. **Run full suite** before committing: `pytest tests/ -v`

### Agent Testing Requirements

All agents must have tests covering:
- Agent initialization
- `process_task()` method behavior
- Multimodal handling (if applicable)
- Error scenarios

### Test Checklist

Before committing new code, ensure:

- [ ] All existing tests pass
- [ ] New tests added for new features
- [ ] Coverage does not decrease significantly
- [ ] Tests follow naming convention: `test_{feature}_{scenario}`
- [ ] Tests are properly documented with docstrings
- [ ] Edge cases are covered (empty input, null values, errors)

---

**Last Updated**: 2026-03-02
**Maintainer**: GPTase Development Team
