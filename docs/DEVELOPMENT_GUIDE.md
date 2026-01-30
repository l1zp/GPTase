# Development Guide

This guide covers code style, formatting tools, and development workflow for the GPTase project.

## Quick Start

```bash
# One-time setup of pre-commit hooks
./scripts/setup_hooks.sh

# Manual formatting
isort --profile=google src/ tests/ examples/
yapf --in-place --parallel --recursive src/ tests/ examples/

# Type checking
mypy src/ --ignore-missing-imports
```

## Code Formatting Tools

### Pre-commit Hooks (Recommended)

The project uses pre-commit hooks to automatically format code on every commit.

```bash
# Install pre-commit hooks (one-time setup)
./scripts/setup_hooks.sh

# Or manually:
pip install pre-commit
pre-commit install
```

Every commit automatically:
- Sorts imports with isort (Google profile)
- Formats code with yapf
- Removes trailing whitespace
- Fixes end-of-file issues
- Checks for common issues

### Manual Formatting

```bash
# Format imports
isort --profile=google src/ tests/ examples/

# Format code
yapf --in-place --parallel --recursive src/ tests/ examples/

# Check formatting without modifying
isort --check-only --diff --profile=google src/
yapf --diff --parallel --recursive src/
```

## Tool Specifications

### isort (Import Sorting)
- **Profile**: Google
- **Config**: Automatically sorts imports according to Google's style guide
- **Run**: `isort --profile=google <files>`

### yapf (Code Formatting)
- **Config**: `.style.yapf`
- **Style**: 88 character line limit, 4 space indent
- **Run**: `yapf --in-place --parallel --recursive <files>`

### mypy (Type Checking)
- **Run**: `mypy src/ --ignore-missing-imports`
- **Status**: Non-blocking (warnings only)

## Pre-commit Configuration

### What Gets Checked

**Every Commit:**
- Import sorting (isort with Google profile)
- Code formatting (yapf)
- Trailing whitespace removal
- End-of-file fixes
- Python AST validation
- Merge conflict detection
- Debug statement detection
- JSON/YAML/TOML validation

**Files Checked:**
- All Python files (`src/`, `tests/`, `examples/`, `pipelines/`)
- Configuration files (JSON, YAML, TOML, XML)

### Manual Pre-commit Usage

```bash
# Run hooks on all files
pre-commit run --all-files

# Run hooks on specific files
pre-commit run --files src/models/types.py

# Update hook versions
pre-commit autoupdate

# Uninstall hooks
pre-commit uninstall
```

## CI/CD Pipeline

The CI pipeline automatically checks code formatting on every pull request:

1. **Format Check**: Verifies isort and yapf compliance
2. **Lint**: Runs mypy for type checking
3. **Test**: Runs pytest across Python 3.8-3.12

If format check fails, the CI will provide instructions on how to fix.

## Benefits

1. **Zero Friction**: Code is formatted automatically on every commit
2. **Consistent Style**: All code follows the same formatting rules
3. **Fewer CI Failures**: Most formatting issues are caught and fixed locally
4. **Better Code Quality**: Additional checks for common issues
5. **Team Alignment**: Everyone uses the same formatting rules

## Troubleshooting

### Pre-commit hooks not running

```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install
```

### Hook fails and you don't know why

```bash
# Run with verbose output
pre-commit run --all-files --verbose
```

### Need to skip hooks (not recommended)

```bash
# Skip hooks for this commit
git commit --no-verify -m "Your message"
```

**Warning**: Only use `--no-verify` in emergencies.

### CI still fails after running hooks

```bash
# Make sure hooks fixed everything
pre-commit run --all-files

# Check what's modified
git status

# Commit the fixes
git add .
git commit -m "Style: Apply pre-commit fixes"
```

## Quick Reference

```bash
# Install and setup pre-commit hooks
./scripts/setup_hooks.sh

# Run hooks manually on all files
pre-commit run --all-files

# Run hooks on specific files
pre-commit run --files src/models/types.py

# Format specific file
isort --profile=google src/models/types.py
yapf --in-place src/models/types.py

# Type check
mypy src/ --ignore-missing-imports
```
