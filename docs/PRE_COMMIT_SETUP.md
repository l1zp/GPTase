# Pre-commit Hooks Setup Summary

## ✅ What Was Done

### 1. Updated Pre-commit Configuration ([`.pre-commit-config.yaml`](../.pre-commit-config.yaml))
- Added more pre-commit hooks for better code quality:
  - `check-ast`: Validate Python AST
  - `check-json`: Validate JSON files
  - `check-toml`: Validate TOML files
  - `check-xml`: Validate XML files
- Updated isort to use `--filter-files` flag
- Updated yapf to use `--recursive` flag for better coverage

### 2. Enhanced CI Configuration ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml))
- Added helpful error messages when format checks fail
- Included instructions for auto-fixing formatting issues
- Made it easier for developers to understand and fix CI failures

### 3. Created Setup Script ([`scripts/setup_hooks.sh`](../scripts/setup_hooks.sh))
- One-command installation of pre-commit hooks
- User-friendly output with clear instructions
- Executable and ready to use

### 4. Added Documentation
- **[CODE_STYLE.md](CODE_STYLE.md)**: Comprehensive code style guide
- Updated **README.md**: Added pre-commit hooks section with clear instructions

## 🚀 How to Use

### First-Time Setup

```bash
# Run the setup script
./scripts/setup_hooks.sh
```

That's it! Pre-commit hooks are now installed and will run automatically on every commit.

### Daily Development

Just commit your code as usual:

```bash
git add .
git commit -m "Your commit message"
```

Pre-commit hooks will:
1. Automatically format your code (isort + yapf)
2. Check for common issues
3. Either pass or fix issues automatically
4. If issues can't be auto-fixed, it will block the commit and show you what to fix

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

## 🎯 Benefits

1. **Zero Friction**: Code is formatted automatically on every commit
2. **Consistent Style**: All code follows the same formatting rules
3. **Fewer CI Failures**: Most formatting issues are caught and fixed locally
4. **Better Code Quality**: Additional checks for common issues
5. **Team Alignment**: Everyone uses the same formatting rules

## 📋 What Gets Checked

### Every Commit
- ✅ Import sorting (isort with Google profile)
- ✅ Code formatting (yapf)
- ✅ Trailing whitespace removal
- ✅ End-of-file fixes
- ✅ Python AST validation
- ✅ Merge conflict detection
- ✅ Debug statement detection
- ✅ JSON/YAML/TOML validation

### Files Checked
- All Python files (`src/`, `tests/`, `examples/`, `pipelines/`)
- Configuration files (JSON, YAML, TOML, XML)

## 🔧 Troubleshooting

### Hooks Not Running

```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install
```

### Hook Fails and You Don't Know Why

```bash
# Run with verbose output
pre-commit run --all-files --verbose
```

### Need to Skip Hooks (Not Recommended)

```bash
# Skip hooks for this commit
git commit --no-verify -m "Your message"
```

⚠️ **Warning**: Only use `--no-verify` in emergencies. Your code should normally pass all hooks.

### CI Still Fails After Running Hooks

```bash
# Make sure hooks fixed everything
pre-commit run --all-files

# Check what's modified
git status

# Commit the fixes
git add .
git commit -m "Style: Apply pre-commit fixes"
```

## 📚 Additional Resources

- [Pre-commit Documentation](https://pre-commit.com/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [yapf Documentation](https://github.com/google/yapf)
- [Project Code Style Guide](CODE_STYLE.md)

## ✨ Summary

With these changes, every commit will automatically format your code, ensuring:
- Consistent code style across the entire project
- Fewer CI failures
- Less time spent on manual formatting
- Higher code quality

Just run `./scripts/setup_hooks.sh` once, and you're set! 🎉
