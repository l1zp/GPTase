"""Tests for FailureHandler in gptase/agents/plan_failure_handler.py.

Covers decide() and _heuristic_decide() without making any real API calls.
"""

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import FailureDecision
from gptase.agents.plan_failure_handler import FailureHandler
from gptase.agents.types import Task


def _make_step(step_id="1", agent="test-agent", optional=False, retry_count=0):
    return Task(task_id=step_id,
                description="Test task",
                agent_id=agent,
                optional=optional,
                retry_count=retry_count)


def _make_context(plan_id="test-plan"):
    return ExecutionContext(plan_id=plan_id)


class TestHeuristicDecide:
    """Tests for _heuristic_decide edge cases."""

    def test_no_pattern_under_retry_limit_returns_retry(self):
        handler = FailureHandler(max_retries=3)
        step = _make_step()

        decision = handler._heuristic_decide(step, "some unknown error", attempt=1)

        assert decision == FailureDecision.RETRY

    def test_no_pattern_at_retry_limit_returns_abort(self):
        handler = FailureHandler(max_retries=3)
        step = _make_step()

        decision = handler._heuristic_decide(step, "some unknown error", attempt=3)

        assert decision == FailureDecision.ABORT

    def test_retry_pattern_case_insensitive(self):
        handler = FailureHandler()
        step = _make_step()
        decision = handler._heuristic_decide(step,
                                             "Connection TIMEOUT occurred",
                                             attempt=0)
        assert decision == FailureDecision.RETRY

    def test_abort_pattern_case_insensitive(self):
        handler = FailureHandler()
        step = _make_step()
        decision = handler._heuristic_decide(step, "File Does Not Exist", attempt=0)
        assert decision == FailureDecision.ABORT

    def test_timed_out_pattern_returns_retry(self):
        handler = FailureHandler()
        step = _make_step()
        decision = handler._heuristic_decide(step, "Request timed out after 30s", 0)
        assert decision == FailureDecision.RETRY

    def test_out_of_memory_pattern_returns_abort(self):
        handler = FailureHandler()
        step = _make_step()
        decision = handler._heuristic_decide(step, "out of memory", 0)
        assert decision == FailureDecision.ABORT

    def test_service_unavailable_pattern_returns_retry(self):
        handler = FailureHandler()
        step = _make_step()
        decision = handler._heuristic_decide(step, "Service unavailable (503)", 0)
        assert decision == FailureDecision.RETRY

    def test_invalid_pattern_returns_abort(self):
        handler = FailureHandler()
        step = _make_step()
        decision = handler._heuristic_decide(step, "invalid request format", 0)
        assert decision == FailureDecision.ABORT

    def test_permission_denied_pattern_returns_abort(self):
        handler = FailureHandler()
        step = _make_step()

        decision = handler._heuristic_decide(step, "Permission denied for /tmp/x", 0)

        assert decision == FailureDecision.ABORT

    def test_malformed_json_pattern_returns_abort(self):
        handler = FailureHandler()
        step = _make_step()

        decision = handler._heuristic_decide(step, "Malformed JSON output", 0)

        assert decision == FailureDecision.ABORT


class TestDecideAsync:
    """Tests for the async decide() method."""

    async def test_optional_step_returns_skip(self):
        handler = FailureHandler()
        step = _make_step(optional=True)
        context = _make_context()

        decision = await handler.decide(step, "some error", context, attempt=0)

        assert decision == FailureDecision.SKIP

    async def test_max_retries_exceeded_returns_abort(self):
        handler = FailureHandler(max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler.decide(step, "some error", context, attempt=3)

        assert decision == FailureDecision.ABORT

    async def test_heuristic_retry_on_transient_error(self):
        handler = FailureHandler(max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler.decide(step, "Connection timeout", context, attempt=0)

        assert decision == FailureDecision.RETRY

    async def test_heuristic_abort_on_fatal_error(self):
        handler = FailureHandler(max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler.decide(step, "Resource not found", context, attempt=0)

        assert decision == FailureDecision.ABORT
