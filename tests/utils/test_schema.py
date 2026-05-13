"""Unit tests for gptase.utils.schema — JSON Schema validation helpers.

Covers the three public functions used at the DelegateTask boundary:
validate_agent_inputs, validate_agent_output, check_schema. Each test
is a pure-function call against an in-memory schema dict — no Agent or
DelegateTask wiring (that lives in tests/tools/test_handlers.py).
"""
import json

import pytest

from gptase.utils.schema import check_schema
from gptase.utils.schema import validate_agent_inputs
from gptase.utils.schema import validate_agent_output

_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "x": {
            "type": "integer"
        },
        "y": {
            "type": "string"
        },
    },
    "required": ["x"],
}


class TestValidateAgentInputs:
    """validate_agent_inputs: dict-vs-schema validation with skip semantics."""

    def test_validate_agent_inputs_passes_when_no_schema(self):
        # None schema is the backward-compat case: any inputs pass through.
        assert validate_agent_inputs({"anything": True}, None) is None
        assert validate_agent_inputs(None, None) is None

    def test_validate_agent_inputs_reports_missing_required_key(self):
        # Error string must mention the missing key so the Coordinator
        # (or a human reading the failed delegation log) can fix it.
        err = validate_agent_inputs({"y": "ok"}, _OBJECT_SCHEMA)

        assert err is not None
        assert "'x' is a required property" in err

    def test_validate_agent_inputs_treats_none_data_as_empty(self):
        # task_inputs=None is a common path (LLM omits the field); it
        # should fail the same way as task_inputs={} when schema requires keys.
        err = validate_agent_inputs(None, _OBJECT_SCHEMA)

        assert err is not None
        assert "'x'" in err


class TestValidateAgentOutput:
    """validate_agent_output: JSON-parse then schema-check."""

    def test_validate_agent_output_requires_parseable_json(self):
        # Declaring output_schema is a contract that content is JSON.
        # Plain text fails fast with a clear JSON parse error.
        err = validate_agent_output("hello world (not json)", _OBJECT_SCHEMA)

        assert err is not None
        assert "not valid JSON" in err

    def test_validate_agent_output_passes_valid_json(self):
        err = validate_agent_output(json.dumps({"x": 42}), _OBJECT_SCHEMA)

        assert err is None

    def test_validate_agent_output_skips_when_no_schema(self):
        # Without a declared schema, content can be anything (back-compat).
        assert validate_agent_output("free-form text", None) is None


class TestCheckSchema:
    """check_schema: load-time schema self-validation."""

    def test_check_schema_accepts_well_formed_schema(self):
        # Smoke: a normal object schema is well-formed.
        check_schema(_OBJECT_SCHEMA, "test context")

    def test_check_schema_raises_on_malformed_schema(self):
        # `type` must be a string or list, not an integer. jsonschema
        # surfaces this through Draft202012Validator.check_schema; the
        # wrapper turns it into a ValueError carrying the agent label.
        bad = {"type": 42}

        with pytest.raises(ValueError, match="agent 'broken' inputs_schema"):
            check_schema(bad, "agent 'broken' inputs_schema")
