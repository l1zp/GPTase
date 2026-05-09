"""Unit tests for gptase.evals.assertions.

Three concerns tested in isolation:

* ``extract_field`` — JSONPath-lite DSL (dotted, wildcard, filter,
  index, keys-containing-dots).
* ``_check_condition`` — every implemented condition branch (length_gte,
  gte, approx_eq, contains, contains_all, contains_any) plus the
  "unknown condition" fallback.
* ``evaluate_key_facts`` / ``EvalResult`` — orchestration and score math.

Note: the project's actual ``golden.yaml`` files use condition names
that ``_check_condition`` does NOT implement (``min_length``,
``min_value``, ``equals``, ``is_null``, ``not_equals``,
``equals_case_insensitive``). Those land in the unknown-condition
branch and are not this file's concern — see project memory note
``project_evals_condition_drift``.
"""
from gptase.evals.assertions import _check_condition
from gptase.evals.assertions import EvalResult
from gptase.evals.assertions import evaluate_key_facts
from gptase.evals.assertions import extract_field
from gptase.evals.assertions import validate_schema


class TestEvalResultScore:
    """Score property handles the empty case + normal arithmetic."""

    def test_score_returns_one_when_no_facts(self):
        # Empty assertion set is a vacuous success — never report 0/0
        # as a fail because nothing was actually checked.
        r = EvalResult(agent_name="x",
                       schema_valid=True,
                       schema_error="",
                       total_facts=0,
                       passed_facts=0)
        assert r.score == 1.0

    def test_score_returns_pass_ratio(self):
        r = EvalResult(agent_name="x",
                       schema_valid=True,
                       schema_error="",
                       total_facts=4,
                       passed_facts=3)
        assert r.score == 0.75


class TestValidateSchema:
    """Pydantic validation against the SCHEMA_MAP registry."""

    def test_known_schema_validates_clean_payload(self):
        ok, err = validate_schema({"reactions": []}, "enzyme_kinetics")
        assert ok is True
        assert err == ""

    def test_unknown_schema_returns_explicit_error(self):
        ok, err = validate_schema({}, "this_schema_does_not_exist")
        assert ok is False
        assert "Unknown schema" in err


class TestExtractFieldDSL:
    """Six core DSL patterns. Every other case is a composition of these."""

    def test_dotted_path_resolves_nested_keys(self):
        data = {"statistics": {"total_variants": 13}}

        assert extract_field(data, "statistics.total_variants") == 13

    def test_wildcard_collects_field_from_each_item(self):
        data = {"reactions": [{"name": "Des27"}, {"name": "Des27.7"}]}

        assert extract_field(data, "reactions[*].name") == ["Des27", "Des27.7"]

    def test_filter_returns_first_match_with_subfield(self):
        # The `[key=value]` filter compares against the *string* form,
        # so numeric values would need string spelling here.
        data = {
            "reactions": [
                {
                    "enzyme_name": "Des27",
                    "kinetics": {
                        "kcat/KM": 131
                    }
                },
                {
                    "enzyme_name": "Des27.7",
                    "kinetics": {
                        "kcat/KM": 150
                    }
                },
            ],
        }

        result = extract_field(data, "reactions[enzyme_name=Des27].kinetics.kcat/KM")

        assert result == 131

    def test_indexed_traversal_with_subfield(self):
        data = {"reactions": [{"name": "first"}, {"name": "second"}]}

        assert extract_field(data, "reactions[1].name") == "second"

    def test_dotted_get_resolves_keys_containing_dots(self):
        # The greedy-join logic in _dotted_get handles literal dotted
        # keys like "kcat/KM" living under "statistics.kcat.KM" path
        # syntax. This is the trickiest and most error-prone branch.
        data = {"statistics": {"kcat.KM": 42}}

        assert extract_field(data, "statistics.kcat.KM") == 42

    def test_returns_none_on_missing_path_or_none_input(self):
        assert extract_field({"a": 1}, "missing") is None
        assert extract_field({"a": {}}, "a.b.c") is None
        assert extract_field(None, "anything") is None
        assert extract_field({"a": 1}, "") is None


class TestCheckCondition:
    """Each implemented condition branch + unknown-name fallback."""

    def test_length_gte_passes_and_fails_with_typeerror_path(self):
        # Pass on length match.
        ok, _ = _check_condition([1, 2, 3], "length_gte", {"value": 2})
        assert ok is True

        # Fail on shortage with measured length in message.
        ok, reason = _check_condition([1], "length_gte", {"value": 2})
        assert ok is False
        assert "1" in reason and "2" in reason

        # Non-len-able value reported as TypeError, not crash.
        ok, reason = _check_condition(42, "length_gte", {"value": 2})
        assert ok is False
        assert "cannot take len()" in reason

    def test_gte_and_approx_eq_numeric_branches(self):
        # gte coerces strings to float.
        ok, _ = _check_condition("3.5", "gte", {"value": 1})
        assert ok is True
        ok, _ = _check_condition("not a number", "gte", {"value": 1})
        assert ok is False

        # approx_eq within tolerance (default 0.15 = 15%).
        ok, _ = _check_condition(0.95, "approx_eq", {"value": 1.0})
        assert ok is True
        ok, reason = _check_condition(2.0, "approx_eq", {"value": 1.0})
        assert ok is False
        assert "diff" in reason  # percent-diff formatting

        # Zero is the special case — both must be zero exactly.
        ok, _ = _check_condition(0, "approx_eq", {"value": 0})
        assert ok is True
        ok, _ = _check_condition(0.001, "approx_eq", {"value": 0})
        assert ok is False

    def test_contains_family_substring_semantics_in_lists(self):
        # contains is plain str(actual) substring.
        ok, _ = _check_condition("hello world", "contains", {"value": "world"})
        assert ok is True

        # contains_all matches each value as a substring inside ANY
        # of the actual strings (legacy CSV-row semantics).
        actual = ["variant,score\nDes27.2,1\nDes27.7,2", "variant,score\nDes27.9,3"]
        ok, _ = _check_condition(actual, "contains_all",
                                 {"values": ["Des27.2", "Des27.7", "Des27.9"]})
        assert ok is True

        # contains_all reports the missing values in failure message.
        ok, reason = _check_condition(["Des27.2"], "contains_all",
                                      {"values": ["Des27.2", "Des27.9"]})
        assert ok is False
        assert "Des27.9" in reason

        # contains_any short-circuits on first hit.
        ok, _ = _check_condition(["KM = 0.21 mM", "kcat = 2.85 s-1"], "contains_any",
                                 {"values": ["12,696", "2.85"]})
        assert ok is True

    def test_unknown_condition_returns_failure_with_name(self):
        # Real golden.yaml files use names like "min_length", "min_value",
        # "equals", "is_null" that the engine does NOT implement. They
        # all funnel through this branch.
        ok, reason = _check_condition(5, "min_length", {"value": 1})
        assert ok is False
        assert "min_length" in reason

        # None actual short-circuits before condition dispatch.
        ok, reason = _check_condition(None, "gte", {"value": 1})
        assert ok is False
        assert "None" in reason


class TestEvaluateKeyFacts:
    """End-to-end orchestration: extract_field + _check_condition + counts."""

    def test_returns_passed_count_and_failure_messages(self):
        data = {"statistics": {"total": 5}, "reactions": [{"name": "Des27"}]}
        key_facts = [
            {
                "field": "statistics.total",
                "condition": "gte",
                "value": 3
            },
            {
                "field": "reactions[*].name",
                "condition": "contains_all",
                "values": ["Des27"]
            },
            {
                "field": "missing.path",
                "condition": "gte",
                "value": 1
            },
        ]

        result = evaluate_key_facts(data, key_facts, agent_name="test-agent")

        assert result.total_facts == 3
        assert result.passed_facts == 2
        assert len(result.failed_facts) == 1
        # Failure message includes agent_name, field, condition, reason.
        msg = result.failed_facts[0]
        assert "test-agent" in msg
        assert "missing.path" in msg
        assert "[gte]" in msg

    def test_passes_through_schema_validation_status(self):
        # evaluate_key_facts does NOT re-run schema validation — it
        # accepts the upstream verdict and threads it into the result.
        result = evaluate_key_facts(
            data={},
            key_facts=[],
            agent_name="agent",
            schema_valid=False,
            schema_error="bad shape",
        )

        assert result.schema_valid is False
        assert result.schema_error == "bad shape"
        # Empty key_facts -> vacuous success on the score axis.
        assert result.score == 1.0
