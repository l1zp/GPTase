#!/bin/bash
# Production startup script

echo "🚀 Starting GPTase Production Environment"
echo "📊 Web Dashboard: http://localhost:8000"
echo "🔧 API Docs: http://localhost:8000/docs"

# Install production dependencies
pip install -r requirements/prod.txt

# Start the web server
uvicorn src.web.app:create_app --host 0.0.0.0 --port 8000 --workers 4 --factory