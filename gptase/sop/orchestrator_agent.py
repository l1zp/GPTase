"""Unified SOP Orchestrator Agent.

This module provides the SOPOrchestratorAgent class that drives all
SOP execution. It reads SOP definitions, dispatches tasks to
specialized agents, and aggregates results.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid

from gptase.agents.base import BaseAgent
from gptase.core.config import FrameworkConfig
from gptase.core.constants import STATUS_ERROR
from gptase.core.constants import STATUS_SUCCESS
from gptase.memory.manager import MemoryManager
from gptase.models.model import Model
from gptase.sop.dispatcher import TaskDispatcher
from gptase.sop.exceptions import SOPExecutionError
from gptase.sop.failure_handler import FailureHandler
from gptase.sop.loader import SOPLoader
from gptase.sop.loader import SOPRegistry
from gptase.sop.types import ExecutionContext
from gptase.sop.types import FailureDecision
from gptase.sop.types import ParallelStep
from gptase.sop.types import SOPDefinition
from gptase.sop.types import SOPStep
from gptase.sop.types import StepResult
from gptase.sop.types import StepStatus
from gptase.sop.types import TaskResult

logger = logging.getLogger(__name__)


class SOPOrchestratorAgent(BaseAgent):
    """Unified orchestrator agent for all SOP execution.

    This agent:
    1. Reads SOP definition from registry
    2. Dispatches tasks to specialized agents
    3. Collects and aggregates results
    4. Handles failures with AI-driven recovery

    The orchestrator supports:
    - Sequential step execution
    - Parallel step execution
    - Template variable resolution
    - Failure recovery (abort/skip/retry)
    - Session tracking for persistence

    Attributes:
        loader: SOP definition loader.
        registry: SOP registry for discovery.
        dispatcher: Task dispatcher for agent execution.
        failure_handler: Failure recovery handler.
    """

    AGENT_NAME = "sop_orchestrator"

    def __init__(
        self,
        config: Optional[FrameworkConfig] = None,
        memory_manager: Optional[MemoryManager] = None,
        model_manager: Optional[Model] = None,
        sop_dir: Optional[str] = None,
    ):
        """Initialize the SOP orchestrator.

        Args:
            config: Framework configuration.
            memory_manager: Memory manager for agents.
            model_manager: Optional model manager for LLM agents.
            sop_dir: Optional custom SOP directory.
        """
        self.config = config or FrameworkConfig()

        # Create a memory manager if not provided
        if memory_manager is None:
            from gptase.memory.manager import MemoryManager

            memory_manager = MemoryManager(config=self.config.memory)

        # Create a model manager if not provided
        if model_manager is None:
            from gptase.models.model import Model

            model_manager = Model()

        super().__init__(
            agent_id="sop_orchestrator",
            memory_manager=memory_manager,
            model_manager=model_manager,
            capabilities=[
                "sop_execution",
                "workflow_orchestration",
                "agent_dispatch",
                "failure_recovery",
            ],
        )

        self.loader = SOPLoader()
        self.registry = SOPRegistry.get_instance()
        self.dispatcher = TaskDispatcher(
            agent_factory=self._create_agent_factory(),
            memory_manager=memory_manager,
            model_manager=model_manager,
        )
        self.failure_handler = FailureHandler(model=model_manager)

    def _create_agent_factory(self):
        """Create an agent factory for the dispatcher."""
        from gptase.agents.markdown_agent import MarkdownAgentFactory

        return MarkdownAgentFactory()

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process an SOP execution task.

        Args:
            task: Task dictionary with:
                - plan_id: SOP definition to execute
                - input_data: Initial input data
                - document_path: Optional document path

        Returns:
            Dictionary with status and aggregated results.
        """
        plan_id = task.get("plan_id")
        input_data = task.get("input_data", task.get("input", {}))
        document_path = task.get("document_path")

        if not plan_id:
            return {
                "status": STATUS_ERROR,
                "error": "Missing required field: plan_id",
            }

        try:
            result = await self.execute_sop(
                plan_id=plan_id,
                input_data=input_data,
                document_path=document_path,
            )
            return result
        except SOPExecutionError as e:
            logger.error("SOP execution failed: %s", e)
            return {
                "status": STATUS_ERROR,
                "error": str(e),
                "details": e.details,
            }
        except Exception as e:
            logger.error("Unexpected error during SOP execution: %s", e)
            return {
                "status": STATUS_ERROR,
                "error": str(e),
            }

    async def execute_sop(
        self,
        plan_id: str,
        input_data: Dict[str, Any],
        document_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute an SOP workflow.

        Args:
            plan_id: SOP definition to execute.
            input_data: Initial input (document_path, text, etc.).
            document_path: Optional document path for resolving relative paths.

        Returns:
            Aggregated results from all steps.
        """
        # Load the SOP definition
        sop = self.registry.get_sop(plan_id)

        logger.info(
            "Starting SOP execution: %s (%s)",
            sop.name or plan_id,
            plan_id,
        )

        # Initialize execution context
        session_id = self._generate_session_id()
        context = ExecutionContext(
            plan_id=plan_id,
            input_data=input_data,
            document_path=document_path,
            session_id=session_id,
        )

        # Store input_data in variables for easy access
        context.set_variable("input_data", input_data)
        if "text" in input_data:
            context.set_variable("input_text", input_data["text"])

        # Start session tracking
        await self._start_session(sop, context)

        try:
            # Execute workflow
            for workflow_item in sop.workflow:
                if isinstance(workflow_item, ParallelStep):
                    await self._execute_parallel(workflow_item, context, sop)
                else:
                    await self._execute_step(workflow_item, context, sop)

            # Mark as success
            result = context.to_result()
            result["status"] = STATUS_SUCCESS

            logger.info("SOP execution completed successfully: %s", plan_id)

            return result

        except SOPExecutionError:
            raise
        except Exception as e:
            logger.error("SOP execution failed with unexpected error: %s", e)
            raise SOPExecutionError(
                plan_id=plan_id,
                reason=f"Unexpected error: {e}",
                original_error=e,
            ) from e

    async def _execute_step(
        self,
        step: SOPStep,
        context: ExecutionContext,
        sop: SOPDefinition,
    ) -> StepResult:
        """Execute a single workflow step.

        Args:
            step: The step to execute.
            context: Execution context.
            sop: Parent SOP definition.

        Returns:
            StepResult from the execution.
        """
        logger.info(
            "Executing step '%s': %s",
            step.step_id,
            step.description or step.action,
        )

        context.current_step = step.step_id

        # Initialize step result
        step_result = StepResult(
            step_id=step.step_id,
            status=StepStatus.RUNNING,
        )
        context.update_step_result(step.step_id, step_result)

        # Dispatch the task
        result = await self.dispatcher.dispatch(step, context)

        # Handle success
        if result.is_success():
            step_result.status = StepStatus.SUCCESS
            step_result.result = result
            context.update_step_result(step.step_id, step_result)
            return step_result

        # Handle failure
        return await self._handle_failure(step, result, context, sop)

    async def _execute_parallel(
        self,
        parallel_step: ParallelStep,
        context: ExecutionContext,
        sop: SOPDefinition,
    ) -> None:
        """Execute parallel steps.

        Args:
            parallel_step: Group of parallel steps.
            context: Execution context.
            sop: Parent SOP definition.
        """
        steps = parallel_step.parallel
        logger.info(
            "Executing %d parallel steps: %s",
            len(steps),
            [s.step_id for s in steps],
        )

        # Dispatch all steps in parallel
        results = await self.dispatcher.dispatch_parallel(
            steps=steps,
            context=context,
            max_concurrent=sop.max_parallel,
        )

        # Process results
        for step, result in zip(steps, results):
            step_result = StepResult(
                step_id=step.step_id,
                status=StepStatus.SUCCESS if result.is_success() else StepStatus.FAILED,
                result=result,
            )

            if result.is_success():
                context.update_step_result(step.step_id, step_result)
            else:
                # Handle individual failure
                await self._handle_failure(step, result, context, sop)

    async def _handle_failure(
        self,
        step: SOPStep,
        result: TaskResult,
        context: ExecutionContext,
        sop: SOPDefinition,
    ) -> StepResult:
        """Handle a step failure with recovery logic.

        Args:
            step: The failed step.
            result: The failed task result.
            context: Execution context.
            sop: Parent SOP definition.

        Returns:
            Final StepResult after recovery attempt.

        Raises:
            SOPExecutionError: If abort is decided.
        """
        error = result.error or "Unknown error"
        logger.warning(
            "Step '%s' failed: %s",
            step.step_id,
            error,
        )

        # Get recovery decision
        attempt = 0
        max_retries = step.retry_count or sop.default_retry_count or 3

        while True:
            decision = await self.failure_handler.decide(
                step=step,
                error=error,
                context=context,
                attempt=attempt,
            )

            step_result = StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                result=result,
                failure_decision=decision,
            )

            if decision == FailureDecision.ABORT:
                logger.error(
                    "Step '%s' failure is critical, aborting SOP",
                    step.step_id,
                )
                context.update_step_result(step.step_id, step_result)
                raise SOPExecutionError(
                    plan_id=context.plan_id,
                    step_id=step.step_id,
                    reason=error,
                )

            if decision == FailureDecision.SKIP:
                logger.info(
                    "Skipping failed step '%s' (optional or non-critical)",
                    step.step_id,
                )
                step_result.status = StepStatus.SKIPPED
                context.update_step_result(step.step_id, step_result)
                return step_result

            if decision == FailureDecision.RETRY:
                attempt += 1
                if attempt > max_retries:
                    logger.error(
                        "Max retries exceeded for step '%s', aborting",
                        step.step_id,
                    )
                    context.update_step_result(step.step_id, step_result)
                    raise SOPExecutionError(
                        plan_id=context.plan_id,
                        step_id=step.step_id,
                        reason=f"Max retries exceeded: {error}",
                    )

                logger.info(
                    "Retrying step '%s' (attempt %d/%d)",
                    step.step_id,
                    attempt,
                    max_retries,
                )

                # Retry the step
                result = await self.dispatcher.dispatch(step, context)

                if result.is_success():
                    step_result.status = StepStatus.SUCCESS
                    step_result.result = result
                    step_result.retry_attempts = attempt
                    context.update_step_result(step.step_id, step_result)
                    return step_result

                # Update error for next iteration
                error = result.error or "Unknown error"
                continue

        # Should not reach here
        return step_result

    def _generate_session_id(self) -> str:
        """Generate a unique session ID.

        Returns:
            UUID-based session ID.
        """
        return f"sop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def _start_session(self, sop: SOPDefinition,
                             context: ExecutionContext) -> None:
        """Start session tracking for the SOP execution.

        Args:
            sop: The SOP definition.
            context: Execution context.
        """
        logger.debug(
            "Starting session %s for SOP %s",
            context.session_id,
            sop.plan_id,
        )

        # Store session info in memory for tracking
        # This could be extended to use ConversationStorage
        session_info = {
            "session_id": context.session_id,
            "plan_id": sop.plan_id,
            "name": sop.name,
            "start_time": datetime.now().isoformat(),
            "input_data": context.input_data,
        }

        await self.memory.store_agent_state(self.state)
        logger.info("Session started: %s", context.session_id)

    def list_available_sops(self) -> List[Dict[str, str]]:
        """List all available SOP definitions.

        Returns:
            List of dictionaries with SOP metadata.
        """
        return self.registry.list_sops()

    def get_sop(self, plan_id: str) -> SOPDefinition:
        """Get an SOP definition by plan_id.

        Args:
            plan_id: The SOP identifier.

        Returns:
            The SOPDefinition.
        """
        return self.registry.get_sop(plan_id)

    async def close(self) -> None:
        """Close all resources owned by this orchestrator.

        Should be called before program exit to properly close database
        connections and prevent aiosqlite 'Event loop is closed' errors.
        """
        # Close memory manager storage (BaseAgent uses 'memory' attribute)
        if self.memory:
            await self.memory.close()

        # Close model manager tracking storage if present
        if self.model_manager and hasattr(self.model_manager, "tracking_storage"):
            if self.model_manager.tracking_storage:
                await self.model_manager.tracking_storage.close()

        logger.debug("SOPOrchestratorAgent resources closed")
