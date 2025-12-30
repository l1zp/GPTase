import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.agents.base import BaseAgent
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry


class LiteratureAgent(BaseAgent):
    """Specialized agent for:
    1) Literature Data Extraction (Markdown enzyme reactions)
    2) Pipeline Documentation (data flow, steps, validations, transformations)
    3) JSON Persistence of extracted data and pipeline summary
    """

    def __init__(
        self, agent_id: str, memory_manager: MemoryManager, tool_registry: ToolRegistry
    ):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=[
                "extraction",
                "pipeline_documentation",
                "validation",
                "persistence",
            ],
        )
        self.logger = logging.getLogger(__name__)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process literature extraction task.

        Expected task shape:
        {
            "files": ["data/example1.md", ...],
            "output_path": "data/extraction/results.json"  # optional
        }
        """
        await self.update_status("processing", task.get("id"))

        errors: List[str] = []
        validations: List[str] = []
        steps: List[Dict[str, Any]] = []
        reactions_all = []

        files: List[str] = task.get("files", [])
        if not files:
            errors.append("No files provided")
            await self.update_status("error", task.get("id"))
            return {"status": "error", "error": "No files provided"}

        # Step: Load and extract
        for fpath in files:
            steps.append(
                {
                    "name": "load_markdown",
                    "description": f"Load {fpath}",
                    "status": "started",
                }
            )
            try:
                # Use DocumentLoaderTool to read file content
                result = await self.tools.execute_tool(
                    "document_loader",
                    {"source_type": "file", "path": fpath},
                )
                if result.status.value != "success":
                    errors.append(f"Failed to read {fpath}: {result.error}")
                    steps[-1]["status"] = "failed"
                    continue
                text = result.data.get("text", "")
                steps[-1]["status"] = "completed"

                # Step: parse
                steps.append(
                    {
                        "name": "parse_markdown",
                        "description": f"Parse {fpath}",
                        "status": "started",
                    }
                )
                reactions = parse_markdown(text, source_file=fpath)
                steps[-1]["status"] = "completed"

                # Step: validation
                for rx in reactions:
                    issues = validate_reaction(rx)
                    if issues:
                        errors.extend([f"{fpath}: {issue}" for issue in issues])
                    else:
                        validations.append(f"{fpath}: reaction validated OK")
                reactions_all.extend(reactions)

            except Exception as e:
                self.logger.error(f"Extraction error for {fpath}: {e}")
                errors.append(f"Exception for {fpath}: {e}")
                steps[-1]["status"] = "failed"

        # Step: persistence
        steps.append(
            {
                "name": "persist_json",
                "description": "Save results to JSON",
                "status": "started",
            }
        )
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_out = (
                Path("data") / "extraction" / f"enzyme_extraction_{timestamp}.json"
            )
            out_path = Path(task.get("output_path") or default_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            output_model = build_output(
                reactions_all, steps=steps, validations=validations, errors=errors
            )
            payload = json.dumps(output_model.model_dump(), indent=2)

            write_res = await self.tools.execute_tool(
                "code_writer",
                {"file_path": str(out_path), "content": payload, "overwrite": True},
            )
            if write_res.status.value == "success":
                steps[-1]["status"] = "completed"
                await self.update_status("completed", task.get("id"))
                return {
                    "status": "success",
                    "output_path": str(out_path),
                    "reactions_count": len(reactions_all),
                    "errors": errors,
                    "validations": validations,
                    "pipeline_steps": steps,
                }
            else:
                steps[-1]["status"] = "failed"
                await self.update_status("error", task.get("id"))
                return {
                    "status": "error",
                    "error": write_res.error,
                    "reactions_count": len(reactions_all),
                    "pipeline_steps": steps,
                }

        except Exception as e:
            steps[-1]["status"] = "failed"
            await self.update_status("error", task.get("id"))
            return {"status": "error", "error": str(e), "pipeline_steps": steps}
