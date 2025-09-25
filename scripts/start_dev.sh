#!/bin/bash
# Development startup script

echo "🚀 Starting GPTase Development Environment"
echo "📊 Web Dashboard: http://localhost:8000"
echo "🔧 API Docs: http://localhost:8000/docs"

# Install development dependencies
pip install -r requirements/dev.txt

# Start the web server with hot reload
uvicorn src.web.app:create_app --host 0.0.0.0 --port 8000 --reload --factory