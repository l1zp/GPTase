#!/usr/bin/env python3
"""
GPTase - Multi-Agent Framework
Main entry point for the framework
"""

import asyncio
import sys
from src.core.config import FrameworkConfig
from src.agents.orchestrator import AgentOrchestrator

async def main():
    """Main entry point for the framework."""
    print("🚀 Starting GPTase Multi-Agent Framework")
    
    # Initialize configuration
    config = FrameworkConfig()
    
    # Create orchestrator
    orchestrator = AgentOrchestrator(config)
    
    # Example task
    task = {
        "id": "demo_task_001",
        "description": "Create a Python script that calculates fibonacci numbers",
        "priority": "high"
    }
    
    print(f"🎯 Executing task: {task['description']}")
    result = await orchestrator.execute_task(task)
    
    print("✅ Task completed!")
    print(f"📊 Result: {result['status']}")
    
    # Shutdown gracefully
    await orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(main())