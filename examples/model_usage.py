#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path to import GPTase package
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import from GPTase package shims
from GPTase.models.manager import ModelManager
from GPTase.core.config import FrameworkConfig, ModelConfigExtended
from GPTase.models.types import ModelConfig, ModelProvider, ModelRole

async def main():
    """Demonstrate model configuration and usage."""
    
    print("🤖 Model Configuration Demo")
    print("=" * 40)
    
    # Load template configuration
    config_path = Path(__file__).parent.parent / "config" / "llm_config.template.json"
    with open(config_path, 'r') as f:
        template_config = json.load(f)

    # Example 1: Basic configuration
    print("\n📊 Example 1: Basic Model Setup")
    config = FrameworkConfig(
        llm=ModelConfigExtended(
            provider=ModelProvider.CUSTOM,
            model_name=template_config['model_name'],
            api_key=template_config.get('api_key', ''),
            base_url=template_config.get('base_url', ''),
            temperature=0.1,
            max_tokens=2000
        )
    )
    
    # Initialize ModelManager with default configuration
    manager = ModelManager(
        default_config=ModelConfig(
            provider=ModelProvider.CUSTOM,
            model_name=template_config['model_name'],
            api_key=template_config.get('api_key', ''),
            base_url=template_config.get('base_url', ''),
            temperature=0.1,
            max_tokens=2000
        )
    )
    
    # Check model health
    health = await manager.health_check()
    print(f"Model health: {health}")
    
    # Example 2: Role-specific configurations
    print("\n🎯 Example 2: Role-Specific Models")
    
    # Different models for different roles
    advanced_config = FrameworkConfig(
        llm=ModelConfigExtended(
            provider=ModelProvider.CUSTOM,
            model_name=template_config['model_name'],
            api_key=template_config.get('api_key', ''),
            base_url=template_config.get('base_url', ''),
            planner_config=ModelConfig(
                provider=ModelProvider.CUSTOM,
                model_name=template_config['model_name'],
                temperature=0.1
            ),
            executor_config=ModelConfig(
                provider=ModelProvider.CUSTOM,
                model_name=template_config['model_name'],
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
    openai_models = await manager.list_available_models(ModelProvider.CUSTOM)
    print(f"Custom models: {openai_models}")
    
    local_models = await manager.list_available_models(ModelProvider.LOCAL)
    print(f"Local models: {local_models}")
    
    # Example 4: Model usage statistics
    print("\n📊 Example 4: Usage Statistics")
    stats = manager.get_usage_stats()
    print(f"Stats: {stats}")
    
    print("\n🧹 Demo complete")

if __name__ == "__main__":
    asyncio.run(main())
