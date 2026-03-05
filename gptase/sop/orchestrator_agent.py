"""Unified SOP Orchestrator Agent.

This module provides the SOPOrchestratorAgent class that drives all
SOP execution. It reads SOP definitions, dispatches tasks to
specialized agents, and aggregates results.
"""

from datetime import datetime
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from gptase.agents.agent import Agent
from gptase.agents.agent import AgentState
from gptase.core.config import FrameworkConfig
from gptase.core.constants import STATUS_ERROR
from gptase.core.constants import STATUS_SUCCESS
from gptase.memory.manager import MemoryManager
from gptase.models.model import Model
from gptase.sop.dispatcher import TaskDispatcher
from gptase.sop.exceptions import CheckpointCorruptedError
from gptase.sop.exceptions import CheckpointNotFoundError
from gptase.sop.exceptions import CheckpointVersionMismatchError
from gptase.sop.exceptions import SOPExecutionError
from gptase.sop.failure_handler import FailureHandler
from gptase.sop.loader import SOPLoader
from gptase.sop.loader import SOPRegistry
from gptase.sop.types import ExecutionContext
from gptase.sop.types import FailureDecision
from gptase.sop.types import ParallelStep
from gptase.sop.types import SOPCheckpoint
from gptase.sop.types import SOPDefinition
from gptase.sop.types import SOPStep
from gptase.sop.types import StepResult
from gptase.sop.types import StepStatus
from gptase.sop.types import TaskResult

logger = logging.getLogger(__name__)


class SOPOrchestratorAgent(Agent):
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
            system_prompt="",
            agent_id="sop_orchestrator",
            capabilities=[
                "sop_execution",
                "workflow_orchestration",
                "agent_dispatch",
                "failure_recovery",
            ],
        )
        self.memory = memory_manager
        self.model_manager = model_manager
        self.state = AgentState(
            agent_id="sop_orchestrator",
            capabilities=self.capabilities,
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
        from gptase.agents.loader import MarkdownAgentFactory

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
        session_id: Optional[str] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
        pre_completed_steps: Optional[Dict[str, StepResult]] = None,
        auto_checkpoint: bool = True,
    ) -> Dict[str, Any]:
        """Execute an SOP workflow with optional checkpoint recovery.

        Args:
            plan_id: SOP definition to execute.
            input_data: Initial input (document_path, text, etc.).
            document_path: Optional document path for resolving relative paths.
            session_id: Optional session ID to resume from.
            checkpoint: Optional checkpoint data to restore from.
            pre_completed_steps: Optional pre-populated step results.
            auto_checkpoint: Whether to automatically save checkpoints.

        Returns:
            Aggregated results from all steps.
        """
        # Load the SOP definition
        sop = self.registry.get_sop(plan_id)

        # Calculate SOP hash for compatibility checking
        sop_hash = self._calculate_sop_hash(sop)

        # Initialize or restore context
        if checkpoint:
            context = ExecutionContext.from_checkpoint(checkpoint, validate_sop=sop)
            logger.info("Restored context from checkpoint: %s", context.session_id)
        elif session_id:
            stored_checkpoint = await self._load_checkpoint_from_db(session_id)
            if stored_checkpoint:
                context = ExecutionContext.from_checkpoint(stored_checkpoint,
                                                           validate_sop=sop)
                logger.info("Resumed session: %s", session_id)
            else:
                raise CheckpointNotFoundError(session_id)
        else:
            # Fresh execution
            session_id = session_id or self._generate_session_id()
            context = ExecutionContext(
                plan_id=plan_id,
                input_data=input_data,
                document_path=document_path,
                session_id=session_id,
            )

        # Apply pre-completed steps if provided
        if pre_completed_steps:
            for step_id, step_result in pre_completed_steps.items():
                context.update_step_result(step_id, step_result)
                logger.info("Pre-populated step result: %s", step_id)

        # Store input_data in variables for easy access
        context.set_variable("input_data", input_data)
        if "text" in input_data:
            context.set_variable("input_text", input_data["text"])

        logger.info(
            "Starting SOP execution: %s (%s)",
            sop.name or plan_id,
            plan_id,
        )

        # Start session tracking
        await self._start_session(sop, context)

        # Save initial checkpoint
        if auto_checkpoint:
            await self._save_checkpoint_to_db(context, sop, "in_progress")

        try:
            # Execute workflow with skip logic
            for workflow_item in sop.workflow:
                if isinstance(workflow_item, ParallelStep):
                    await self._execute_parallel_with_resume(workflow_item, context,
                                                             sop)
                else:
                    await self._execute_step_with_resume(workflow_item, context, sop)

                # Save checkpoint after each workflow item
                if auto_checkpoint:
                    await self._save_checkpoint_to_db(context, sop, "in_progress")

            # Mark as success
            result = context.to_result()
            result["status"] = STATUS_SUCCESS

            # Save final checkpoint
            if auto_checkpoint:
                await self._save_checkpoint_to_db(context, sop, "completed")

            logger.info("SOP execution completed successfully: %s", plan_id)

            return result

        except SOPExecutionError as e:
            # Save checkpoint on failure for potential resume
            if auto_checkpoint:
                await self._save_checkpoint_to_db(context, sop, "failed")
            # Add session_id to error details for recovery
            e.details["session_id"] = context.session_id
            raise
        except Exception as e:
            logger.error("SOP execution failed with unexpected error: %s", e)
            # Save checkpoint on failure
            if auto_checkpoint:
                await self._save_checkpoint_to_db(context, sop, "failed")
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

    async def _execute_step_with_resume(
        self,
        step: SOPStep,
        context: ExecutionContext,
        sop: SOPDefinition,
    ) -> StepResult:
        """Execute step with checkpoint-based skip logic.

        Args:
            step: The step to execute.
            context: Execution context.
            sop: Parent SOP definition.

        Returns:
            StepResult from the execution.
        """
        # Check if already completed
        existing_result = context.get_step_result(step.step_id)
        if existing_result and existing_result.status == StepStatus.SUCCESS:
            logger.info(
                "Skipping step '%s' - already completed (checkpoint)",
                step.step_id,
            )
            return existing_result

        # Check for failed step (may want to retry)
        if existing_result and existing_result.status == StepStatus.FAILED:
            logger.info(
                "Retrying failed step '%s' from checkpoint",
                step.step_id,
            )
            # Clear the failed result to retry
            context.step_results.pop(step.step_id, None)

        return await self._execute_step(step, context, sop)

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

    async def _execute_parallel_with_resume(
        self,
        parallel_step: ParallelStep,
        context: ExecutionContext,
        sop: SOPDefinition,
    ) -> None:
        """Execute parallel steps with partial completion handling.

        Args:
            parallel_step: Group of parallel steps.
            context: Execution context.
            sop: Parent SOP definition.
        """
        steps = parallel_step.parallel

        # Categorize steps by status
        completed_steps = []
        pending_steps = []
        failed_steps = []

        for step in steps:
            existing = context.get_step_result(step.step_id)
            if existing:
                if existing.status == StepStatus.SUCCESS:
                    completed_steps.append(step)
                elif existing.status == StepStatus.FAILED:
                    failed_steps.append(step)
                else:
                    pending_steps.append(step)
            else:
                pending_steps.append(step)

        logger.info(
            "Parallel step status: %d completed, %d pending, %d failed",
            len(completed_steps),
            len(pending_steps),
            len(failed_steps),
        )

        # Only execute pending and failed steps (for retry)
        steps_to_execute = pending_steps + failed_steps

        if not steps_to_execute:
            logger.info("All parallel steps already completed")
            return

        # Clear failed results for retry
        for step in failed_steps:
            context.step_results.pop(step.step_id, None)

        # Execute remaining steps in parallel
        results = await self.dispatcher.dispatch_parallel(
            steps=steps_to_execute,
            context=context,
            max_concurrent=sop.max_parallel,
        )

        # Process results
        for step, result in zip(steps_to_execute, results):
            step_result = StepResult(
                step_id=step.step_id,
                status=StepStatus.SUCCESS if result.is_success() else StepStatus.FAILED,
                result=result,
            )

            if result.is_success():
                context.update_step_result(step.step_id, step_result)
            else:
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

    # =========================================================================
    # Checkpoint Management
    # =========================================================================

    async def _save_checkpoint_to_db(
        self,
        context: ExecutionContext,
        sop: SOPDefinition,
        status: str = "in_progress",
    ) -> str:
        """Save current context as checkpoint to database.

        Args:
            context: Execution context to save.
            sop: SOP definition for progress calculation.
            status: Checkpoint status.

        Returns:
            Checkpoint ID.
        """
        # Calculate progress
        all_steps = sop.get_all_steps()
        total_steps = len(all_steps)
        completed_steps = sum(
            1 for s in all_steps if context.get_step_result(s.step_id)
            and context.get_step_result(s.step_id).status == StepStatus.SUCCESS)

        checkpoint = SOPCheckpoint(
            session_id=context.session_id,
            plan_id=context.plan_id,
            input_data=context.input_data,
            document_path=context.document_path,
            step_results=context.step_results,
            variables=context.variables,
            current_step=context.current_step,
            status=status,
            total_steps=total_steps,
            completed_steps=completed_steps,
            sop_hash=self._calculate_sop_hash(sop),
        )

        checkpoint_data = checkpoint.model_dump()
        # Serialize datetime
        checkpoint_data["created_at"] = checkpoint.created_at.isoformat()

        now = datetime.now().isoformat()

        # Use the storage database directly
        db = self.memory.storage.db

        await db.execute(
            """INSERT OR REPLACE INTO sop_checkpoints
               (checkpoint_id, session_id, plan_id, created_at, updated_at,
                checkpoint_data, status, total_steps, completed_steps)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                checkpoint.checkpoint_id,
                checkpoint.session_id,
                checkpoint.plan_id,
                checkpoint.created_at.isoformat(),
                now,
                json.dumps(checkpoint_data),
                checkpoint.status,
                checkpoint.total_steps,
                checkpoint.completed_steps,
            ),
        )
        await db.commit()

        logger.debug(
            "Saved checkpoint: %s (progress: %d/%d)",
            checkpoint.session_id,
            completed_steps,
            total_steps,
        )
        return checkpoint.checkpoint_id

    async def _load_checkpoint_from_db(
        self,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load checkpoint from database.

        Args:
            session_id: Session ID to load.

        Returns:
            Checkpoint data dictionary or None if not found.
        """
        db = self.memory.storage.db

        cursor = await db.execute(
            "SELECT checkpoint_data FROM sop_checkpoints WHERE session_id = ?",
            (session_id, ),
        )
        row = await cursor.fetchone()

        if row:
            return json.loads(row[0])
        return None

    def _calculate_sop_hash(self, sop: SOPDefinition) -> str:
        """Calculate hash of SOP workflow for compatibility check.

        Args:
            sop: SOP definition.

        Returns:
            Hash string.
        """
        # Create deterministic string from workflow
        workflow_sig = []
        for item in sop.workflow:
            if isinstance(item, ParallelStep):
                step_ids = sorted([s.step_id for s in item.parallel])
                workflow_sig.append(f"parallel:{','.join(step_ids)}")
            else:
                workflow_sig.append(f"step:{item.step_id}:{item.agent}")

        workflow_str = "|".join(workflow_sig)
        return hashlib.md5(workflow_str.encode()).hexdigest()[:16]

    async def save_checkpoint(self, session_id: str) -> Dict[str, Any]:
        """Save checkpoint for a session.

        Args:
            session_id: Session ID to save checkpoint for.

        Returns:
            Checkpoint data.

        Raises:
            CheckpointNotFoundError: If session not found.
        """
        checkpoint_data = await self._load_checkpoint_from_db(session_id)
        if not checkpoint_data:
            raise CheckpointNotFoundError(session_id)
        return checkpoint_data

    async def load_checkpoint(self, session_id: str) -> Dict[str, Any]:
        """Load checkpoint by session_id from storage.

        Args:
            session_id: Session ID to load.

        Returns:
            Checkpoint data.

        Raises:
            CheckpointNotFoundError: If checkpoint not found.
            CheckpointCorruptedError: If checkpoint data is invalid.
            CheckpointVersionMismatchError: If checkpoint version is incompatible.
        """
        try:
            checkpoint_data = await self._load_checkpoint_from_db(session_id)

            if not checkpoint_data:
                raise CheckpointNotFoundError(session_id)

            # Validate version
            version = checkpoint_data.get("checkpoint_version", "1.0")
            if version != "1.0":
                raise CheckpointVersionMismatchError(session_id, version, "1.0")

            # Validate required fields
            required_fields = ["plan_id", "session_id", "step_results"]
            for field in required_fields:
                if field not in checkpoint_data:
                    raise CheckpointCorruptedError(session_id,
                                                   f"Missing required field: {field}")

            return checkpoint_data

        except json.JSONDecodeError as e:
            raise CheckpointCorruptedError(session_id, f"Invalid JSON: {e}")

    async def resume_sop(
        self,
        session_id: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resume SOP execution from saved checkpoint.

        Args:
            session_id: Session ID to resume.
            input_data: Optional override for input data.

        Returns:
            Execution result.
        """
        checkpoint = await self.load_checkpoint(session_id)

        # Override input_data if provided
        if input_data:
            checkpoint["input_data"] = input_data

        return await self.execute_sop(
            plan_id=checkpoint["plan_id"],
            input_data=checkpoint.get("input_data", {}),
            document_path=checkpoint.get("document_path"),
            session_id=session_id,
            checkpoint=checkpoint,
            auto_checkpoint=True,
        )

    async def list_sessions(
        self,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List all SOP execution sessions.

        Args:
            plan_id: Optional filter by plan_id.
            status: Optional filter by status.
            limit: Maximum number of sessions to return.

        Returns:
            List of session metadata dictionaries.
        """
        db = self.memory.storage.db

        query = """SELECT session_id, plan_id, created_at, updated_at, status,
                          total_steps, completed_steps
                   FROM sop_checkpoints"""
        conditions = []
        params = []

        if plan_id:
            conditions.append("plan_id = ?")
            params.append(plan_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        sessions = []
        for row in rows:
            sessions.append({
                "session_id":
                row[0],
                "plan_id":
                row[1],
                "created_at":
                row[2],
                "updated_at":
                row[3],
                "status":
                row[4],
                "total_steps":
                row[5],
                "completed_steps":
                row[6],
                "progress": (round(row[6] / row[5] * 100, 1) if row[5] > 0 else 0),
            })

        return sessions

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a session including progress.

        Args:
            session_id: Session ID to check.

        Returns:
            Session status dictionary or None if not found.
        """
        db = self.memory.storage.db

        cursor = await db.execute(
            """SELECT session_id, plan_id, created_at, updated_at, status,
                      total_steps, completed_steps, checkpoint_data
               FROM sop_checkpoints WHERE session_id = ?""",
            (session_id, ),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        checkpoint_data = json.loads(row[7]) if row[7] else {}

        return {
            "session_id": row[0],
            "plan_id": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "status": row[4],
            "total_steps": row[5],
            "completed_steps": row[6],
            "progress": round(row[6] / row[5] * 100, 1) if row[5] > 0 else 0,
            "current_step": checkpoint_data.get("current_step"),
            "step_results": {
                step_id: {
                    "status": sr.get("status")
                }
                for step_id, sr in checkpoint_data.get("step_results", {}).items()
            },
        }

    async def close(self) -> None:
        """Close all resources owned by this orchestrator.

        Should be called before program exit to properly close database
        connections and prevent aiosqlite 'Event loop is closed' errors.
        """
        # Close memory manager storage
        if self.memory:
            await self.memory.close()

        # Close model manager tracking storage if present
        if self.model_manager and hasattr(self.model_manager, "tracking_storage"):
            if self.model_manager.tracking_storage:
                await self.model_manager.tracking_storage.close()

        logger.debug("SOPOrchestratorAgent resources closed")
