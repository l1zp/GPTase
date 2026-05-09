"""Tests for the YAML plan -> Coordinator prompt expander."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from gptase.agents.plan_prompt import detect_supplementary_path
from gptase.agents.plan_prompt import expand_plan_to_prompt
from gptase.agents.plan_prompt import PlanPromptError


def _write_plan(tmp_path: Path, name: str, data: dict) -> Path:
    """Write a YAML plan into a tmp directory and return that directory."""
    plan_dir = tmp_path / "plans"
    plan_dir.mkdir(exist_ok=True)
    (plan_dir / f"{name}.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    return plan_dir


class TestExpandLegacySchema:
    """Cover the existing enzyme_extraction_pipeline.yaml shape."""

    def test_renders_all_step_ids(self, tmp_path):
        plan_dir = _write_plan(
            tmp_path, "demo", {
                "plan_id":
                "demo",
                "name":
                "Demo Pipeline",
                "description":
                "Test description.",
                "workflow": [
                    {
                        "step_id": "1",
                        "agent": "document_structure_analyzer",
                        "description": "Analyze",
                        "inputs": {
                            "document_path": "{{document_path}}"
                        },
                    },
                    {
                        "parallel": [
                            {
                                "step_id": "2a",
                                "agent": "enzyme_kinetics_extractor",
                                "description": "Text extract",
                                "replicate": 3,
                                "inputs": {
                                    "document_path": "{{document_path}}"
                                },
                            },
                            {
                                "step_id": "2b",
                                "agent": "vision_image_analyzer",
                                "description": "Vision",
                                "replicate": 3,
                                "inputs": {
                                    "images": "{{step1.images}}"
                                },
                            },
                        ]
                    },
                    {
                        "step_id": "3s",
                        "agent": "enzyme_kinetics_extractor",
                        "description": "SI extract",
                        "optional": True,
                        "inputs": {
                            "document_path": "{{si_document_path}}"
                        },
                    },
                    {
                        "step_id": "4",
                        "agent": "enzyme_variant_normalizer",
                        "description": "Normalize",
                        "inputs": {
                            "text_extraction_data": "{{step2a}}"
                        },
                    },
                    {
                        "step_id": "5",
                        "agent": "enzyme_extraction_summary",
                        "description": "Summary",
                        "inputs": {},
                    },
                ],
            })

        prompt = expand_plan_to_prompt(
            "demo",
            document_path="/tmp/paper.md",
            plan_dir=plan_dir,
        )

        for sid in ["Step 1", "Step 2a", "Step 2b", "Step 3s", "Step 4", "Step 5"]:
            assert sid in prompt, f"Missing {sid} in prompt"

    def test_replicate_renders_exactly_n(self, tmp_path):
        plan_dir = _write_plan(
            tmp_path, "rep", {
                "plan_id":
                "rep",
                "name":
                "Rep",
                "workflow": [{
                    "step_id": "x",
                    "agent": "enzyme_kinetics_extractor",
                    "description": "",
                    "replicate": 3,
                    "inputs": {},
                }],
            })
        prompt = expand_plan_to_prompt("rep", plan_dir=plan_dir)
        assert "EXACTLY 3 parallel" in prompt

    def test_agent_id_normalized_to_dash(self, tmp_path):
        plan_dir = _write_plan(
            tmp_path, "norm", {
                "plan_id":
                "norm",
                "name":
                "Norm",
                "workflow": [{
                    "step_id": "1",
                    "agent": "enzyme_variant_normalizer",
                    "description": "",
                    "inputs": {},
                }],
            })
        prompt = expand_plan_to_prompt("norm", plan_dir=plan_dir)
        assert 'agent_id="enzyme-variant-normalizer"' in prompt
        assert "enzyme_variant_normalizer" not in prompt.split("DelegateTask(", 1)[1]

    def test_document_path_substituted(self, tmp_path):
        plan_dir = _write_plan(
            tmp_path, "subst", {
                "plan_id":
                "subst",
                "name":
                "Subst",
                "workflow": [{
                    "step_id": "1",
                    "agent": "doc_agent",
                    "description": "Read",
                    "inputs": {
                        "document_path": "{{document_path}}"
                    },
                }],
            })
        prompt = expand_plan_to_prompt(
            "subst",
            document_path="/abs/paper.md",
            plan_dir=plan_dir,
        )
        assert "/abs/paper.md" in prompt
        assert "{{document_path}}" not in prompt

    def test_unknown_placeholder_left_intact(self, tmp_path):
        plan_dir = _write_plan(
            tmp_path, "leak", {
                "plan_id":
                "leak",
                "name":
                "Leak",
                "workflow": [{
                    "step_id": "2",
                    "agent": "x",
                    "description": "",
                    "inputs": {
                        "ref": "{{step1.sections}}"
                    },
                }],
            })
        prompt = expand_plan_to_prompt("leak", plan_dir=plan_dir)
        # Step-N references must NOT be silently replaced — LLM needs to see them.
        assert "{{step1.sections}}" in prompt


class TestExpandSimplifiedSchema:
    """Cover the new ``steps:`` schema introduced for Slice 5."""

    def test_steps_list_with_parallel_with(self, tmp_path):
        plan_dir = _write_plan(
            tmp_path,
            "new",
            {
                "plan_id":
                "new",
                "name":
                "New",
                "steps": [
                    {
                        "id": "1",
                        "agent": "doc",
                        "description": "Analyze",
                        "inputs": {
                            "p": "{{document_path}}"
                        },
                    },
                    {
                        "id": "2a",
                        "agent": "extract",
                        "description": "Text",
                        "replicas": 3,
                        "parallel_with": ["2b"],
                        "inputs": {},
                    },
                    {
                        "id": "2b",
                        "agent": "vision",
                        "description": "Vis",
                        "replicas": 3,
                        "parallel_with": ["2a"],
                        "inputs": {},
                    },
                ],
            },
        )
        prompt = expand_plan_to_prompt(
            "new",
            document_path="/p.md",
            plan_dir=plan_dir,
        )
        assert "Step 1" in prompt
        assert "Step 2a" in prompt
        assert "Step 2b" in prompt
        assert "EXACTLY 3 parallel" in prompt


class TestErrors:
    """Defensive checks."""

    def test_missing_plan_raises(self, tmp_path):
        plan_dir = tmp_path / "empty"
        plan_dir.mkdir()
        with pytest.raises(PlanPromptError):
            expand_plan_to_prompt("nope", plan_dir=plan_dir)

    def test_no_steps_raises(self, tmp_path):
        plan_dir = _write_plan(tmp_path, "empty", {"plan_id": "empty", "name": "Empty"})
        with pytest.raises(PlanPromptError):
            expand_plan_to_prompt("empty", plan_dir=plan_dir)


class TestDetectSupplementaryPath:
    """SI auto-detection covers both legacy (sibling) and new (subdir) layouts."""

    def test_returns_none_when_no_si_anywhere(self, tmp_path):
        paper = tmp_path / "paper.md"
        paper.write_text("# main\n", encoding="utf-8")
        assert detect_supplementary_path(str(paper)) is None

    def test_finds_sibling_si_md(self, tmp_path):
        paper = tmp_path / "paper.md"
        paper.write_text("# main\n", encoding="utf-8")
        si = tmp_path / "paper_si.md"
        si.write_text("# si\n", encoding="utf-8")
        assert detect_supplementary_path(str(paper)) == str(si)

    def test_finds_si_subdir_main_md(self, tmp_path):
        # MinerU layout: paper_dir/main.md + paper_dir/SI_*/main.md
        paper_dir = tmp_path / "paperX"
        paper_dir.mkdir()
        paper = paper_dir / "main.md"
        paper.write_text("# main\n", encoding="utf-8")

        si_dir = paper_dir / "SI_41586_2025_9136_MOESM1_ESM"
        si_dir.mkdir()
        si_main = si_dir / "main.md"
        si_main.write_text("# si\n", encoding="utf-8")

        assert detect_supplementary_path(str(paper)) == str(si_main)

    def test_picks_alphabetically_first_when_multiple_si(self, tmp_path):
        paper_dir = tmp_path / "paperY"
        paper_dir.mkdir()
        paper = paper_dir / "main.md"
        paper.write_text("# main\n", encoding="utf-8")

        for name in ["SI_MOESM3", "SI_MOESM1", "SI_MOESM2"]:
            d = paper_dir / name
            d.mkdir()
            (d / "main.md").write_text(f"# si {name}\n", encoding="utf-8")

        result = detect_supplementary_path(str(paper))
        assert result is not None and result.endswith("SI_MOESM1/main.md")

    def test_recognizes_supplementary_named_dir(self, tmp_path):
        paper_dir = tmp_path / "paperZ"
        paper_dir.mkdir()
        paper = paper_dir / "main.md"
        paper.write_text("# main\n", encoding="utf-8")

        si_dir = paper_dir / "supplementary_info"
        si_dir.mkdir()
        si_main = si_dir / "main.md"
        si_main.write_text("# si\n", encoding="utf-8")

        assert detect_supplementary_path(str(paper)) == str(si_main)

    def test_skips_si_subdir_without_main_md(self, tmp_path):
        paper_dir = tmp_path / "paperW"
        paper_dir.mkdir()
        paper = paper_dir / "main.md"
        paper.write_text("# main\n", encoding="utf-8")

        # SI dir exists but contains no main.md
        si_dir = paper_dir / "SI_empty"
        si_dir.mkdir()

        assert detect_supplementary_path(str(paper)) is None

    def test_sibling_si_takes_precedence_over_subdir(self, tmp_path):
        paper_dir = tmp_path / "paperV"
        paper_dir.mkdir()
        paper = paper_dir / "main.md"
        paper.write_text("# main\n", encoding="utf-8")

        sibling = paper_dir / "main_si.md"
        sibling.write_text("# si sibling\n", encoding="utf-8")

        si_dir = paper_dir / "SI_MOESM1"
        si_dir.mkdir()
        (si_dir / "main.md").write_text("# si subdir\n", encoding="utf-8")

        assert detect_supplementary_path(str(paper)) == str(sibling)

    def test_returns_none_for_nonexistent_path(self):
        assert detect_supplementary_path("/nonexistent/path.md") is None

    def test_returns_none_for_empty_input(self):
        assert detect_supplementary_path("") is None
