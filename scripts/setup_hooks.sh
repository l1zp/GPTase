#!/bin/bash
# Setup script for pre-commit hooks

set -e

echo "[INFO] Setting up pre-commit hooks for GPTase..."
echo ""

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "[INFO] Installing pre-commit..."
    pip install pre-commit
fi

echo "[OK] Installing pre-commit hooks..."
pre-commit install

echo ""
echo "[OK] Pre-commit hooks installed successfully!"
echo ""
echo "[INFO] Hooks will now run automatically on every commit."
echo ""
echo "[INFO] Useful commands:"
echo "   pre-commit run --all-files     # Run on all files"
echo "   pre-commit run --files <path>   # Run on specific files"
echo ""
