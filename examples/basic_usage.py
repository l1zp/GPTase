#!/usr/bin/env python3
"""
Basic usage examples for the multi-agent framework
"""

import asyncio
from agents.orchestrator import AgentOrchestrator
from agents.config import FrameworkConfig

async def main():
    """Demonstrate basic framework usage."""
    
    # Initialize the framework
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)
    
    print("🚀 Multi-Agent Framework Demo")
    print("=" * 40)
    
    # Example 1: Fibonacci calculation
    print("\n📊 Example 1: Fibonacci Calculation")
    task1 = {
        "id": "fibonacci_demo",
        "description": "Create a Python script that calculates fibonacci numbers and test it",
        "priority": "high"
    }
    
    result1 = await orchestrator.execute_task(task1)
    print(f"✅ Task completed: {result1['status']}")
    
    # Example 2: System status
    print("\n🔍 Example 2: System Status")
    status = await orchestrator.get_system_status()
    print(f"📊 Total agents: {len(status['agents'])}")
    print(f"🔧 Total tools: {status['tools']['total_tools']}")
    
    # Example 3: List agents
    print("\n👥 Example 3: Available Agents")
    agents = await orchestrator.list_available_agents()
    for agent in agents:
        print(f"  • {agent['agent_id']}: {agent['capabilities']}")
    
    # Cleanup
    await orchestrator.shutdown()
    print("\n🧹 Framework shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())