"""Task dispatcher for SOP workflow execution.

This module provides the TaskDispatcher class for dispatching tasks
to agents and collecting results, supporting both sequential and
parallel execution.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from gptase.agents.agent import Agent
from gptase.agents.loader import MarkdownAgentFactory
from gptase.memory.manager import MemoryManager
from gptase.models.model import Model
from gptase.sop.exceptions import AgentDispatchError
from gptase.sop.types import ExecutionContext
from gptase.sop.types import SOPStep
from gptase.sop.types import TaskResult

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
        agent_factory: MarkdownAgentFactory,
        memory_manager: MemoryManager,
        model_manager: Optional[Model] = None,
    ):
        """Initialize the task dispatcher.

        Args:
            agent_factory: Factory for creating agent instances.
            memory_manager: Memory manager for agents.
            model_manager: Optional model manager for LLM agents.
        """
        self.agent_factory = agent_factory
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
            agent = self.agent_factory.create_agent(
                agent_id=agent_id,
                memory_manager=self.memory_manager,
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
        step: SOPStep,
        context: ExecutionContext,
    ) -> TaskResult:
        """Dispatch a single task to an agent.

        Resolves template variables in the step inputs, creates the
        agent if needed, and dispatches the task.

        Args:
            step: The workflow step to dispatch.
            context: Current execution context for variable resolution.

        Returns:
            TaskResult from the agent execution.
        """
        start_time = time.time()

        try:
            # Get the agent
            agent = await self._get_agent(step.agent)

            # Resolve inputs with template substitution
            resolved_inputs = self._resolve_inputs(step.inputs, context)

            # Build the task
            task = {
                "action": step.action,
                "step_id": step.step_id,
                **resolved_inputs,
            }

            logger.info(
                "Dispatching step '%s' to agent '%s' with action '%s'",
                step.step_id,
                step.agent,
                step.action,
            )

            # Execute the task
            result = await agent.process_task(task)

            execution_time = time.time() - start_time

            # Build TaskResult
            task_result = TaskResult(
                agent_id=step.agent,
                step_id=step.step_id,
                action=step.action,
                status=result.get("status", "success"),
                data=result.get("data"),
                error=result.get("error"),
                execution_time=execution_time,
            )

            if task_result.is_success():
                logger.info(
                    "Step '%s' completed successfully in %.2fs",
                    step.step_id,
                    execution_time,
                )
            else:
                logger.warning(
                    "Step '%s' failed: %s",
                    step.step_id,
                    task_result.error,
                )

            return task_result

        except AgentDispatchError:
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Step '%s' dispatch failed: %s",
                step.step_id,
                e,
            )
            return TaskResult(
                agent_id=step.agent,
                step_id=step.step_id,
                action=step.action,
                status="failed",
                error=str(e),
                execution_time=execution_time,
            )

    async def dispatch_parallel(
        self,
        steps: List[SOPStep],
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

        async def dispatch_with_semaphore(step: SOPStep) -> TaskResult:
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
                        agent_id=step.agent,
                        step_id=step.step_id,
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
            return self._resolve_step_reference(var_name, context)

        # Handle context variables
        if var_name in context.variables:
            return context.variables[var_name]

        # Try input_data
        if var_name in context.input_data:
            return context.input_data[var_name]

        # Unknown variable - return as-is with warning
        logger.warning("Unknown template variable: %s", var_name)
        return value

    def _resolve_step_reference(self, ref: str, context: ExecutionContext) -> Any:
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
        step_key = parts[0]

        # Extract step ID (remove "step" prefix)
        if step_key.startswith("step"):
            step_id = step_key[4:]
        else:
            step_id = step_key

        # Get step data
        step_data = context.get_step_data(step_id)
        if step_data is None:
            logger.warning("Step '%s' not found in context", step_id)
            return None

        # If no field path, return full data
        if len(parts) == 1:
            return step_data

        # Navigate nested field path
        field_path = parts[1]
        return self._get_nested_field(step_data, field_path)

    def _get_nested_field(self, data: Any, path: str) -> Any:
        """Get a nested field from data using dot notation.

        Args:
            data: The data dictionary.
            path: Dot-separated field path (e.g., "analysis.images").

        Returns:
            The nested value or None if not found.
        """
        current = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current

    def clear_agents(self) -> None:
        """Clear cached agent instances."""
        self._agents.clear()
        logger.debug("Cleared agent cache")
