"""Tests for FailureHandler in gptase/agents/plan_failure_handler.py.

Covers decide(), _llm_decide(), _heuristic_decide(), and should_skip_on_failure()
without making any real API calls.
"""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import FailureDecision
from gptase.agents.plan_failure_handler import DEFAULT_MAX_RETRIES
from gptase.agents.plan_failure_handler import FailureHandler
from gptase.agents.types import Task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(step_id="1", agent="test-agent", optional=False, retry_count=0):
    return Task(task_id=step_id,
                description="Test task",
                agent_id=agent,
                optional=optional,
                retry_count=retry_count)


def _make_context(plan_id="test-plan"):
    return ExecutionContext(plan_id=plan_id)


# ---------------------------------------------------------------------------
# TestFailureHandlerInit
# ---------------------------------------------------------------------------


class TestFailureHandlerInit:
    """Tests for FailureHandler construction."""

    def test_defaults(self):
        handler = FailureHandler()

        assert handler.model is None
        assert handler.model_config is None
        assert handler.max_retries == DEFAULT_MAX_RETRIES

    def test_custom_max_retries(self):
        handler = FailureHandler(max_retries=5)

        assert handler.max_retries == 5

    def test_with_model_and_config(self):
        mock_model = MagicMock()
        mock_config = MagicMock()

        handler = FailureHandler(model=mock_model, model_config=mock_config)

        assert handler.model is mock_model
        assert handler.model_config is mock_config


# ---------------------------------------------------------------------------
# TestShouldSkipOnFailure
# ---------------------------------------------------------------------------


class TestShouldSkipOnFailure:
    """Tests for should_skip_on_failure."""

    def test_optional_step_returns_true(self):
        handler = FailureHandler()
        step = _make_step(optional=True)
        assert handler.should_skip_on_failure(step) is True

    def test_required_step_returns_false(self):
        handler = FailureHandler()
        step = _make_step(optional=False)
        assert handler.should_skip_on_failure(step) is False


# ---------------------------------------------------------------------------
# TestHeuristicDecide
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestDecideAsync
# ---------------------------------------------------------------------------


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

    async def test_no_model_uses_heuristic_retry(self):
        handler = FailureHandler(model=None, max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler.decide(step, "Connection timeout", context, attempt=0)

        assert decision == FailureDecision.RETRY

    async def test_no_model_uses_heuristic_abort(self):
        handler = FailureHandler(model=None, max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler.decide(step, "Resource not found", context, attempt=0)

        assert decision == FailureDecision.ABORT

    async def test_optional_step_skipped_even_with_model(self):
        # Even when a model is present, optional steps short-circuit before LLM call
        mock_model = MagicMock()
        mock_model.generate = AsyncMock()
        handler = FailureHandler(model=mock_model, max_retries=3)
        step = _make_step(optional=True)
        context = _make_context()

        decision = await handler.decide(step, "error", context, attempt=0)

        assert decision == FailureDecision.SKIP
        mock_model.generate.assert_not_awaited()

    async def test_max_retries_abort_before_llm_call(self):
        # LLM should not be consulted when max retries is already exceeded
        mock_model = MagicMock()
        mock_model.generate = AsyncMock()
        handler = FailureHandler(model=mock_model, max_retries=2)
        step = _make_step()
        context = _make_context()

        decision = await handler.decide(step, "error", context, attempt=2)

        assert decision == FailureDecision.ABORT
        mock_model.generate.assert_not_awaited()

    async def test_with_model_calls_generate(self):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "ABORT"
        mock_model.generate = AsyncMock(return_value=mock_response)
        handler = FailureHandler(model=mock_model, max_retries=3)
        step = _make_step()
        context = _make_context()

        await handler.decide(step, "some error", context, attempt=0)

        mock_model.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestLLMDecide
# ---------------------------------------------------------------------------


class TestLLMDecide:
    """Tests for the async _llm_decide() method."""

    def _make_handler(self, response_text="ABORT"):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = response_text
        mock_model.generate = AsyncMock(return_value=mock_response)
        handler = FailureHandler(model=mock_model, max_retries=3)
        return handler, mock_model

    async def test_abort_response_returns_abort(self):
        handler, _ = self._make_handler("ABORT")
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step, "error", context, attempt=0)

        assert decision == FailureDecision.ABORT

    async def test_skip_response_returns_skip(self):
        handler, _ = self._make_handler("SKIP")
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step, "error", context, attempt=0)

        assert decision == FailureDecision.SKIP

    async def test_retry_response_returns_retry(self):
        handler, _ = self._make_handler("RETRY")
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step, "error", context, attempt=0)

        assert decision == FailureDecision.RETRY

    async def test_unclear_response_defaults_to_abort(self):
        handler, _ = self._make_handler("I am not sure what to do")
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step, "error", context, attempt=0)

        assert decision == FailureDecision.ABORT

    async def test_empty_response_defaults_to_abort(self):
        handler, _ = self._make_handler("")
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step, "error", context, attempt=0)

        assert decision == FailureDecision.ABORT

    async def test_exception_falls_back_to_heuristic_abort(self):
        mock_model = MagicMock()
        mock_model.generate = AsyncMock(side_effect=RuntimeError("API unavailable"))
        handler = FailureHandler(model=mock_model, max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step,
                                             "Resource not found",
                                             context,
                                             attempt=0)

        assert decision == FailureDecision.ABORT

    async def test_exception_falls_back_to_heuristic_retry(self):
        mock_model = MagicMock()
        mock_model.generate = AsyncMock(side_effect=ConnectionError("network error"))
        handler = FailureHandler(model=mock_model, max_retries=3)
        step = _make_step()
        context = _make_context()

        decision = await handler._llm_decide(step,
                                             "Connection timeout",
                                             context,
                                             attempt=0)

        assert decision == FailureDecision.RETRY

    async def test_prompt_includes_plan_and_step_identifiers(self):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "ABORT"
        captured = []

        async def capture(messages, config=None):
            captured.extend(messages)
            return mock_response

        mock_model.generate = capture
        handler = FailureHandler(model=mock_model, max_retries=3)
        step = _make_step(step_id="step-42", agent="my-agent")
        context = ExecutionContext(plan_id="my-plan")

        await handler._llm_decide(step, "error happened", context, attempt=1)

        prompt = captured[0]["content"]
        assert "my-plan" in prompt
        assert "step-42" in prompt
        assert "my-agent" in prompt

    async def test_long_error_is_truncated_to_500_chars(self):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "ABORT"
        captured = []

        async def capture(messages, config=None):
            captured.extend(messages)
            return mock_response

        mock_model.generate = capture
        handler = FailureHandler(model=mock_model, max_retries=3)

        await handler._llm_decide(_make_step(), "x" * 1000, _make_context(), attempt=0)

        prompt = captured[0]["content"]
        assert "x" * 500 in prompt
        assert "x" * 501 not in prompt

    async def test_attempt_number_shown_in_prompt(self):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "ABORT"
        captured = []

        async def capture(messages, config=None):
            captured.extend(messages)
            return mock_response

        mock_model.generate = capture
        handler = FailureHandler(model=mock_model, max_retries=3)

        await handler._llm_decide(_make_step(), "error", _make_context(), attempt=1)

        # attempt=1 is displayed as "2/3" (attempt+1 / max_retries)
        assert "2/3" in captured[0]["content"]

    async def test_model_config_passed_to_generate(self):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "ABORT"
        mock_model.generate = AsyncMock(return_value=mock_response)
        mock_config = MagicMock()
        handler = FailureHandler(model=mock_model,
                                 model_config=mock_config,
                                 max_retries=3)

        await handler._llm_decide(_make_step(), "error", _make_context(), attempt=0)

        call_args = mock_model.generate.await_args
        assert call_args[1].get("config") is mock_config
