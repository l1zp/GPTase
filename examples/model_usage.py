#!/usr/bin/env python3
"""
Model usage examples for the multi-agent framework
"""

import asyncio
from agents.orchestrator import AgentOrchestrator
from agents.config import FrameworkConfig
from models.types import ModelConfig, ModelProvider, ModelRole

async def main():
    """Demonstrate model configuration and usage."""
    
    print("🤖 Model Configuration Demo")
    print("=" * 40)
    
    # Example 1: Basic configuration
    print("\n📊 Example 1: Basic Model Setup")
    config = FrameworkConfig(
        llm=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            api_key="your-api-key-here",  # Replace with actual key
            temperature=0.1,
            max_tokens=2000
        )
    )
    
    orchestrator = AgentOrchestrator(config)
    
    # Check model health
    health = await orchestrator.model_manager.health_check()
    print(f"Model health: {health}")
    
    # Example 2: Role-specific configurations
    print("\n🎯 Example 2: Role-Specific Models")
    
    # Different models for different roles
    advanced_config = FrameworkConfig(
        llm=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            api_key="your-api-key-here",
            planner_config=ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4",
                temperature=0.1
            ),
            executor_config=ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                temperature=0.2
            ),
            tool_manager_config=ModelConfig(
                provider=ModelProvider.LOCAL,
                model_name="llama2",
                base_url="http://localhost:11434"
            )
        )
    )
    
    # Example 3: Check available models
    print("\n📋 Example 3: Available Models")
    openai_models = await orchestrator.model_manager.list_available_models(ModelProvider.OPENAI)
    print(f"OpenAI models: {openai_models}")
    
    local_models = await orchestrator.model_manager.list_available_models(ModelProvider.LOCAL)
    print(f"Local models: {local_models}")
    
    # Example 4: Model usage statistics
    print("\n📊 Example 4: Usage Statistics")
    stats = orchestrator.model_manager.get_usage_stats()
    print(f"Stats: {stats}")
    
    # Cleanup
    await orchestrator.shutdown()
    print("\n🧹 Framework shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())