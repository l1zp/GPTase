# Testing Guide

Comprehensive guide for testing the GPTase framework, including test strategies, requirements, and best practices.

## Test Types

The framework uses a multi-level testing strategy:

### Unit Tests
Test individual components in isolation:
- **Models**: LLM abstraction, streaming, configuration
- **Tools**: Document loader, code executor, file manager
- **Memory**: Storage and context management

### Integration Tests
Test interactions between components:
- **Agent-Tool integration**: Tool execution through agents
- **Model-Tool integration**: LLM calls from tools
- **Memory-Agent integration**: Context passing and storage

### End-to-End Tests
Test complete workflows:
- **Enzyme extraction**: Full pipeline execution
- **Agent orchestration**: Multi-agent workflows
- **Session tracking**: Database operations

## Test Structure

```
tests/
├── __init__.py                 # pytest_asyncio plugin config
├── conftest.py                 # Shared fixtures (FrameworkConfig)
├── test_models.py              # Model manager and provider tests
├── test_thinking_config.py     # Thinking mode configuration tests
├── test_streaming_logic.py     # Streaming chunking logic tests
├── test_csv_handling.py        # CSV export pipeline tests
├── test_mutation_extraction.py # Mutation format validation tests
├── test_pdb_data_structure.py  # PDB data normalization tests
├── test_pdb_ec_conversion.py   # PDB-to-EC number lookup tests
├── test_pdb_novelty.py         # PDB novelty classification tests
├── test_tools/                 # Tool-specific tests
│   ├── test_planner_tool.py    # 5-phase planner tests
│   └── test_mineru_tool.py     # MinerU PDF converter tests
├── test_agents/                # Agent tests
│   ├── test_markdown_agents_integration.py  # Markdown agent loading
│   └── test_sdk_integration.py # SDK adapter, tool bridge, hooks
├── test_core/                  # Core module tests
│   └── test_sop_executor.py    # SOP variable resolution tests
└── integration/                # Integration tests
    ├── test_orchestrator.py    # Orchestrator lifecycle tests
    ├── test_enzyme_agent.py    # Enzyme extraction integration
    └── test_planner_integration.py  # Planner integration
```

## Running Tests

### Run All Tests

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run with HTML coverage report
pytest tests/ -v --cov=src --cov-report=html
open htmlcov/index.html
```

### Run Specific Test Categories

```bash
# Test tools only
pytest tests/test_tools/ -v

# Test agents only
pytest tests/test_agents/ -v

# Test integration only
pytest tests/integration/ -v
```

### Run Single Test File

```bash
# Run specific test file
pytest tests/test_models.py -v

# Run specific test class
pytest tests/test_models.py::TestModelManager -v

# Run specific test
pytest tests/test_models.py::TestModelManager::test_generate -v
```

### Run with Filters

```bash
# Run tests matching pattern
pytest tests/ -v -k "test_streaming"

# Run tests excluding pattern
pytest tests/ -v -k "not test_docker"

# Run tests marked with specific marker
pytest tests/ -v -m integration
```

## MANDATORY: Test Requirement for New Features

**IMPORTANT**: Every new feature, tool, or agent MUST have corresponding tests added to the `tests/` directory before the feature can be merged.

### When Adding New Functionality

#### 1. Adding a New Tool

**Required Tests:**

```python
# tests/test_tools/test_my_tool.py
import pytest

from src.tools.utils import MyTool  # Update to correct module
from src.tools.base import ToolResult


class TestMyTool:
    """Test suite for MyTool"""

    def test_initialization(self):
        """Test tool can be initialized"""
        tool = MyTool()
        assert tool.name == "my_tool"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution"""
        tool = MyTool()
        result = await tool.execute(param="value")

        assert result.status == "success"
        assert result.data is not None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_with_invalid_params(self):
        """Test error handling for invalid parameters"""
        tool = MyTool()
        result = await tool.execute(invalid_param="value")

        assert result.status == "error"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test timeout behavior"""
        tool = MyTool(timeout=0.1)  # Very short timeout

        with pytest.raises(TimeoutError):
            await tool.execute(slow_operation=True)

    @pytest.mark.asyncio
    async def test_execute_edge_cases(self):
        """Test edge cases and boundary conditions"""
        tool = MyTool()

        # Test with empty input
        result = await tool.execute(param="")
        assert result.status == "error"

        # Test with very large input
        result = await tool.execute(param="x" * 1000000)
        assert result.status == "success"
```

**Location:** `tests/test_tools/test_{tool_name}.py`

**Requirements:**
- Test initialization and configuration
- Test `execute()` method with valid inputs
- Test error handling and edge cases
- Test timeout behavior
- Ensure all tests pass before committing

#### 2. Adding a New Agent

**Required Tests:**

Since most agents are now Markdown-based, test the Markdown configuration and integration:

```python
# tests/test_agents/test_my_agent.py
import pytest

from src.agents.markdown_agent import MarkdownAgentFactory
from src.models.model import Model
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

class TestMyAgent:
    """Test suite for MyAgent"""

    @pytest.fixture
    def agent(self):
        """Create agent instance from markdown definition"""
        model_manager = Model()
        tool_registry = ToolRegistry()
        memory_manager = MemoryManager()
        factory = MarkdownAgentFactory()

        return factory.create_agent(
            "my_agent",
            memory_manager,
            tool_registry,
            model_manager=model_manager
        )

    def test_initialization(self, agent):
        """Test agent can be initialized"""
        assert agent.agent_id == "test_agent"
        assert agent.memory_manager is not None
        assert agent.tool_registry is not None

    @pytest.mark.asyncio
    async def test_process_task(self, agent):
        """Test task processing"""
        task = {"param": "value"}

        result = await agent.process_task(task)

        assert result["status"] in ["success", "error"]
        assert "data" in result or "error" in result

    @pytest.mark.asyncio
    async def test_process_task_with_missing_params(self, agent):
        """Test error handling for missing parameters"""
        task = {}  # Missing required params

        result = await agent.process_task(task)

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_check(self, agent):
        """Test health check functionality"""
        health = await agent.health_check()

        assert health["status"] == "healthy"
        assert "agent_id" in health

    @pytest.mark.asyncio
    async def test_shutdown(self, agent):
        """Test cleanup on shutdown"""
        await agent.shutdown()
        # Verify resources are cleaned up
        assert True  # Add specific assertions
```

**Location:** `tests/test_agents/test_{agent_name}.py`

**Requirements:**
- Test agent initialization
- Test `process_task()` or `execute_task()` methods
- Test integration with dependencies (memory_manager, tool_registry, model_manager)
- Test error scenarios
- Ensure all tests pass before committing

#### 3. Adding a New Module

Create appropriate test directory structure:

**Example:**
```
src/tools/new_tool.py → tests/test_tools/test_new_tool.py
src/models/new_model.py → tests/test_models.py
```

Follow existing test patterns in `tests/` directory.

## Test Templates

### Unit Test Template

```python
import pytest

from src.module import ClassUnderTest


class TestClassUnderTest:
    """Test suite for ClassUnderTest"""

    @pytest.fixture
    def instance(self):
        """Create instance for testing"""
        return ClassUnderTest(param="value")

    def test_feature_x(self, instance):
        """Test feature X"""
        result = instance.method_x()
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_async_feature_y(self, instance):
        """Test async feature Y"""
        result = await instance.async_method_y()
        assert result is not None
```

### Integration Test Template

```python
import pytest

from src.agents.my_agent import MyAgent
from src.tools.registry import ToolRegistry


@pytest.mark.integration
class TestAgentToolIntegration:
    """Test agent-tool integration"""

    @pytest.fixture
    def agent_with_tools(self):
        """Create agent with tools"""
        registry = ToolRegistry()
        registry.register_tools([MyTool()])

        agent = MyAgent(
            "test_agent",
            memory_manager,
            registry,
            model_manager
        )
        return agent

    @pytest.mark.asyncio
    async def test_agent_uses_tool(self, agent_with_tools):
        """Test agent can use tools"""
        result = await agent.process_task({
            "action": "use_tool",
            "tool_name": "my_tool"
        })
        assert result["status"] == "success"
```

## CI/CD Integration

### GitHub Actions Workflow

The framework uses GitHub Actions (`.github/workflows/ci.yml`) for automated testing:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run format check
        run: |
          isort --check-only src/ tests/
          yapf --diff --recursive src/ tests/

      - name: Run type check
        run: mypy src/ --ignore-missing-imports

      - name: Run tests
        run: pytest tests/ -v --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### What CI/CD Checks

1. **Format check**: isort and yapf must pass
2. **Lint**: mypy type checking
3. **Test**: pytest across Python 3.9-3.12 with coverage reporting
4. **Coverage**: Coverage does not decrease significantly
5. **New features**: Have corresponding tests

## Test Fixtures

### Common Fixtures (conftest.py)

```python
# tests/conftest.py
import os
import sys

import pytest

from src.core.config import FrameworkConfig

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture
def framework_config():
    """Fixture to provide a standard FrameworkConfig instance."""
    return FrameworkConfig()
```

## Testing Best Practices

### 1. Test Isolation

```python
# Good: Isolated test
def test_addition():
    result = add(2, 3)
    assert result == 5

# Bad: Dependent test
def test_addition_then_multiplication():
    sum_result = add(2, 3)
    mult_result = multiply(sum_result, 4)  # Depends on add
```

### 2. Descriptive Test Names

```python
# Good: Clear what it tests
def test_execute_with_valid_input_returns_success()

# Bad: Vague
def test_execute()
```

### 3. Use Fixtures

```python
# Good: Using fixtures
def test_with_fixture(agent):
    result = agent.process_task(task)

# Bad: Hardcoded setup
def test_without_fixture():
    agent = MyAgent(...)
    result = agent.process_task(task)
```

### 4. Test Edge Cases

```python
class TestMyTool:
    async def test_with_normal_input(self):
        """Test normal case"""

    async def test_with_empty_input(self):
        """Test edge case: empty input"""

    async def test_with_large_input(self):
        """Test edge case: large input"""

    async def test_with_special_characters(self):
        """Test edge case: special characters"""
```

### 5. Mock External Dependencies

```python
from unittest.mock import AsyncMock
from unittest.mock import patch


class TestAgent:
    @pytest.mark.asyncio
    async def test_with_mocked_llm(self, agent):
        """Test with mocked LLM calls"""
        with patch.object(
            agent.model_manager,
            'generate',
            new_callable=AsyncMock,
            return_value="Mocked response"
        ):
            result = await agent.process_task(task)
            assert result["data"] == "Mocked response"
```

## Coverage Requirements

### Target Coverage

- **Overall**: > 80% coverage
- **Critical modules**: > 90% coverage
- **New code**: 100% coverage (MANDATORY)

### Generating Coverage Reports

```bash
# Terminal report
pytest tests/ --cov=src --cov-report=term-missing

# HTML report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest tests/ --cov=src --cov-report=xml
```

### Interpreting Coverage

```
Name                              Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
src/tools/system.py                 145      12    92%   23-27, 45-49
src/agents/base.py                  89      15    83%   67-82
src/models/manager.py              203       8    96%   234-241
-------------------------------------------------------------------
TOTAL                              437      35    92%
```

**Focus on:**
- High-traffic code (should be > 90%)
- Error handling paths
- Edge cases and boundary conditions

## Debugging Tests

### Run Tests in Debug Mode

```bash
# Run with pdb debugger
pytest tests/test_mytest.py --pdb

# Run on failure and drop into debugger
pytest tests/test_mytest.py --pdb-trace

# Show local variables on failure
pytest tests/test_mytest.py -l
```

### Print Debugging

```python
def test_with_prints():
    result = my_function()
    print(f"Result: {result}")  # Shows with -s flag
    assert result == expected
```

Run with: `pytest tests/ -v -s`

### Selective Testing

```bash
# Run only failed tests from last run
pytest tests/ --lf

# Run only tests affected by changes
pytest tests/ --affected
```

## Performance Testing

### Benchmarking

```python
import time


def test_performance():
    """Test that operation completes in acceptable time"""
    start = time.time()
    result = slow_operation()
    duration = time.time() - start

    assert result is not None
    assert duration < 1.0  # Should complete in < 1 second
```

### Load Testing

```python
@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test handling concurrent requests"""
    tasks = [operation() for _ in range(100)]
    results = await asyncio.gather(*tasks)

    assert all(r is not None for r in results)
```

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [.github/workflows/ci.yml](../.github/workflows/ci.yml) - CI/CD configuration
- [pytest documentation](https://docs.pytest.org/) - pytest framework guide
