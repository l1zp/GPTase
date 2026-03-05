---
name: docs
description: |
  Comprehensive documentation update for codebases - sync docs with code, fix inconsistencies, add missing docstrings, update README files, and maintain documentation quality.
  ALWAYS trigger when user mentions: "update documentation", "update docs", "fix the docs", "sync docs with code", "documentation is outdated", "update README", "add docstring", "document this function/class/module", "write API docs", "missing documentation", "docs are wrong", "outdated docs", "document the changes", "update the documentation for X", "add missing docs", "improve documentation".
---

# Documentation Update

Systematically update and maintain documentation to stay in sync with code changes.

## Documentation Types

| Type | Location | Focus |
|------|----------|-------|
| README | `README.md`, `docs/README.md` | Project overview, quick start, installation |
| Feature Docs | `docs/features/*.md` | Feature usage, examples, configuration |
| API Docs | `docs/api/*.md` | Public APIs, parameters, return types |
| Agent Configs | `config/agents/*.md` | Agent capabilities, prompts, metadata |
| Code Docstrings | `*.py` files | Function/class/module documentation |
| Inline Comments | Source files | Complex logic explanations |

## Workflow

### Phase 1: Scope Discovery

1. **Identify target scope**
   - Ask: "Which module/feature needs documentation updates?"
   - Clarify: Single file, entire module, or full project?

2. **Find all related files**
   ```bash
   # Markdown files
   glob "**/*.md"

   # Python files with docstrings
   grep -l '"""' **/*.py

   # Agent configs
   glob "config/agents/*.md"
   ```

3. **Determine update type**
   - Sync with code changes (after refactoring/feature addition)
   - Fix existing inconsistencies
   - Add missing documentation
   - Update outdated examples

### Phase 2: Analysis

1. **Read related code and docs in parallel**
   - Source code: Understand current implementation
   - Existing docs: Identify gaps and inconsistencies
   - Tests: Understand expected behavior

2. **Check for common issues**
   - [ ] Function signatures match documented parameters
   - [ ] Return types are documented and accurate
   - [ ] Code examples are executable and correct
   - [ ] Links and references are valid
   - [ ] Version numbers and dates are current
   - [ ] Agent capabilities match `@capabilities` metadata
   - [ ] CLI commands match actual interface

3. **Prioritize updates**
   - High: Breaking changes, incorrect usage, missing required docs
   - Medium: Outdated examples, stale links
   - Low: Minor wording improvements

### Phase 3: Update Plan

Present a structured plan before making changes:

```markdown
## Documentation Update Plan

### Files to Update
| File | Issue | Action |
|------|-------|--------|
| path/to/file.md | Description | What to change |

### Summary
- X files to update
- Y inconsistencies to fix
- Z examples to verify
```

### Phase 4: Execute Updates

1. **Update documentation files**
   - Fix inconsistencies first
   - Add missing sections
   - Update examples and code snippets
   - Refresh dates if significant changes

2. **Add/update docstrings** (if in scope)
   - Follow Google-style docstrings
   - Include: description, args, returns, raises, examples
   - Keep concise but complete

3. **Verify code examples**
   - Run executable examples if possible
   - Check imports and dependencies
   - Validate output format

## Best Practices

### Writing Style
- Use present tense ("Returns X" not "Will return X")
- Start with verb for function descriptions ("Extract enzyme data from...")
- Include practical examples for complex features
- Link to related documentation

### Consistency Rules
- Same terminology across all docs
- Consistent heading hierarchy
- Standard code block formatting with language tags
- Unified date format (YYYY-MM-DD)

### README Structure
```markdown
# Project Name
Brief description

## Features
## Installation
## Quick Start
## Usage
## API Reference
## Contributing
## License
```

### Docstring Template
```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """Brief one-line description.

    Longer description if needed, explaining behavior,
    edge cases, or important notes.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.

    Example:
        >>> result = function_name("test", 42)
        >>> result["status"]
        'success'
    """
```

## Output Report

After completing updates, provide a summary:

```markdown
## Documentation Update Report

### Files Updated
- `path/to/file1.md`: Fixed parameter names, updated example
- `path/to/file2.md`: Added missing installation section

### Changes Made
- Fixed 3 inconsistencies
- Added 2 new sections
- Verified 5 code examples

### Remaining Items
- [ ] None or list any deferred items
```

## Integration Notes

- **After refactoring**: Run this skill to sync docs with code changes
- **After adding features**: Document new APIs and update feature docs
- **Before releases**: Verify all documentation is current
- **With deadcode removal**: Remove documentation for deleted code
