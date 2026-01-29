#!/bin/bash
# Setup script for pre-commit hooks
# This script installs pre-commit hooks and runs them on all files

set -e

echo "🔧 Setting up pre-commit hooks for GPTase..."
echo ""

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

echo "✅ Installing pre-commit hooks..."
pre-commit install

echo ""
echo "🎉 Pre-commit hooks installed successfully!"
echo ""
echo "ℹ️  Hooks will now run automatically on every commit."
echo ""
echo "💡 To run hooks manually on all files:"
echo "   pre-commit run --all-files"
echo ""
echo "💡 To run hooks on specific files:"
echo "   pre-commit run --files src/models/types.py"
echo ""
