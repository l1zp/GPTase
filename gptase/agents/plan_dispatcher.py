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
import time
from typing import Any, Dict, List, Optional

from gptase.agents import Agent
from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import TaskResult
from gptase.agents.types import AgentTask
from gptase.agents.types import PlannedTask
from gptase.memory.manager import MemoryManager
from gptase.models.model import Model

logger = logging.getLogger(__name__)


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
            result = await agent.process_task(agent_task)

            execution_time = time.time() - start_time

            # Build TaskResult
            task_result = TaskResult(
                agent_id=task.agent_id,
                task_id=task.task_id,
                action=task.action,
                status=result.get("status", "success"),
                data=result.get("data"),
                error=result.get("error"),
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
            resolved[key] = self._resolve_value(value, context)

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

    def _resolve_value(self, value: Any, context: ExecutionContext) -> Any:
        """Resolve a single value, handling template strings.

        Args:
            value: The value to resolve.
            context: Execution context.

        Returns:
            The resolved value.
        """
        if not isinstance(value, str):
            return value

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
            return self._resolve_task_reference(var_name, context)

        # Handle context variables
        if var_name in context.variables:
            return context.variables[var_name]

        # Try input_data
        if var_name in context.input_data:
            return context.input_data[var_name]

        # Unknown variable - return as-is with warning
        logger.warning("Unknown template variable: %s", var_name)
        return value

    def _resolve_task_reference(self, ref: str, context: ExecutionContext) -> Any:
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

        # If no field path, return full data
        if len(parts) == 1:
            return task_data

        # Navigate nested field path
        field_path = parts[1]
        return self._get_nested_field(task_data, field_path)

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
        if not content:
            return None

        # Strip whitespace
        content = content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            # Extract JSON from ```json ... ```
            parts = content.split("```json")
            if len(parts) > 1:
                json_part = parts[1].split("```")[0].strip()
                try:
                    return json.loads(json_part)
                except (json.JSONDecodeError, ValueError):
                    # Try to repair common JSON issues
                    try:
                        # Remove trailing commas
                        import re
                        json_part_fixed = re.sub(r',\s*([}\]])', r'\1', json_part)
                        return json.loads(json_part_fixed)
                    except (json.JSONDecodeError, ValueError):
                        pass
        elif content.startswith("```"):
            # Extract from generic code block
            parts = content.split("```")
            if len(parts) > 1:
                json_part = parts[1].strip()
                # Skip language identifier if present
                if "\n" in json_part:
                    json_part = json_part.split("\n", 1)[1]
                try:
                    return json.loads(json_part)
                except (json.JSONDecodeError, ValueError):
                    pass

        # Try direct JSON parse
        if content.startswith("{") or content.startswith("["):
            try:
                return json.loads(content)
            except (json.JSONDecodeError, ValueError):
                pass

        # Try to find JSON object anywhere in the content
        import re
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def clear_agents(self) -> None:
        """Clear cached agent instances."""
        self._agents.clear()
        logger.debug("Cleared agent cache")
