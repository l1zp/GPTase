"""
Example usage of the frontend interface
"""

import asyncio
import requests
import json

def test_frontend_api():
    """Test the frontend API endpoints."""
    base_url = "http://localhost:8000"
    
    # Test system status
    try:
        response = requests.get(f"{base_url}/api/status")
        status = response.json()
        print("✅ System Status:", json.dumps(status, indent=2))
    except Exception as e:
        print("❌ System status failed:", e)
    
    # Test agents list
    try:
        response = requests.get(f"{base_url}/api/agents")
        agents = response.json()
        print("✅ Agents:", json.dumps(agents, indent=2))
    except Exception as e:
        print("❌ Agents failed:", e)
    
    # Test task creation
    try:
        task = {
            "id": "test_frontend_001",
            "description": "Test the frontend API",
            "priority": "medium"
        }
        response = requests.post(f"{base_url}/api/tasks", json=task)
        result = response.json()
        print("✅ Task Result:", json.dumps(result, indent=2))
    except Exception as e:
        print("❌ Task creation failed:", e)

if __name__ == "__main__":
    print("🚀 Testing Frontend API...")
    test_frontend_api()
    print("🎉 Frontend testing complete!")