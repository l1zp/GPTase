import json
from pathlib import Path
from typing import Any, Dict

from src.models.manager import ModelManager
from src.models.types import ModelConfig
from src.models.types import ModelProvider
from src.models.types import ModelRole

from ..base import BaseAgent


class HelloWorldAgent(BaseAgent):

    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(agent_id, memory_manager, tool_registry, ["hello_world"])
        self.model_config = self._load_model_config()
        self.model_manager = ModelManager(self.model_config)

    def _load_model_config(self) -> ModelConfig:
        # Locate project root and template config
        project_root = Path(__file__).resolve().parents[4]
        config_path = project_root / "config" / "llm_config.template.json"

        with open(config_path, "r") as f:
            data = json.load(f)

        # Use CUSTOM provider (MockProvider) to avoid external dependencies
        return ModelConfig(
            provider=ModelProvider.CUSTOM,
            model_name=data.get("model_name", "mock-model"),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            temperature=data.get("temperature", 0.1),
            max_tokens=data.get("max_tokens", 2000),
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Return a Hello World message generated via the model manager."""
        await self.update_status("processing", task.get("id"))
        try:
            prompt = task.get("prompt") or "Hello World"
            messages = [{"role": "user", "content": prompt}]
            response = await self.model_manager.generate(messages,
                                                         role=ModelRole.GENERAL)

            await self.update_status("completed", task.get("id"))
            return {
                "status": "success",
                "message": response.content,
                "model": response.model,
                "provider": response.provider,
                "agent_id": self.agent_id,
            }
        except Exception as e:
            await self.update_status("error", task.get("id"))
            return {"status": "error", "error": str(e), "agent_id": self.agent_id}
