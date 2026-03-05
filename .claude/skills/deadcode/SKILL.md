---
name: deadcode
description: |
  DELETE unused code. ALWAYS trigger when user says: remove, delete, unused, dead, orphaned, deprecated, old, legacy, leftover, clean up, coverage 0%, is this used, references, touched in years, help me remove, want to delete, verify safe to remove.
---

# Dead Code Removal

A systematic, safety-first workflow for identifying and removing unreferenced code from the codebase.

## Core Principle

**Never remove code without verification.** The goal is to confidently identify truly dead code while avoiding false positives that could break the system.

## Workflow

### Phase 1: Discovery and Analysis

1. **Understand the target**
   - Ask the user to specify what code they want to remove (function, class, module, file)
   - Clarify the scope: single file, package, or entire codebase
   - Note any known constraints (e.g., "this is legacy code", "we migrated away from this")

2. **Search for references**
   - Use Grep to find all occurrences of the target name
   - Search for imports: `from X import target` and `import X.target`
   - Search for usages: function calls, class instantiations, attribute access
   - Check string references: configuration files, docs, test fixtures

3. **Check exports and public APIs**
   - Review `__init__.py` files for exports
   - Check for `__all__` declarations
   - Look for public API documentation
   - Search for decorator-based registration (e.g., `@pytest.fixture`, `@click.command`)

4. **Identify dynamic usage patterns**
   - `getattr(obj, "target_name")` - dynamic attribute access
   - `importlib.import_module()` - dynamic imports
   - String-based configuration that references code names
   - Entry points in `setup.py` or `pyproject.toml`
   - Plugin systems and registries

### Phase 2: Verification and Reporting

5. **Present findings to user**
   ```
   ## Dead Code Analysis Report

   Target: `function_name` in `path/to/file.py`

   ### References Found
   - Imports: X locations
   - Usages: Y locations
  - Test references: Z locations
   - Config mentions: N locations

   ### Risk Assessment
   - [ ] Static references only
   - [ ] Dynamic usage possible
   - [ ] Public API impact
   - [ ] Test coverage exists

   ### Recommendation
   [SAFE TO REMOVE / NEEDS REVIEW / DO NOT REMOVE]

   Files to modify:
   - path/to/file.py (remove function)
   - path/to/__init__.py (remove export)
   - tests/test_x.py (remove tests)
   ```

6. **Wait for user confirmation**
   - Never proceed without explicit approval
   - If unsure, ask clarifying questions
   - Offer alternatives (deprecation, comments, conditional removal)

### Phase 3: Safe Removal

7. **Execute removal in order**
   - Remove test files/tests first
   - Remove usages and imports
   - Remove the target code itself
   - Update `__init__.py` and exports
   - Remove any related documentation

8. **Verify with tests**
   ```bash
   pytest tests/ -v
   ```

9. **Check for import errors**
   ```bash
   python -c "import package_name"
   ```

10. **Offer to commit**
    - Suggest a clear commit message
    - Wait for approval before committing

## Language-Specific Guidance

### Python

- Check `__all__` in `__init__.py`
- Look for `@register` decorators
- Search `setup.py` entry_points
- Check `pyproject.toml` for script entry points
- Consider `typing.TYPE_CHECKING` blocks

### JavaScript/TypeScript

- Check `package.json` exports
- Look for dynamic `require()` calls
- Search for string-based imports
- Check barrel files (`index.js` exports)

### General

- Always check for string references in configs
- Look for reflection/introspection patterns
- Consider plugin/extension systems
- Check CI/CD configurations

## Edge Cases

### False Positive Risks

1. **Dynamic imports**
   ```python
   module = importlib.import_module(f"plugins.{name}")
   # Searching for "plugins" won't catch this
   ```

2. **String-based references**
   ```python
   func = getattr(module, function_name)
   # function_name might come from config
   ```

3. **Registration decorators**
   ```python
   @registry.register("handler_name")
   class Handler: ...
   # The decorator registers it, no direct reference needed
   ```

4. **Test fixtures**
   ```python
   @pytest.fixture
   def my_fixture(): ...
   # Used by name in test parameters
   ```

### Handling Uncertainty

When you cannot be 100% certain:

1. **Add a deprecation warning**
   ```python
   import warnings
   warnings.warn("This function will be removed in v2.0", DeprecationWarning)
   ```

2. **Comment instead of delete**
   ```python
   # DEPRECATED: Removed as of 2024-01-15
   # def old_function(): ...
   ```

3. **Create a tracking issue**
   - Document the uncertainty
   - Request user testing
   - Set a removal timeline

## Tools Reference

| Tool | Purpose |
|------|---------|
| Grep | Search for text patterns across files |
| Glob | Find files matching a pattern |
| Read | Examine file contents |
| Edit | Make targeted file changes |
| Bash | Run tests and verification commands |

## Examples

### Example 1: Removing a simple unused function

```
User: Remove the `calculate_discount` function from utils.py

Assistant:
1. Grep for "calculate_discount" across the codebase
2. Check utils.py for function definition
3. Check __init__.py for exports
4. Find: No references found, function is not exported
5. Present report: "Safe to remove"
6. After confirmation, remove function
7. Run tests to verify
```

### Example 2: Potentially used code

```
User: Can I remove the `ProcessManager` class?

Assistant:
1. Grep for "ProcessManager"
2. Find: Referenced in config/settings.yaml
3. Find: Used in tests/test_processes.py
4. Present report: "Not safe - still has active references"
5. Suggest: Deprecate first, or verify with team
```

## Commit Message Template

```
refactor: remove unused [function/class/module] `name`

- Removed `name` from `path/to/file.py`
- Updated exports in `__init__.py`
- Removed related tests

No references found in codebase search.
```

## Checklist Before Removal

- [ ] Searched for all text references
- [ ] Checked dynamic import patterns
- [ ] Reviewed public API documentation
- [ ] Identified and removed related tests
- [ ] Updated exports and `__init__.py` files
- [ ] User confirmed the removal
- [ ] Tests pass after removal
