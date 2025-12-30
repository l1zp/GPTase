from typing import Any, Dict

from src.agents.base import BaseAgent
from src.models.manager import ModelManager
from src.tools.llm_enzyme_extractor import extract_with_llm


class LLMEnzymeExtractorAgent(BaseAgent):
    def __init__(
        self, agent_id: str, memory_manager, tool_registry, model_manager: ModelManager
    ):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["llm_enzyme_extraction"],
        )
        self.model_manager = model_manager

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        doc = task.get("document") or {}
        source_type = (doc.get("source_type") or "text").lower()
        content = doc.get("content")
        path = doc.get("path")
        url = doc.get("url")

        text = ""
        source_file = "unknown.md"

        if source_type == "text":
            if not content:
                return {"status": "error", "error": "Missing text content"}
            text = str(content)
            source_file = "inline_text.md"
        elif source_type == "file":
            if not path:
                return {"status": "error", "error": "Missing file path"}
            source_file = str(path)
            loaded = await self.tools.execute_tool(
                "document_loader", {"source_type": "file", "path": str(path)}
            )
            if loaded.status.value != "success":
                return {"status": "error", "error": loaded.error or "load_failed"}
            text = loaded.data.get("text", "")
        elif source_type == "url":
            if not url:
                return {"status": "error", "error": "Missing URL"}
            source_file = str(url)
            loaded = await self.tools.execute_tool(
                "document_loader", {"source_type": "url", "url": str(url)}
            )
            if loaded.status.value != "success":
                return {"status": "error", "error": loaded.error or "load_failed"}
            text = loaded.data.get("text", "")
        else:
            return {"status": "error", "error": "Unsupported source_type"}

        data = await extract_with_llm(
            text=text,
            source_file=source_file,
            manager=self.model_manager,
        )

        return {"status": "success", "data": {"extraction": data}}
