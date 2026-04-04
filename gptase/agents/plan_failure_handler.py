"""AI-driven failure recovery for SOP execution.

This module provides the FailureHandler class that uses LLM to
decide recovery actions when workflow steps fail.
"""

import logging
from typing import Optional

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import FailureDecision
from gptase.agents.types import Task
from gptase.models.model import Model
from gptase.models.types import ModelConfig

logger = logging.getLogger(__name__)

# Default maximum retries before automatic abort
DEFAULT_MAX_RETRIES = 3


class FailureHandler:
    """AI-driven failure recovery decision engine.

    Uses an LLM to analyze failure contexts and decide the appropriate
    recovery action: ABORT, SKIP, or RETRY.

    The decision is based on:
    - The nature of the error
    - The importance of the failed step
    - Current execution state
    - Previous retry attempts

    Attributes:
        model: Optional Model instance for LLM calls.
        model_config: Configuration for model calls.
        max_retries: Maximum retry attempts before abort.
    """

    # Prompt template for failure decision
    DECISION_PROMPT = """A step in an SOP workflow failed. Analyze the failure and decide the recovery action.

## SOP: {plan_id}
## Failed Task: {task_id} ({agent_id}.{action})
## Task Description: {description}
## Error: {error}
## Attempt: {attempt}/{max_retries}
## Completed Steps: {completed_steps}

## Options:
- ABORT: Critical failure, stop entire workflow
- SKIP: Non-critical step, continue without it
- RETRY: Transient error, retry the step

## Decision Rules:
1. ABORT if: Input data is missing/corrupt, critical dependency failed, error indicates fundamental issue
2. SKIP if: Step is optional/non-critical, missing data is acceptable, error is recoverable
3. RETRY if: Network/API timeout, rate limit, temporary resource unavailability

Respond with ONLY ONE WORD: ABORT, SKIP, or RETRY"""

    def __init__(
        self,
        model: Optional[Model] = None,
        model_config: Optional[ModelConfig] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize the failure handler.

        Args:
            model: Optional Model instance for LLM decisions.
            model_config: Configuration for model calls.
            max_retries: Maximum retry attempts before abort.
        """
        self.model = model
        self.model_config = model_config
        self.max_retries = max_retries

    async def decide(
        self,
        step: Task,
        error: str,
        context: ExecutionContext,
        attempt: int = 0,
    ) -> FailureDecision:
        """Decide how to handle a step failure.

        Args:
            step: The step that failed.
            error: Error message from the failure.
            context: Current execution context.
            attempt: Current retry attempt number.

        Returns:
            The failure decision (ABORT, SKIP, or RETRY).
        """
        # If step is marked optional, skip by default
        if step.optional:
            logger.info("Step '%s' is marked optional, auto-skipping", step.task_id)
            return FailureDecision.SKIP

        # If max retries exceeded, abort
        if attempt >= self.max_retries:
            logger.warning(
                "Max retries (%d) exceeded for step '%s', aborting",
                self.max_retries,
                step.task_id,
            )
            return FailureDecision.ABORT

        # If retry_count is configured for the step, check it
        if step.retry_count > 0 and attempt >= step.retry_count:
            logger.warning(
                "Step retry count (%d) exceeded for step '%s'",
                step.retry_count,
                step.task_id,
            )
            # Don't auto-abort, let LLM decide
            pass

        # Use LLM for decision if available
        if self.model:
            return await self._llm_decide(step, error, context, attempt)

        # Default heuristic-based decision
        return self._heuristic_decide(step, error, attempt)

    async def _llm_decide(
        self,
        step: Task,
        error: str,
        context: ExecutionContext,
        attempt: int,
    ) -> FailureDecision:
        """Use LLM to make the failure decision.

        Args:
            step: The step that failed.
            error: Error message.
            context: Execution context.
            attempt: Retry attempt number.

        Returns:
            The LLM's failure decision.
        """
        try:
            # Build the prompt
            completed_steps = list(context.task_results.keys())

            prompt = self.DECISION_PROMPT.format(
                plan_id=context.plan_id,
                task_id=step.task_id,
                agent_id=step.agent_id,
                action=step.action,
                description=step.description or "No description",
                error=error[:500],  # Truncate long errors
                attempt=attempt + 1,
                max_retries=self.max_retries,
                completed_steps=completed_steps,
            )

            # Call the model
            messages = [{"role": "user", "content": prompt}]
            response = await self.model.generate(messages, config=self.model_config)

            # Parse the decision
            decision_text = response.content.strip().upper()

            # Extract the decision word
            for decision in FailureDecision:
                if decision.value.upper() in decision_text:
                    logger.info(
                        "LLM decided %s for step '%s' failure",
                        decision.value,
                        step.task_id,
                    )
                    return decision

            # Default to ABORT if unclear response
            logger.warning(
                "Unclear LLM response '%s', defaulting to ABORT",
                decision_text[:50],
            )
            return FailureDecision.ABORT

        except Exception as e:
            logger.error("LLM decision failed: %s, falling back to heuristics", e)
            return self._heuristic_decide(step, error, attempt)

    def _heuristic_decide(self, step: Task, error: str,
                          attempt: int) -> FailureDecision:
        """Make a heuristic-based failure decision.

        Uses simple rules based on error patterns.

        Args:
            step: The step that failed.
            error: Error message.
            attempt: Retry attempt number.

        Returns:
            The failure decision.
        """
        error_lower = error.lower()

        category = self._classify_error(error_lower)

        if category == "transient":
            logger.info("Error classified as transient, will retry")
            return FailureDecision.RETRY

        if category in {
                "invalid_input",
                "permission",
                "invalid_output",
                "fatal_config",
        }:
            logger.info("Error classified as %s, will abort", category)
            return FailureDecision.ABORT

        # Default: if under retry limit, retry; otherwise abort
        if attempt < self.max_retries:
            logger.info(
                "Error classified as unknown, will retry (attempt %d/%d)",
                attempt + 1,
                self.max_retries,
            )
            return FailureDecision.RETRY

        return FailureDecision.ABORT

    def _classify_error(self, error_lower: str) -> str:
        """Classify errors into coarse recovery buckets."""
        # Patterns suggesting retry
        retry_patterns = [
            "timeout",
            "timed out",
            "rate limit",
            "too many requests",
            "service unavailable",
            "temporary",
            "try again",
            "connection reset",
            "network error",
        ]

        for pattern in retry_patterns:
            if pattern in error_lower:
                return "transient"

        permission_patterns = [
            "unauthorized",
            "forbidden",
            "permission denied",
            "access denied",
            "not allowed",
        ]
        for pattern in permission_patterns:
            if pattern in error_lower:
                return "permission"

        invalid_input_patterns = [
            "not found",
            "does not exist",
            "missing required",
            "invalid input",
            "invalid argument",
            "invalid path",
            "file not found",
            "unknown agent",
        ]
        for pattern in invalid_input_patterns:
            if pattern in error_lower:
                return "invalid_input"

        invalid_output_patterns = [
            "invalid output",
            "schema",
            "parse",
            "malformed",
            "json",
        ]
        for pattern in invalid_output_patterns:
            if pattern in error_lower:
                return "invalid_output"

        # Patterns suggesting abort
        abort_patterns = [
            "invalid",
            "not supported",
            "out of memory",
            "configuration",
            "misconfigured",
        ]

        for pattern in abort_patterns:
            if pattern in error_lower:
                return "fatal_config"

        return "unknown"

    def should_skip_on_failure(self, step: Task) -> bool:
        """Check if a step should be skipped on failure.

        Args:
            step: The step to check.

        Returns:
            True if the step should be skipped when it fails.
        """
        return step.optional
