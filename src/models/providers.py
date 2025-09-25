"""
LLM provider implementations for different model APIs
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from src.models.types import ModelConfig, ModelResponse, ModelProvider

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)

class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Generate response from the model."""
        pass
        
    @abstractmethod
    async def validate_config(self) -> bool:
        """Validate the provider configuration."""
        pass
        
    async def health_check(self) -> Dict[str, Any]:
        """Check if the provider is healthy."""
        try:
            await self.validate_config()
            return {"status": "healthy", "provider": self.config.provider}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "provider": self.config.provider}

class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        if not openai:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
            
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or None
        )
        
    async def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        if not self.config.api_key:
            raise ValueError("OpenAI API key is required")
        return True
        
    async def generate(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Generate response using OpenAI API."""
        await self.validate_config()
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout
            )
            
            return ModelResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                model=response.model,
                provider=ModelProvider.OPENAI,
                metadata={"response_id": response.id}
            )
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise

class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider implementation."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=config.api_key)
        except ImportError:
            raise ImportError("Anthropic library not installed. Run: pip install anthropic")
            
    async def validate_config(self) -> bool:
        """Validate Anthropic configuration."""
        if not self.config.api_key:
            raise ValueError("Anthropic API key is required")
        return True
        
    async def generate(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Generate response using Anthropic API."""
        await self.validate_config()
        
        try:
            # Convert OpenAI format to Anthropic format
            system_message = None
            conversation_messages = []
            
            for msg in messages:
                if msg.get("role") == "system":
                    system_message = msg.get("content", "")
                else:
                    conversation_messages.append(msg)
            
            response = await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=conversation_messages,
                system=system_message
            )
            
            return ModelResponse(
                content=response.content[0].text,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                model=response.model,
                provider=ModelProvider.ANTHROPIC,
                metadata={"response_id": response.id}
            )
            
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise

class LocalProvider(BaseProvider):
    """Local LLM provider for running models locally."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        
    async def validate_config(self) -> bool:
        """Validate local provider configuration."""
        if not self.config.base_url:
            raise ValueError("Local provider requires base_url")
        return True
        
    async def generate(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Generate response using local LLM API."""
        await self.validate_config()
        
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "stream": False
                }
                
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=self.config.timeout
                ) as response:
                    result = await response.json()
                    
                    return ModelResponse(
                        content=result["choices"][0]["message"]["content"],
                        usage=result.get("usage", {}),
                        model=result["model"],
                        provider=ModelProvider.LOCAL,
                        metadata={"response_id": result.get("id", "local")}
                    )
                    
        except Exception as e:
            self.logger.error(f"Local provider error: {e}")
            raise

class MockProvider(BaseProvider):
    """Mock provider for testing without real API calls."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        
    async def validate_config(self) -> bool:
        """Mock validation always passes."""
        return True
        
    async def generate(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Generate mock response."""
        last_message = messages[-1]["content"] if messages else "Hello"
        
        return ModelResponse(
            content=f"Mock response for: {last_message[:50]}...",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model=self.config.model_name,
            provider=ModelProvider.CUSTOM,
            metadata={"mock": True}
        )