"""High-level working-memory service for named agents."""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Union

from gptase.memory.manager import MemoryManager
from gptase.memory.models import AgentWorkingMemory

_DEFAULT_MAX_SUMMARY_CHARS = 1200
_SECTION_DIVIDER = "\n\n"
_SUMMARY_SECTION_PATTERN = re.compile(
    r"(Recent context|Latest task|Latest result):\s*(.*?)(?=\s+(?:Recent context|Latest task|Latest result):|\Z)",
    re.DOTALL,
)


class AgentMemoryService:
    """Build, inject, and update compressed working memory for agents."""

    def __init__(self,
                 memory_manager: MemoryManager,
                 config: Optional[Any] = None) -> None:
        self.memory_manager = memory_manager
        self.config = config

    def is_enabled_for(self, agent_id: Optional[str]) -> bool:
        return bool(agent_id) and _get_config_value(self.config, "enabled", True)

    async def build_memory_context(self, agent_id: Optional[str]) -> str:
        """Render working memory as prompt context."""
        if not self.is_enabled_for(agent_id):
            return ""

        memory = await self.memory_manager.get_agent_working_memory(agent_id)
        if memory is None or not memory.summary.strip():
            return ""

        return (
            "Agent Working Memory:\n"
            f"{memory.summary.strip()}\n\n"
            "Use this as prior context when relevant. Prefer the current task if there is a conflict."
        )

    async def update_memory(
        self,
        agent_id: Optional[str],
        task_input: Union[str, List[Dict[str, Any]]],
        result: Dict[str, Any],
    ) -> Optional[AgentWorkingMemory]:
        """Compress the latest successful run into persistent working memory."""
        if not self.is_enabled_for(agent_id):
            return None

        status = result.get("status")
        if status not in {
                "success", "completed"
        } and not _get_config_value(self.config, "update_on_failure", False):
            return None

        existing = await self.memory_manager.get_agent_working_memory(agent_id)
        summary = self._compose_summary(existing.summary if existing else "",
                                        task_input, result)
        if not summary:
            return existing

        memory = AgentWorkingMemory(
            agent_id=agent_id,
            summary=summary,
            metadata={
                "status": status,
                "updated_from": "agent_run",
            },
            last_updated=datetime.now(),
        )
        await self.memory_manager.store_agent_working_memory(memory)
        return memory

    def _compose_summary(
        self,
        existing_summary: str,
        task_input: Union[str, List[Dict[str, Any]]],
        result: Dict[str, Any],
    ) -> str:
        max_chars = int(
            _get_config_value(self.config, "max_summary_chars",
                              _DEFAULT_MAX_SUMMARY_CHARS))

        sections = []
        if existing_summary.strip():
            recent_context = self._summarize_existing_memory(existing_summary,
                                                             max_chars // 3)
            if recent_context:
                sections.append(f"Recent context:\n{recent_context}")

        task_snapshot = self._summarize_task(task_input)
        if task_snapshot:
            sections.append(f"Latest task:\n{task_snapshot}")

        result_snapshot = self._summarize_result(result)
        if result_snapshot:
            sections.append(f"Latest result:\n{result_snapshot}")

        combined = _SECTION_DIVIDER.join(section for section in sections if section)
        return _truncate(combined, max_chars)

    def _summarize_existing_memory(self, existing_summary: str, limit: int) -> str:
        parsed_sections = self._parse_summary_sections(existing_summary)
        snippets: List[str] = []

        latest_result = parsed_sections.get("Latest result")
        if latest_result:
            snippets.append(f"Previous result: {_truncate(latest_result, limit // 2)}")

        latest_task = parsed_sections.get("Latest task")
        if latest_task:
            snippets.append(f"Previous task: {_truncate(latest_task, limit // 2)}")

        if not snippets:
            cleaned = _strip_memory_wrappers(existing_summary)
            if cleaned:
                snippets.append(_truncate(cleaned, limit))

        return _truncate(" | ".join(snippets), limit)

    def _parse_summary_sections(self, summary: str) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for label, content in _SUMMARY_SECTION_PATTERN.findall(summary):
            cleaned = _strip_memory_wrappers(content)
            if cleaned:
                parsed[label] = cleaned
        return parsed

    def _summarize_task(self, task_input: Union[str, List[Dict[str, Any]]]) -> str:
        if isinstance(task_input, str):
            return _truncate(task_input.strip(), 400)

        parts: List[str] = []
        image_count = 0
        for item in task_input:
            if item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]).strip())
            elif item.get("type") == "image_url":
                image_count += 1

        text_summary = _truncate(" ".join(p for p in parts if p), 300)
        if image_count:
            suffix = f" [includes {image_count} image(s)]"
            text_summary = (text_summary
                            + suffix).strip() if text_summary else suffix[1:]
        return text_summary

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        data = result.get("data")
        if isinstance(data, dict):
            content = data.get("content")
            parsed_output = data.get("parsed_output")
            if isinstance(content, str) and content.strip():
                return _truncate(content.strip(), 500)
            if parsed_output is not None:
                return _truncate(_to_compact_json(parsed_output), 500)
            return _truncate(_to_compact_json(data), 500)
        if result.get("error"):
            return _truncate(str(result["error"]), 300)
        return _truncate(_to_compact_json(result), 500)


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:max(limit - 3, 0)].rstrip() + "..."


def _strip_memory_wrappers(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.replace("Agent Working Memory:", "")
    cleaned = cleaned.replace(
        "Use this as prior context when relevant. Prefer the current task if there is a conflict.",
        "",
    )
    cleaned = cleaned.replace("Current Task:", "")
    cleaned = re.sub(r"(Prior context:\s*)+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _to_compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)


def inject_memory_context(
    task: Union[str, List[Dict[str, Any]]],
    memory_context: str,
) -> Union[str, List[Dict[str, Any]]]:
    """Prepend memory context to a task payload."""
    if not memory_context:
        return task
    if isinstance(task, str):
        return f"{memory_context}\n\nCurrent Task:\n{task}"
    return [{"type": "text", "text": memory_context}, *task]


def _get_config_value(config: Optional[Any], key: str, default: Any) -> Any:
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)
