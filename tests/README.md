# Tests Directory Structure

This directory contains all tests for the GPTase framework.

## Directory Layout

```
tests/
├── __init__.py
├── conftest.py                 # Pytest configuration and fixtures
├── README.md                   # This file
├── test_*.py                   # Unit tests (run by default)
├── integration/                # Integration tests
│   ├── __init__.py
│   ├── test_orchestrator.py    # Agent orchestrator tests
│   ├── test_executors.py       # Code execution engine tests (skipped - legacy)
│   └── test_enzyme_agent.py    # Enzyme kinetics extraction agent tests
└── verification/               # Verification and demonstration scripts
    ├── __init__.py
    ├── test_analyzer.py        # Document analyzer verification
    ├── test_llm_analyzer.py    # LLM-enhanced analyzer verification
    ├── compare_llm_enhancement.py
    └── LLM_ENHANCEMENT_VERIFICATION_REPORT.md
```

## Test Categories

### Unit Tests (`tests/test_*.py`)

These are fast, isolated tests that test individual components in isolation:
- `test_models.py` - Model manager and provider tests
- `test_enzyme_extractor.py` - Enzyme extraction tool function tests (keyword-based)

**Run unit tests only:**
```bash
pytest tests/ -v --ignore=tests/integration --ignore=tests/verification
```

### Integration Tests (`tests/integration/`)

These tests verify that multiple components work together correctly:
- `test_orchestrator.py` - Agent system orchestration and task execution
- `test_executors.py` - Code execution engines (skipped - legacy, not currently applicable)
- `test_enzyme_agent.py` - End-to-end enzyme kinetics extraction workflow

**Note:** Enzyme agents have been renamed for clarity:
- `enzyme_kinetics_extractor` - Extracts kinetic parameters (Km, kcat, Tm, etc.)
- `enzyme_design_parser` - Extracts enzyme design workflows

**Removed tests:**
- `test_fibonacci_task_execution` - Unreliable, requires LLM execution
- `test_task_with_plan` - Unreliable, requires LLM execution
  These tests were removed because they depend on LLM behavior and frequently fail.

**Run integration tests:**
```bash
pytest tests/integration/ -v
```

**Note:** Some integration tests may require:
- LLM API keys (set `API_KEY` environment variable)
- Docker daemon running (for Docker executor tests)
- Network access (for web-related tests)

### Verification Scripts (`tests/verification/`)

These are demonstration and verification scripts that show the system working with real data:
- `test_analyzer.py` - Verifies document structure analyzer on real documents
- `test_llm_analyzer.py` - Verifies LLM-enhanced analyzer on real documents

**Run verification scripts:**
```bash
pytest tests/verification/ -v -s
```

**Note:** Verification scripts require:
- LLM API keys
- Real data files in `data/` directory
- Generate output files and detailed print statements

## Running All Tests

```bash
# Run all tests (unit + integration, excludes verification)
pytest tests/ -v --ignore=tests/verification

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing --ignore=tests/verification

# Run specific test file
pytest tests/test_models.py -v

# Run specific test
pytest tests/test_models.py::test_model_manager_initialization -v
```

## CI/CD Pipeline

The GitHub Actions CI pipeline (`.github/workflows/ci.yml`) runs:
1. Code format checks (isort, yapf)
2. Type checking (mypy)
3. All tests except verification scripts

Verification scripts are meant to be run manually to verify new features or demonstrate capabilities.

## Adding New Tests

1. **Unit tests**: Add `test_*.py` files in `tests/` directory
2. **Integration tests**: Add `test_*.py` files in `tests/integration/`
3. **Verification scripts**: Add to `tests/verification/` for manual testing

## Test Configuration

- **pytest.ini/pyproject.toml**: Pytest configuration
- **conftest.py**: Adds `src/` to Python path, provides shared fixtures
- **Python versions**: Tests run on Python 3.8-3.12
