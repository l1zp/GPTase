class AgentDispatchError(Exception):
    pass


"""Task dispatcher for Plan workflow execution.

This module provides the TaskDispatcher class for dispatching tasks
to agents and collecting results, supporting both sequential and
parallel execution.
"""

import asyncio
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional

from gptase.agents import Agent
from gptase.agents.types import AgentMode
from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import TaskResult
from gptase.agents.types import AgentTask
from gptase.agents.types import PlannedTask
from gptase.memory.manager import MemoryManager
from gptase.models.model import Model
from gptase.utils.json_utils import parse_json_content

logger = logging.getLogger(__name__)

_TASK_OUTPUT_REF_RE = re.compile(r"^output(?:s)?\s+from\s+task(?:s)?\s+(.+)$",
                                 re.IGNORECASE)
_TASK_RANGE_RE = re.compile(r"(\w+)\s+through\s+(\w+)", re.IGNORECASE)
_TASK_ID_RE = re.compile(r"task\s+(\w+)", re.IGNORECASE)


class TaskDispatcher:
    """Dispatcher for dispatching tasks to agents and collecting results.

    Handles the dispatch-collect pattern for SOP execution:
    - Creates agents on demand from the factory
    - Dispatches tasks with resolved inputs
    - Collects and aggregates results
    - Supports both sequential and parallel dispatch

    Attributes:
        agent_factory: Factory for creating agent instances.
        memory_manager: Memory manager for agents.
        model_manager: Optional model manager for LLM agents.
    """

    _FIGURE_IMAGE_RE = re.compile(r'!\[\]\((images/[^)]+)\)')
    _FIGURE_CAPTION_RE = re.compile(r'^(?:Fig\.|Figure)\s+(\d+)\s*\|', re.IGNORECASE)

    def __init__(
        self,
        memory_manager: MemoryManager,
        model_manager: Optional[Model] = None,
    ):
        """Initialize the task dispatcher.

        Args:
            memory_manager: Memory manager for agents.
            model_manager: Optional model manager for LLM agents.
        """
        self.memory_manager = memory_manager
        self.model_manager = model_manager
        self._agents: Dict[str, Agent] = {}

    async def _get_agent(self, agent_id: str) -> Agent:
        """Get or create an agent instance.

        Agents are cached after creation for reuse within the same
        SOP execution.

        Args:
            agent_id: The agent identifier.

        Returns:
            The agent instance.

        Raises:
            AgentDispatchError: If agent creation fails.
        """
        if agent_id in self._agents:
            return self._agents[agent_id]

        try:
            agent = Agent.from_markdown(
                agent_id,
                model_manager=self.model_manager,
            )
            self._agents[agent_id] = agent
            logger.info("Created agent instance for '%s'", agent_id)
            return agent
        except Exception as e:
            raise AgentDispatchError(
                agent_id=agent_id,
                reason=f"Failed to create agent: {e}",
                original_error=e,
            ) from e

    async def dispatch(
        self,
        task: PlannedTask,
        context: ExecutionContext,
    ) -> TaskResult:
        """Dispatch a single task to an agent.

        Resolves template variables in the step inputs, creates the
        agent if needed, and dispatches the task.

        Args:
            task: The workflow step to dispatch.
            context: Current execution context for variable resolution.

        Returns:
            TaskResult from the agent execution.
        """
        start_time = time.time()

        try:
            # Get the agent
            agent = await self._get_agent(task.agent_id)

            # The agent's workspace for executing tools should be the input document folder
            agent.workspace_dir = context.document_path or context.workspace_dir

            # Provision agent output workspace dynamically for parsed intermediate results
            agent_workspace = None
            if context.workspace_dir:
                agent_workspace = Path(context.workspace_dir) / task.agent_id
                agent_workspace.mkdir(parents=True, exist_ok=True)

            # Resolve inputs with template substitution
            resolved_inputs = self._resolve_inputs(task.inputs, context)
            input_error = self._validate_resolved_inputs(task, resolved_inputs)
            if input_error:
                execution_time = time.time() - start_time
                return TaskResult(
                    agent_id=task.agent_id,
                    task_id=task.task_id,
                    action=task.action,
                    status="failed",
                    error=input_error,
                    failure_category="invalid_input",
                    execution_time=execution_time,
                )

            # Normalize image-related fields: extract paths from image metadata dicts
            resolved_inputs = self._normalize_image_fields(resolved_inputs)

            # Build the agent task
            agent_task = AgentTask(
                action=task.action,
                task_id=task.task_id,
                **resolved_inputs,
            )

            logger.info(
                "Dispatching step '%s' to agent '%s' with action '%s'",
                task.task_id,
                task.agent_id,
                task.action,
            )

            # Execute the task
            result = await agent.process_task_with_mode(agent_task, mode=AgentMode.DIRECT)
            result_data = result.get("data") or {}
            if isinstance(result_data, dict):
                parsed_output = self._extract_structured_payload(result_data)
                if parsed_output is not None:
                    parsed_output = self._enrich_structured_output(task, resolved_inputs,
                                                                  parsed_output)
                    result_data = dict(result_data)
                    result_data["parsed_output"] = parsed_output
                    result["data"] = result_data

            output_error = self._validate_task_output(task, resolved_inputs, result)
            if output_error:
                result["status"] = "failed"
                result["error"] = output_error
                result["failure_category"] = "invalid_output"

            execution_time = time.time() - start_time

            # Build TaskResult
            task_result = TaskResult(
                agent_id=task.agent_id,
                task_id=task.task_id,
                action=task.action,
                status=result.get("status", "success"),
                data=result.get("data"),
                trace=result.get("trace"),
                error=result.get("error"),
                failure_category=result.get("failure_category"),
                execution_time=execution_time,
            )

            if task_result.is_success():
                # Auto-save intermediate output
                if agent_workspace and task_result.data:
                    output_file = agent_workspace / f"{task.task_id}_result.json"
                    try:
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(task_result.data, f, indent=2, ensure_ascii=False)
                        logger.debug(
                            "Saved step '%s' result to workspace at %s",
                            task.task_id,
                            output_file,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to save step result to %s: %s",
                            output_file,
                            e,
                        )

                    # Post-process the result to extract formatted files
                    self._post_process_result(task, task_result, agent_workspace)

                logger.info(
                    "Step '%s' completed successfully in %.2fs",
                    task.task_id,
                    execution_time,
                )
            else:
                logger.warning(
                    "Step '%s' failed: %s",
                    task.task_id,
                    task_result.error,
                )

            return task_result

        except AgentDispatchError:
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Step '%s' dispatch failed: %s",
                task.task_id,
                e,
            )
            return TaskResult(
                agent_id=task.agent_id,
                task_id=task.task_id,
                action=task.action,
                status="failed",
                error=str(e),
                failure_category="dispatch_error",
                execution_time=execution_time,
            )

    def _post_process_result(self, step: PlannedTask, task_result: TaskResult,
                             agent_workspace: Path):
        """Parse LLM string output into structured JSON and CSV files."""
        if not task_result.data or not isinstance(task_result.data, dict):
            return

        content = task_result.data.get("content")
        if not content or not isinstance(content, str):
            return

        # Try to parse the content as JSON
        try:
            clean_content = content.strip()
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0]
            elif clean_content.startswith("```"):
                clean_content = clean_content.split("```")[1].split("```")[0]

            parsed_data = json.loads(clean_content.strip())
        except Exception as e:
            logger.debug("Could not parse LLM output as JSON for step '%s': %s",
                         step.task_id, e)
            return

        # Write the parsed JSON
        json_path = agent_workspace / f"{step.task_id}_parsed.json"
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)
            logger.debug("Saved parsed JSON to %s", json_path)
        except Exception as e:
            logger.warning("Failed to write parsed JSON: %s", e)

        # Helper to write list of dicts to CSV
        def write_csv(data_list, filename):
            if not data_list or not isinstance(data_list, list) or len(
                    data_list) == 0 or not isinstance(data_list[0], dict):
                return
            import csv

            try:
                # Find all unique keys across all dictionaries
                keys = []
                for item in data_list:
                    for k in item.keys():
                        if k not in keys:
                            keys.append(k)

                csv_path = agent_workspace / filename
                with open(csv_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    for item in data_list:
                        # Convert nested structures to strings to avoid errors
                        row = {
                            k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                            for k, v in item.items()
                        }
                        writer.writerow(row)
                logger.debug("Saved extracted CSV to %s", csv_path)
            except Exception as e:
                logger.warning("Failed to write CSV %s: %s", filename, e)

        # Extract CSVs based on recognized keys
        if "extracted_tables" in parsed_data:
            # E.g. Vision Image Analyzer
            for i, tbl in enumerate(parsed_data["extracted_tables"]):
                csv_data = tbl.get("csv_data")
                img_num = tbl.get("image_number", i + 1)
                if csv_data:
                    csv_path = agent_workspace / f"table_{img_num}.csv"
                    try:
                        with open(csv_path, "w", encoding="utf-8") as f:
                            f.write(csv_data)
                        logger.debug("Saved CSV data to %s", csv_path)
                    except Exception as e:
                        logger.warning("Failed to write table CSV: %s", e)

        # General extraction for lists of objects
        for key in ["reactions", "tables", "images", "sections", "analysis_results"]:
            if key in parsed_data and isinstance(parsed_data[key], list):
                write_csv(parsed_data[key], f"{step.task_id}_{key}.csv")

    async def dispatch_parallel(
        self,
        steps: List[PlannedTask],
        context: ExecutionContext,
        max_concurrent: int = 10,
    ) -> List[TaskResult]:
        """Dispatch multiple steps in parallel.

        Executes all steps concurrently and collects results. Uses
        a semaphore to limit concurrent execution.

        Args:
            steps: List of steps to dispatch.
            context: Current execution context.
            max_concurrent: Maximum concurrent executions.

        Returns:
            List of TaskResults in the same order as steps.
        """
        logger.info(
            "Dispatching %d steps in parallel (max %d concurrent)",
            len(steps),
            max_concurrent,
        )

        semaphore = asyncio.Semaphore(max_concurrent)

        async def dispatch_with_semaphore(step: PlannedTask) -> TaskResult:
            async with semaphore:
                return await self.dispatch(step, context)

        # Dispatch all steps concurrently
        tasks = [dispatch_with_semaphore(step) for step in steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to TaskResults
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                step = steps[i]
                final_results.append(
                    TaskResult(
                        agent_id=step.agent_id,
                        task_id=step.task_id,
                        action=step.action,
                        status="failed",
                        error=str(result),
                    ))
            else:
                final_results.append(result)

        # Log summary
        success_count = sum(1 for r in final_results if r.is_success())
        logger.info(
            "Parallel dispatch complete: %d/%d succeeded",
            success_count,
            len(steps),
        )

        return final_results

    def _resolve_inputs(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Resolve template variables in inputs.

        Supports the following template patterns:
        - {{input_text}}: Value from context.input_data
        - {{step1}}: Full result data from step "1"
        - {{step1.field}}: Nested field access from step result
        - {{document_path}}: The document path from context

        Args:
            inputs: Input dictionary with potential template values.
            context: Execution context for variable resolution.

        Returns:
            Dictionary with resolved values.
        """
        resolved = {}

        for key, value in inputs.items():
            resolved[key] = self._resolve_value(value, context, input_key=key)

        return resolved

    def _normalize_image_fields(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize image-related fields for AgentTask compatibility.

        When images come from step results (e.g., {{step1.images}}), they may be
        a list of image metadata dicts with 'image_path' fields. AgentTask expects
        a list of strings (paths). This method extracts paths from such dicts.

        If image_path is missing but figure_id is present, tries to construct
        a path from the figure_id.

        Args:
            inputs: Input dictionary with potentially nested image data.

        Returns:
            Dictionary with normalized image fields.
        """
        image_fields = ["images", "image_paths"]
        workspace = inputs.get("workspace_dir") or inputs.get("document_path")

        for field in image_fields:
            if field not in inputs:
                continue

            value = inputs[field]
            if not isinstance(value, list):
                continue

            # Check if it's a list of dicts with image_path
            if value and isinstance(value[0], dict):
                paths = []
                for item in value:
                    if isinstance(item, str):
                        paths.append(item)
                    elif isinstance(item, dict):
                        # Try image_path first
                        if "image_path" in item and item["image_path"]:
                            paths.append(item["image_path"])
                        elif workspace:
                            # Fallback: try to find image by figure_id in workspace
                            figure_id = item.get("figure_id", "")
                            # Extract figure number (e.g., "Figure 3a" -> "3a")
                            import re
                            match = re.search(r"Figure\s*(\d+[a-z]?)", figure_id,
                                              re.IGNORECASE)
                            if match:
                                fig_num = match.group(1)
                                # Try common image locations
                                img_patterns = [
                                    f"images/figure_{fig_num}.png",
                                    f"images/fig_{fig_num}.png",
                                    f"images/Figure_{fig_num}.png",
                                    f"images/Fig_{fig_num}.png",
                                ]
                                for pattern in img_patterns:
                                    test_path = Path(workspace) / pattern
                                    if test_path.exists():
                                        paths.append(pattern)
                                        logger.debug("Found image path %s for %s",
                                                     pattern, figure_id)
                                        break
                if paths:
                    inputs[field] = paths
                    logger.debug(
                        "Normalized '%s' field: extracted %d paths from %d items",
                        field,
                        len(paths),
                        len(value),
                    )
                else:
                    # No paths found - clear the field to avoid validation error
                    inputs[field] = []
                    logger.warning(
                        "Could not extract image paths from '%s' field, clearing it",
                        field)

        return inputs

    def _resolve_value(
        self,
        value: Any,
        context: ExecutionContext,
        input_key: Optional[str] = None,
    ) -> Any:
        """Resolve a single value, handling template strings.

        Args:
            value: The value to resolve.
            context: Execution context.

        Returns:
            The resolved value.
        """
        if isinstance(value, dict):
            return {
                k: self._resolve_value(v, context, input_key=k)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self._resolve_value(v, context, input_key=input_key) for v in value]
        if not isinstance(value, str):
            return value

        placeholder_value = self._resolve_placeholder_reference(value, context, input_key)
        if placeholder_value is not None:
            return placeholder_value

        # Check for template pattern {{...}}
        if not value.startswith("{{") or not value.endswith("}}"):
            return value

        # Extract variable name
        var_name = value[2:-2].strip()

        # Handle special variables
        if var_name == "input_text":
            return context.input_data.get("text", "")
        if var_name == "document_path":
            return context.document_path or context.input_data.get("document_path", "")
        if var_name == "input_data":
            return context.input_data

        # Handle step references: step1, step1.field.nested
        if var_name.startswith("step"):
            return self._resolve_task_reference(var_name, context, input_key=input_key)

        # Handle context variables
        if var_name in context.variables:
            return context.variables[var_name]

        # Try input_data
        if var_name in context.input_data:
            return context.input_data[var_name]

        # Unknown variable - return as-is with warning
        logger.warning("Unknown template variable: %s", var_name)
        return value

    def _resolve_task_reference(
        self,
        ref: str,
        context: ExecutionContext,
        input_key: Optional[str] = None,
    ) -> Any:
        """Resolve a reference to a step result.

        Handles patterns like:
        - step1 -> full result from step "1"
        - step2a -> full result from step "2a"
        - step1.analysis.images -> nested field access

        Args:
            ref: The step reference string (e.g., "step1.field").
            context: Execution context.

        Returns:
            The resolved value or None if not found.
        """
        parts = ref.split(".", 1)
        task_key = parts[0]

        # Extract step ID (remove "step" prefix)
        if task_key.startswith("step"):
            task_id = task_key[4:]
        else:
            task_id = task_key

        # Get step data
        task_data = context.get_task_data(task_id)
        if task_data is None:
            logger.warning("Step '%s' not found in context", task_id)
            return None

        structured_data = self._get_structured_task_data(task_data)

        # If no field path, return full data
        if len(parts) == 1:
            return self._coerce_task_output_for_input(input_key, structured_data)

        # Navigate nested field path
        field_path = parts[1]
        return self._get_nested_field(structured_data, field_path)

    def _get_nested_field(self, data: Any, path: str) -> Any:
        """Get a nested field from data using dot notation.

        Handles special case where 'content' field contains markdown-wrapped JSON.
        When a field is not found directly, tries to parse 'content' and look there.

        Args:
            data: The data dictionary.
            path: Dot-separated field path (e.g., "analysis.images").

        Returns:
            The nested value or None if not found.
        """
        current = data
        for part in path.split("."):
            if isinstance(current, dict):
                # Try to get the field directly first
                if part in current:
                    current = current[part]
                # If field is 'content', parse it
                elif part == "content" and "content" in current:
                    content = current["content"]
                    if isinstance(content, str):
                        parsed = self._try_parse_content_json(content)
                        if parsed is not None:
                            current = parsed
                        else:
                            current = content
                    else:
                        current = content
                # If field not found but there's a 'content' field, try parsing it
                elif "content" in current:
                    content = current["content"]
                    if isinstance(content, str):
                        parsed = self._try_parse_content_json(content)
                        if parsed is not None and isinstance(parsed,
                                                             dict) and part in parsed:
                            current = parsed[part]
                        else:
                            return None
                    else:
                        return None
                else:
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    def _try_parse_content_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Try to parse JSON from content, handling markdown code blocks.

        Args:
            content: String content that may contain JSON.

        Returns:
            Parsed JSON dict or None if parsing fails.
        """
        parsed = parse_json_content(content)
        if isinstance(parsed, dict):
            return parsed
        return None

    def _resolve_placeholder_reference(
        self,
        value: str,
        context: ExecutionContext,
        input_key: Optional[str],
    ) -> Any:
        match = _TASK_OUTPUT_REF_RE.match(value.strip())
        if not match:
            return None

        ref_text = match.group(1).strip()
        range_match = _TASK_RANGE_RE.search(ref_text)
        if range_match:
            task_ids = self._expand_task_range(range_match.group(1), range_match.group(2))
            return {
                task_id: self._coerce_task_output_for_input(
                    None,
                    self._get_structured_task_data(context.get_task_data(task_id)),
                )
                for task_id in task_ids
                if context.get_task_data(task_id) is not None
            }

        task_ids = _TASK_ID_RE.findall(ref_text)
        if not task_ids and ref_text:
            task_ids = [ref_text]

        if len(task_ids) == 1:
            task_data = context.get_task_data(task_ids[0])
            if task_data is None:
                return None
            return self._coerce_task_output_for_input(
                input_key,
                self._get_structured_task_data(task_data),
            )

        bundle = {}
        for task_id in task_ids:
            task_data = context.get_task_data(task_id)
            if task_data is None:
                continue
            bundle[task_id] = self._get_structured_task_data(task_data)
        return bundle or None

    def _expand_task_range(self, start: str, end: str) -> List[str]:
        try:
            start_num = int(start)
            end_num = int(end)
        except ValueError:
            return [start, end]
        if start_num > end_num:
            start_num, end_num = end_num, start_num
        return [str(i) for i in range(start_num, end_num + 1)]

    def _get_structured_task_data(self, task_data: Optional[Dict[str, Any]]) -> Any:
        if not isinstance(task_data, dict):
            return task_data
        if "parsed_output" in task_data:
            return task_data["parsed_output"]
        parsed_output = self._extract_structured_payload(task_data)
        return parsed_output if parsed_output is not None else task_data

    def _extract_structured_payload(self, data: Dict[str, Any]) -> Optional[Any]:
        parsed_output = data.get("parsed_output")
        if parsed_output is not None:
            return parsed_output
        content = data.get("content")
        if isinstance(content, str):
            parsed = parse_json_content(content)
            if parsed is not None:
                return parsed
        return None

    def _enrich_structured_output(
        self,
        task: PlannedTask,
        resolved_inputs: Dict[str, Any],
        parsed_output: Any,
    ) -> Any:
        if task.agent_id != "document-structure-analyzer":
            return parsed_output
        if not isinstance(parsed_output, dict):
            return parsed_output

        document_path = resolved_inputs.get("document_path")
        if not isinstance(document_path, str) or not document_path:
            return parsed_output

        document_file = Path(document_path)

        deterministic_images = self._extract_main_figure_images(document_file)
        if not deterministic_images:
            return parsed_output

        images = parsed_output.get("images")
        if not isinstance(images, list):
            images = []

        images_by_path = {
            item.get("image_path"): item
            for item in images
            if isinstance(item, dict) and item.get("image_path")
        }

        supplemented: List[Dict[str, Any]] = []
        for number, item in enumerate(deterministic_images, start=1):
            merged = dict(images_by_path.get(item["image_path"], {}))
            merged.update(item)
            merged["image_number"] = number
            supplemented.append(merged)

        if supplemented != images:
            parsed_output = dict(parsed_output)
            parsed_output["images"] = supplemented
            logger.info(
                "Normalized document structure output to %d named figures from markdown",
                len(supplemented),
            )

        return parsed_output

    def _extract_main_figure_images(self, document_file: Path) -> List[Dict[str, Any]]:
        if not document_file.is_file():
            return []

        try:
            text = document_file.read_text(encoding="utf-8")
        except Exception:
            return []

        main_text = text.split("\n# Online content", 1)[0]
        results: List[Dict[str, Any]] = []
        pending_paths: List[str] = []
        for raw_line in main_text.splitlines():
            line = raw_line.strip()
            image_match = self._FIGURE_IMAGE_RE.search(line)
            if image_match:
                pending_paths.append(image_match.group(1))
                continue

            caption_match = self._FIGURE_CAPTION_RE.match(line)
            if caption_match and pending_paths:
                figure_number = caption_match.group(1)
                if len(pending_paths) == 1:
                    figure_ids = [f"Figure {figure_number}"]
                else:
                    figure_ids = [
                        f"Figure {figure_number}{chr(ord('a') + idx)}"
                        for idx in range(len(pending_paths))
                    ]

                for figure_id, image_path in zip(figure_ids, pending_paths):
                    results.append({
                        "image_path": image_path,
                        "figure_id": figure_id,
                        "is_reaction_related": True,
                        "reasoning": "Auto-extracted from markdown main-figure block.",
                    })
                pending_paths = []

        return results

    def _coerce_task_output_for_input(self, input_key: Optional[str], value: Any) -> Any:
        if not input_key or not isinstance(value, dict):
            return value

        normalized_key = input_key.lower()
        if normalized_key in {"candidate_sequences", "initial_candidate_sequences"}:
            for candidate_key in ("candidate_sequences", "designed_sequences", "sequences"):
                candidate_value = value.get(candidate_key)
                if candidate_value is not None:
                    return candidate_value
        if normalized_key in {"template_pdb", "template_pdb_for_prediction"}:
            for candidate_key in ("template_pdb", "template_pdb_for_prediction",
                                  "best_template_pdb"):
                candidate_value = value.get(candidate_key)
                if candidate_value:
                    return candidate_value
        return value

    def _validate_resolved_inputs(self, task: PlannedTask,
                                  resolved_inputs: Dict[str, Any]) -> Optional[str]:
        issues: List[str] = []
        for key, value in resolved_inputs.items():
            original = task.inputs.get(key)
            if self._looks_like_placeholder(original):
                if value is None or value == original:
                    issues.append(f"{key}: unresolved reference '{original}'")
            if self._contains_low_quality_signal(value):
                issues.append(f"{key}: upstream result is insufficient for downstream work")
            fatal_error = self._extract_fatal_error(value)
            if fatal_error:
                issues.append(f"{key}: upstream fatal error: {fatal_error}")

        if issues:
            return "Task blocked due to invalid upstream inputs: " + "; ".join(issues)
        return None

    def _validate_task_output(
        self,
        task: PlannedTask,
        resolved_inputs: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Optional[str]:
        if result.get("status") != "success":
            return None

        data = result.get("data")
        if not isinstance(data, dict):
            return None

        structured = self._extract_structured_payload(data)
        if isinstance(structured, dict):
            fatal_error = structured.get("fatal_error")
            if fatal_error:
                return str(fatal_error)

            if structured.get("data_sufficiency") == "low":
                return f"Task {task.task_id} returned insufficient research data"
            if structured.get("data_completeness") == "low":
                return f"Task {task.task_id} returned incomplete database data"

            candidate_sequences = structured.get("candidate_sequences")
            if isinstance(candidate_sequences, list) and candidate_sequences:
                if all(
                    isinstance(item, dict) and not item.get("sequence")
                    for item in candidate_sequences
                ):
                    return (
                        f"Task {task.task_id} did not produce usable candidate sequences"
                    )

        if ("candidate_sequences" in resolved_inputs
                and not self._has_real_sequence_inputs(resolved_inputs["candidate_sequences"])
                and isinstance(structured, dict)
                and structured.get("predictions")):
            return f"Task {task.task_id} reported predictions without valid input sequences"

        return None

    def _looks_like_placeholder(self, value: Any) -> bool:
        return isinstance(value, str) and _TASK_OUTPUT_REF_RE.match(value.strip()) is not None

    def _contains_low_quality_signal(self, value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("data_sufficiency") == "low":
                return True
            if value.get("data_completeness") == "low":
                return True
            return any(self._contains_low_quality_signal(v) for v in value.values())
        if isinstance(value, list):
            return any(self._contains_low_quality_signal(v) for v in value)
        return False

    def _extract_fatal_error(self, value: Any) -> Optional[str]:
        if isinstance(value, dict):
            fatal_error = value.get("fatal_error")
            if fatal_error:
                return str(fatal_error)
            for nested in value.values():
                found = self._extract_fatal_error(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = self._extract_fatal_error(nested)
                if found:
                    return found
        return None

    def _has_real_sequence_inputs(self, value: Any) -> bool:
        if isinstance(value, list):
            return any(
                isinstance(item, dict) and bool(item.get("sequence"))
                for item in value
            )
        return False

    def clear_agents(self) -> None:
        """Clear cached agent instances."""
        self._agents.clear()
        logger.debug("Cleared agent cache")
