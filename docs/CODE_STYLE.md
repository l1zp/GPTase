# Code Style Guide

This document explains how to format and style code in the GPTase project.

## Automatic Formatting (Recommended)

### Pre-commit Hooks (Recommended)

The project uses pre-commit hooks to automatically format code on every commit.

```bash
# Install pre-commit hooks (one-time setup)
./scripts/setup_hooks.sh

# Or manually:
pip install pre-commit
pre-commit install
```

Now every time you commit, pre-commit will automatically:
- Sort imports with isort (Google profile)
- Format code with yapf
- Remove trailing whitespace
- Fix end-of-file issues
- Check for common issues

### Manual Formatting

If you need to format code manually:

```bash
# Format imports
isort --profile=google src/ tests/ examples/

# Format code
yapf --in-place --parallel --recursive src/ tests/ examples/
```

## Code Style Tools

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

## CI/CD Pipeline

The CI pipeline automatically checks code formatting on every pull request:

1. **Format Check**: Verifies isort and yapf compliance
2. **Lint**: Runs mypy for type checking
3. **Test**: Runs pytest across Python 3.8-3.12

If format check fails, the CI will provide instructions on how to fix.

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

# Check formatting without modifying
isort --check-only --diff --profile=google src/
yapf --diff --parallel --recursive src/

# Type check
mypy src/ --ignore-missing-imports
```

## Troubleshooting

### Pre-commit hooks not running

Make sure hooks are installed:
```bash
pre-commit install
```

### Format check fails in CI

Run the format commands locally:
```bash
pip install yapf isort
isort --profile=google src/ tests/ examples/
yapf --in-place --parallel --recursive src/ tests/ examples/
git add .
git commit
```

Or simply run pre-commit on all files:
```bash
pre-commit run --all-files
```
