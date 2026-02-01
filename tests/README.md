# GPTase Test Suite

This directory contains the complete test suite for the GPTase enzyme extraction framework.

## Test Structure

```
tests/
├── README.md                      # This file
├── conftest.py                     # Pytest configuration and fixtures
├── __init__.py                     # Test package initialization
├── integration/                    # Integration tests
│   ├── test_enzyme_agent.py        # Enzyme extraction agent tests
│   ├── test_executors.py           # Executor tests (Python, Shell, Docker)
│   └── test_orchestrator.py        # Agent orchestrator tests
└── test_*.py                       # Unit tests by feature
```

## Quick Start

### Run All Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_pdb_novelty.py -v

# Run specific test
pytest tests/test_csv_handling.py::TestFlattenReaction::test_flatten_reaction_basic -v
```

### Test Categories

| Category | Test File | Description | Tests |
|----------|-----------|-------------|-------|
| **CSV Handling** | test_csv_handling.py | CSV parsing, quoting, validation | 11 |
| **Mutation Extraction** | test_mutation_extraction.py | Parse and validate mutation formats | 16 |
| **PDB Novelty** | test_pdb_novelty.py | Boolean novelty classification | 7 |
| **PDB Data Structure** | test_pdb_data_structure.py | Normalized PDB database structure | 7 |
| **PDB EC Conversion** | test_pdb_ec_conversion.py | RCSB API EC number lookup | 9 |
| **Models** | test_models.py | LLM model management and configuration | 9 |
| **Enzyme Extractor** | test_enzyme_extractor.py | Enzyme extraction pipeline | 3 |
| **Streaming Logic** | test_streaming_logic.py | Async streaming functionality | 1 |
| **Thinking Config** | test_thinking_config.py | Extended thinking mode | 1 |
| **Tools** | test_tools/test_mineru_tool.py | MinerU PDF conversion tool | 9 |
| **Integration** | integration/*.py | End-to-end and agent tests | 10 |

**Total**: 83 tests across 11 categories

## Test Coverage by Feature

### PDB Features (23 tests)

**PDB Novelty Classification** ([test_pdb_novelty.py](./test_pdb_novelty.py)):
- ✅ Extraction with `pdb_is_new` field
- ✅ Default behavior when field missing
- ✅ Length mismatch handling
- ✅ CSV generation with mixed novelty
- ✅ All new / all old PDBs
- ✅ Real-world paper scenarios

**PDB Data Structure** ([test_pdb_data_structure.py](./test_pdb_data_structure.py)):
- ✅ Enzyme-PDB relationship extraction
- ✅ Junction table generation
- ✅ Normalized structure (no redundancy)
- ✅ Many-to-many relationships
- ✅ Real data validation

**PDB EC Conversion** ([test_pdb_ec_conversion.py](./test_pdb_ec_conversion.py)):
- ✅ PDB ID extraction from CSV
- ✅ RCSB API queries (single & batch)
- ✅ EC number addition to CSV
- ✅ Deduplication
- ✅ Error handling

### Data Processing (27 tests)

**CSV Handling** ([test_csv_handling.py](./test_csv_handling.py)):
- ✅ Flatten reaction data
- ✅ Handle empty fields
- ✅ CSV quoting with special characters
- ✅ Round-trip data preservation
- ✅ Validation (outliers, negative values, missing units)
- ✅ Mutation format cleaning

**Mutation Extraction** ([test_mutation_extraction.py](./test_mutation_extraction.py)):
- ✅ Valid point mutations (e.g., F113L)
- ✅ Valid extended mutations (e.g., Ile54Val)
- ✅ Invalid format detection
- ✅ Case sensitivity
- ✅ Multiple mutations
- ✅ Empty and null handling
- ✅ Whitespace handling
- ✅ Duplicate detection
- ✅ Order preservation

### Core Framework (24 tests)

**Models** ([test_models.py](./test_models.py)):
- ✅ Model manager initialization
- ✅ Mock provider
- ✅ Role configuration
- ✅ Health checks
- ✅ Usage statistics
- ✅ LLM config validation
- ✅ Chat completions

**Integration** ([integration/](./integration/)):
- ✅ Enzyme agent text processing
- ✅ Orchestrator initialization
- ✅ System status
- ✅ Agent listing
- ✅ Memory operations
- ✅ Task execution
- ✅ Health monitoring

## Running Specific Tests

### By Feature

```bash
# PDB tests (23 tests)
pytest tests/test_pdb_*.py -v

# Data processing tests (27 tests)
pytest tests/test_csv_handling.py tests/test_mutation_extraction.py -v

# Core framework tests
pytest tests/test_models.py tests/integration/ -v
```

### By Pattern

```bash
# Run all tests matching a pattern
pytest tests/ -k "pdb" -v
pytest tests/ -k "csv" -v
pytest tests/ -k "mutation" -v
```

### With Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html

# View in browser
open htmlcov/index.html
```

## Test Fixtures

Shared fixtures are defined in [conftest.py](./conftest.py):

- **Sample data**: Temporary files for testing
- **Model managers**: Mock and real configurations
- **Test documents**: Sample markdown/HTML files

## Writing New Tests

### Test Template

```python
"""Tests for [feature]."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules import YourModule


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

### Best Practices

1. **Descriptive names**: `test_extract_pdb_ids_from_csv` (good)
2. **One assertion per test**: When possible
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Use fixtures**: For common setup/teardown
5. **Mock external APIs**: Don't make real network calls
6. **Test edge cases**: Empty inputs, null values, errors

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
- Extraction results: `data/extraction/listov2025_extraction.json`
- CSV outputs: `data/extraction/*.csv`

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Ensure src is on Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
```

### Integration Tests Fail

Integration tests may require:
- API keys (set `API_KEY` environment variable)
- Network access (for RCSB API tests)
- Docker daemon (for executor tests)

Skip if needed:
```bash
pytest tests/ -v -m "not integration"
```

### Slow Tests

Run in parallel:
```bash
pytest tests/ -n auto
```

## Test Metrics

Current test status (as of 2025-01-24):

| Metric | Value |
|--------|-------|
| Total tests | 74 |
| Passing | ~70 |
| Coverage | ~85% (src/) |
| Runtime | ~30 seconds |

## Recent Changes

### 2025-01-24
- ✅ Removed outdated `test_pdb_novelty_classification.py` (old string-based classification)
- ✅ Moved verification scripts to `scripts/verification/`
- ✅ Updated test suite to use boolean novelty classification
- ✅ All PDB tests passing (23/23)

## Related Documentation

- [Main README](../README.md) - Project overview
- [ENZYME EXTRACTION WORKFLOW](../docs/ENZYME_EXTRACTION_WORKFLOW.md) - Usage guide
- [pdb_features.md](../docs/pdb_features.md) - PDB feature documentation

## Contributing

**MANDATORY**: Every new feature, tool, or agent MUST have corresponding tests added to the `tests/` directory before the feature can be merged.

### When Adding New Features

1. **Write tests first** (TDD approach when possible)
2. **Cover edge cases**: Empty inputs, null values, errors
3. **Use test templates**: See `tests/test_tools/TEMPLATE.py` for tools
4. **Update this README** if adding new test categories
5. **Run full suite** before committing: `pytest tests/ -v`

### Tool Testing Requirements

All tools in `src/tools/implementations.py` must have tests in `tests/test_tools/`:

- ✅ Test initialization and configuration
- ✅ Test `execute()` method with valid inputs
- ✅ Test error handling and edge cases
- ✅ Test timeout behavior
- ✅ Test schema validation

**Example**: See `tests/test_tools/test_mineru_tool.py` for a complete test suite.

### Agent Testing Requirements

All agents must have tests in `tests/test_agents/`:

- ✅ Test agent initialization
- ✅ Test `process_task()` or `execute_task()` methods
- ✅ Test integration with dependencies (memory_manager, tool_registry, model_manager)
- ✅ Test error scenarios

### Test Checklist

Before committing new code, ensure:

- [ ] All existing tests pass
- [ ] New tests added for new features
- [ ] Coverage does not decrease significantly
- [ ] Tests follow naming convention: `test_{feature}_{scenario}`
- [ ] Tests are properly documented with docstrings
- [ ] Edge cases are covered (empty input, null values, errors)

### CI/CD Checks

GitHub Actions will automatically verify:
- All tests pass across Python 3.8-3.12
- Coverage does not decrease
- Code formatting (isort, yapf)
- Type checking (mypy)

---

**Last Updated**: 2025-01-24
**Maintainer**: GPTase Development Team
