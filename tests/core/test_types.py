"""Unit tests for gptase.core.types.DispatchRequest.

Pin the four contracts that orchestrator + main + web all depend on:
documented defaults, explicit field round-trip, extra="allow" passthrough,
and the model_dump(exclude_none=True) shape consumed at
gptase/core/orchestrator.py:158 via **spread.
"""
from gptase.core.types import DispatchRequest


class TestDispatchRequest:
    """The typed input for AgentOrchestrator.dispatch()."""

    def test_default_construction_uses_documented_defaults(self):
        req = DispatchRequest()

        assert req.query == ""
        assert req.auto_execute is True
        assert req.id is None
        assert req.session_id is None
        assert req.agent_id is None
        assert req.input_data is None
        assert req.document_path is None
        assert req.workspace_dir is None
        assert req.image_paths is None

    def test_explicit_fields_round_trip(self):
        req = DispatchRequest(
            id="task-123",
            session_id="sess-abc",
            query="extract enzymes",
            agent_id="enzyme-kinetics-table-extractor",
            auto_execute=False,
            input_data={"key": "value"},
            document_path="/data/paper.md",
            workspace_dir="/data/output/paper",
            image_paths=["/img/a.png", "/img/b.png"],
        )

        assert req.id == "task-123"
        assert req.session_id == "sess-abc"
        assert req.query == "extract enzymes"
        assert req.agent_id == "enzyme-kinetics-table-extractor"
        assert req.auto_execute is False
        assert req.input_data == {"key": "value"}
        assert req.document_path == "/data/paper.md"
        assert req.workspace_dir == "/data/output/paper"
        assert req.image_paths == ["/img/a.png", "/img/b.png"]

    def test_extra_keys_preserved_via_allow_config(self):
        # ConfigDict(extra="allow") lets callers pass forward-compat keys
        # that the orchestrator can transparently spread downstream.
        req = DispatchRequest(query="q", custom_flag=True, plan_id="my_plan")

        # Pydantic v2 stores extra fields in model_extra.
        assert req.model_extra is not None
        assert req.model_extra["custom_flag"] is True
        assert req.model_extra["plan_id"] == "my_plan"

    def test_model_dump_exclude_none_matches_orchestrator_contract(self):
        # orchestrator.py:158 does **request.model_dump(exclude_none=True),
        # so unset Optional fields must NOT appear as keys (they would
        # collide with downstream defaults).
        req = DispatchRequest(query="q", auto_execute=True)

        dumped = req.model_dump(exclude_none=True)

        assert dumped == {"query": "q", "auto_execute": True}
        # None-valued Optional fields stripped:
        for absent in ("id", "session_id", "agent_id", "input_data", "document_path",
                       "workspace_dir", "image_paths"):
            assert absent not in dumped
