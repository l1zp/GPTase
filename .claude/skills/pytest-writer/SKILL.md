---
name: pytest-writer
description: |
  Write pytest tests for GPTase source code following project conventions. ALWAYS
  trigger when the user asks to: write tests, add pytest, add test coverage, create
  a test file, test a function or class, improve coverage, add unit tests, add
  integration tests, what needs testing, missing tests, untested code, write a test
  for, test this module, check coverage, how do I test this.
  Also trigger when the user shares a source file and asks "does this have tests?"
  or when pytest output shows uncovered lines and the user wants to fix that.
  Do NOT trigger for: running existing tests (use Bash directly), debugging a
  failing test, or explaining what existing tests do.
---

# pytest-writer

A skill for writing pytest tests that follow GPTase conventions, covering the full
cycle from analyzing source code to verifying tests pass.

## Project Test Conventions

### File organization

Source path to test path mapping (match the existing pattern):
- `gptase/agents/*.py` -> `tests/test_agents/test_<name>.py`
- `gptase/sop/*.py` -> `tests/test_sop.py` (single flat file for the module)
- `gptase/models/*.py` -> `tests/test_models.py`
- `gptase/core/*.py` -> `tests/test_<name>.py` at root of `tests/`
- New modules with many classes: create `tests/test_<module>/` subdirectory

Add to an existing test file when one exists. Create a new file only when none exists.

### Asyncio

`asyncio_mode = "auto"` is configured in `pyproject.toml`. This means:
- Do NOT add `@pytest.mark.asyncio` to any test method -- ever
- Write `async def test_...` and pytest handles it automatically
- Many existing test files still have this decorator -- they are legacy; ignore them

### Class structure

Group tests by the class or logical feature being tested:

```python
class TestClassName:
    """Tests for ClassName."""

    def test_specific_behavior(self):
        ...
```

Module-level functions without a class still go inside a class named after the
feature (e.g., `class TestParseMarkdown:`).

### Arrange-Act-Assert

Keep each test body focused on one behavior:

```python
def test_something(self):
    # Arrange
    agent = Agent(system_prompt="Test")
    task = AgentTask(description="Do work")

    # Act
    result = agent._extract_image_paths(task)

    # Assert
    assert result == []
```

Many small tests > one large test.

### Mocking

Import mocks at the top of the file, not inline:

```python
from unittest.mock import MagicMock, patch, AsyncMock
```

`MagicMock` for synchronous dependencies, `AsyncMock` for coroutines. Patch at the
narrowest scope: patch the name where the function is *used*, not where it is *defined*.

### Fixtures (from tests/conftest.py)

Always check `tests/conftest.py` before creating new fixtures. Available:
- `framework_config` -- FrameworkConfig instance
- `mock_model_config` -- ModelConfig with LOCAL provider, model "test-model"
- `sample_image_png(tmp_path)` -- path to a 1x1 pixel PNG file
- `sample_image_jpeg(tmp_path)` -- path to a minimal JPEG file
- `sample_images_dir(tmp_path)` -- directory with image1.png and image2.jpg

File-scoped fixtures go at the top of that test file. If a fixture would be useful
across multiple test files, propose adding it to `tests/conftest.py` instead.

### API-dependent tests

Put in `tests/integration/`. Add `@pytest.mark.requires_api_key` plus a skip guard:

```python
@pytest.mark.requires_api_key
async def test_real_call(self):
    import os
    if not os.getenv("API_KEY"):
        pytest.skip("No API key configured")
    ...
```

Unit tests must never make real API calls -- mock the provider or model layer instead.

### Exception testing

```python
def test_invalid_input_raises(self):
    with pytest.raises(ValueError, match="Expected error text fragment"):
        some_function(invalid_input)
```

Include `match=` whenever the error message is meaningful to verify.

---

## Workflow

### Phase 1: Understand what needs testing

1. Read the target source file(s). Identify:
   - All public methods and functions
   - Non-trivial private methods (ones with real logic, not just attribute access)
   - Edge cases: empty inputs, None, type mismatches, missing files
   - Async vs. sync methods
   - Exception paths (`raise`, custom exceptions from `gptase/utils/`)

2. Check for an existing test file:
   ```
   Glob: tests/**/*<module_name>*
   ```
   If found, read it to see what is already covered and the local style choices.

3. Read `tests/conftest.py` to know which fixtures are available.

4. Find a style reference matching the type of code:
   - Pydantic model -> `tests/test_sop.py` (TestSOPStep, TestSOPDefinition)
   - Agent subclass -> `tests/test_agent_multimodal.py`
   - Async model calls -> `tests/test_models.py`

### Phase 2: Plan coverage (do not write code yet)

List the test cases you plan to write, organized by class:

```
TestClassName:
  - test_basic_creation: happy path with required fields only
  - test_default_values: verify optional fields default correctly
  - test_invalid_input_raises: error path with bad input
  - test_async_method: async happy path
```

Share this plan with the user and confirm scope before writing if there are
ambiguities about expected behavior.

### Phase 3: Write the tests

Apply all conventions from the section above. Key reminders:
- No `@pytest.mark.asyncio`
- All tests inside `class Test...`
- Arrange-Act-Assert in every test body
- `from unittest.mock import ...` at top of file
- Use fixtures from `conftest.py` where applicable

### Phase 4: Verify tests pass

```bash
conda run -n llm pytest tests/path/to/test_file.py -v --tb=short
```

Do not report success until you have seen green pytest output. If tests fail,
read the error, fix the issue, and run again.

### Phase 5: Coverage analysis (only if requested)

```bash
conda run -n llm pytest tests/ \
    --cov=gptase.module.submodule \
    --cov-report=term-missing \
    tests/path/to/test_file.py
```

For each uncovered line, decide: worth testing / dead code / integration-only.

---

## Common Pitfalls in This Codebase

- **`AgentTask` is Pydantic**: test field validators and defaults, not just construction.
  The class is defined in `gptase/agents/types.py`.

- **`Agent._parse_markdown` raises `ValueError`** for invalid YAML frontmatter.
  Always test the error path. The Agent class is in `gptase/agents/base.py`.

- **`SOPRegistry` is a singleton**: call `SOPRegistry.reset_instance()` in setup
  AND teardown to prevent test pollution. See `tests/test_sop.py` TestSOPRegistry
  for the correct pattern.

- **Mocking `Agent._run_with_llm`**: the method accepts either a string or a list
  depending on whether the task includes images. Mock accordingly.

---

## Output Format

1. Show the full test file content (not just snippets)
2. Show the pytest run output confirming all tests pass
3. If coverage was requested: list uncovered lines and categorize each one
