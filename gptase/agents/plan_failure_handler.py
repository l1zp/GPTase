"""Heuristic failure recovery for plan execution.

Provides a small decision engine that classifies an error message and
returns one of ABORT / SKIP / RETRY for the planner to act on.
"""

import logging

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import FailureDecision
from gptase.agents.types import Task

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3


class FailureHandler:
    """Heuristic failure recovery decision engine.

    Classifies a failure based on the step's `optional` flag, the retry
    attempt counter, and pattern matches against the error message, then
    returns ABORT, SKIP, or RETRY.
    """

    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES):
        self.max_retries = max_retries

    async def decide(
        self,
        step: Task,
        error: str,
        context: ExecutionContext,
        attempt: int = 0,
    ) -> FailureDecision:
        """Decide how to handle a step failure."""
        if step.optional:
            logger.info("Step '%s' is marked optional, auto-skipping", step.task_id)
            return FailureDecision.SKIP

        if attempt >= self.max_retries:
            logger.warning(
                "Max retries (%d) exceeded for step '%s', aborting",
                self.max_retries,
                step.task_id,
            )
            return FailureDecision.ABORT

        return self._heuristic_decide(step, error, attempt)

    def _heuristic_decide(self, step: Task, error: str,
                          attempt: int) -> FailureDecision:
        """Pattern-match the error message into a recovery decision."""
        category = self._classify_error(error.lower())

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
