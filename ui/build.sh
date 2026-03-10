#!/bin/bash

# Exit on error
set -e

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Navigate to the ui directory
cd "$SCRIPT_DIR"

echo "----------------------------------------"
echo "🚀 Starting GPTase UI build..."
echo "----------------------------------------"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm not found. Please install Node.js first."
    exit 1
fi

# Install dependencies if node_modules is missing
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Execute build command
echo "🏗️  Generating production static files..."
npm run build

echo ""
echo "----------------------------------------"
echo "✅ Build successful!"
echo "📂 Static files generated in: $SCRIPT_DIR/dist"
echo "💡 You can now run 'gptase web' to start the service."
echo "----------------------------------------"
