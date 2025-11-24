from typing import Dict, Any
from ..base import BaseAgent
from src.nlp.enzyme_extractor import extract_steps, extract_from_html

class EnzymeDesignAgent(BaseAgent):
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(agent_id, memory_manager, tool_registry, [
            "enzyme_design_extraction", "nlp_parsing", "pdf_html_text_support"
        ])

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        doc = task.get("document", {})
        source_type = (doc.get("source_type") or "text").lower()
        content = doc.get("content")
        path = doc.get("path")
        url = doc.get("url")

        loaded = {"status": "error", "data": {}}
        if source_type == "text":
            loaded = {"status": "success", "data": {"text": content or ""}}
        else:
            res = await self.tools.execute_tool("document_loader", {
                "source_type": source_type,
                "content": content,
                "path": path,
                "url": url,
            })
            loaded = res.model_dump()

        if loaded.get("status") != "success":
            return {"status": "error", "error": loaded.get("error", "load_failed")}

        text = loaded["data"].get("text", "")
        if source_type == "html":
            result = extract_from_html(text)
        else:
            result = extract_steps(text)

        result["annotations_zh"] = "提取到的步骤含保留英文术语，并提供中文标签说明。"
        return {"status": "success", "data": result}
