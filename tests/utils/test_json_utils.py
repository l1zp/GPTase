"""Unit tests for gptase.utils.json_utils.parse_json_content.

Coverage spans the three extraction strategies in priority order
(```json fence -> generic ``` fence -> direct JSON) plus the empty/None
guard. The list-vs-dict return-type lie is pinned by an explicit test so
that future tightening of the type annotation cannot silently regress.
"""
from gptase.utils.json_utils import parse_json_content


class TestParseJsonContent:
    """Cover all branches of the agent-output JSON extractor."""

    def test_json_fence_parses_object(self):
        content = '```json\n{"a": 1, "b": "x"}\n```'
        assert parse_json_content(content) == {"a": 1, "b": "x"}

    def test_json_fence_parses_list_despite_dict_type_hint(self):
        # Signature says Optional[dict] but json.loads on a top-level
        # array returns list — pin this so callers can rely on it.
        content = '```json\n[1, 2, 3]\n```'
        assert parse_json_content(content) == [1, 2, 3]

    def test_json_fence_with_invalid_payload_returns_none(self):
        content = '```json\nnot { valid json\n```'
        assert parse_json_content(content) is None

    def test_generic_fence_strips_language_tag_line(self):
        # Generic ``` fence drops the first line so language tags
        # like ```python or ```yaml don't poison the JSON parser.
        content = '```python\n{"k": 42}\n```'
        assert parse_json_content(content) == {"k": 42}

    def test_generic_fence_with_invalid_payload_returns_none(self):
        # Covers the generic-fence except branch.
        content = '```yaml\nfoo: bar\n```'
        assert parse_json_content(content) is None

    def test_direct_object(self):
        assert parse_json_content('{"key": "value"}') == {"key": "value"}

    def test_direct_array(self):
        assert parse_json_content('[1, 2, 3]') == [1, 2, 3]

    def test_leading_and_trailing_whitespace_stripped(self):
        assert parse_json_content('  \n  {"a": 1}  \n  ') == {"a": 1}

    def test_direct_invalid_json_returns_none(self):
        assert parse_json_content('{not: valid}') is None

    def test_plain_text_returns_none(self):
        assert parse_json_content('just some prose without JSON') is None

    def test_empty_string_returns_none(self):
        assert parse_json_content('') is None

    def test_none_input_returns_none(self):
        # The `if not content` guard handles None defensively even
        # though the type hint forbids it.
        assert parse_json_content(None) is None
