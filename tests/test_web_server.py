import json
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from gptase.web import server
from gptase.web import workspace


async def test_list_agents_exposes_orchestrator_identity(monkeypatch):
    list_available_agents = AsyncMock(
        return_value=[{
            "agent_id": "document-structure-analyzer",
            "description": "Analyze document structure",
        }])
    monkeypatch.setattr(server.orchestrator, "list_available_agents",
                        list_available_agents)

    result = await server.list_agents()

    assert result[0]["id"] == "orchestrator"
    assert result[0]["name"] == "Orchestrator"


async def test_start_plan_forwards_input_data_and_document_path(monkeypatch):
    execute_task = AsyncMock(return_value={"status": "awaiting_approval"})
    monkeypatch.setattr(server.orchestrator, "execute_task", execute_task)

    request = server.PlanStartRequest(
        plan_id="enzyme_extraction_pipeline",
        input_data={
            "text": "extract this enzyme paper",
            "document_path": "/tmp/paper.md",
            "extra": "value",
        },
        document_path="/tmp/paper.md",
        auto_execute=True,
        auto_replan=False,
    )

    result = await server.start_plan(request)

    assert result["status"] == "awaiting_approval"
    execute_task.assert_awaited_once_with({
        "description": "extract this enzyme paper",
        "goal": "extract this enzyme paper",
        "plan_id": "enzyme_extraction_pipeline",
        "input_data": {
            "text": "extract this enzyme paper",
            "document_path": "/tmp/paper.md",
            "extra": "value",
        },
        "auto_execute": True,
        "auto_replan": False,
        "document_path": "/tmp/paper.md",
    })


async def test_chat_with_agent_rejects_removed_auto_alias():
    request = server.ChatRequest(agent_id="auto", message="hello", image_paths=None)

    with pytest.raises(Exception, match="Agent not found: auto"):
        await server.chat_with_agent(request)


async def test_chat_with_orchestrator_uses_execute_task(monkeypatch):
    execute_task = AsyncMock(return_value={"status": "awaiting_approval"})
    run = AsyncMock()
    monkeypatch.setattr(server.orchestrator, "execute_task", execute_task)
    monkeypatch.setattr(server.orchestrator, "run", run)

    request = server.ChatRequest(agent_id="orchestrator",
                                 message="hello",
                                 image_paths=None,
                                 auto_execute=False)
    result = await server.chat_with_agent(request)

    assert result["status"] == "awaiting_approval"
    execute_task.assert_awaited_once_with({
        "description": "hello",
        "goal": "hello",
        "auto_execute": False,
    })
    run.assert_not_awaited()


async def test_get_agent_memory_returns_working_memory(monkeypatch):
    get_memory = AsyncMock(
        return_value={
            "agent_id": "memory-agent",
            "working_memory": {
                "summary": "Prior context",
                "metadata": {
                    "status": "success"
                },
                "last_updated": "2026-03-23T00:00:00",
            },
        })
    monkeypatch.setattr(server.orchestrator, "get_agent_working_memory", get_memory)

    result = await server.get_agent_memory("memory-agent")

    assert result["agent_id"] == "memory-agent"
    assert result["working_memory"]["summary"] == "Prior context"
    get_memory.assert_awaited_once_with("memory-agent")


@pytest.fixture
def workspace_fixture(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    document_name = "listov2025"
    plan_id = "enzyme_extraction_pipeline"

    document_dir = workspace_root / "data" / "input" / document_name
    images_dir = document_dir / "images"
    documents_dir = workspace_root / "data" / "input" / "documents"
    output_dir = workspace_root / "data" / "output" / document_name
    run_old = output_dir / f"{plan_id}_20260323_165401"
    run_new = output_dir / f"{plan_id}_20260324_101530"

    images_dir.mkdir(parents=True)
    documents_dir.mkdir(parents=True)
    run_old.mkdir(parents=True)
    run_new.mkdir(parents=True)

    (documents_dir / f"{document_name}.pdf").write_bytes(b"%PDF-1.4\nfake\n")
    (document_dir / f"{document_name}.md").write_text(
        "# Sample markdown\n\n"
        "Fig. 3 | Structural analysis of Des27.7.\n"
        "Extended Data Table 1 | Des27.7 kcat/KM 12696.\n"
        "![](images/figure1.png)\n",
        encoding="utf-8",
    )
    (images_dir / "figure1.png").write_bytes(b"png")

    for run_dir in (run_old, run_new):
        structure_dir = run_dir / "document-structure-analyzer"
        extract_dir = run_dir / "enzyme-kinetics-extractor"
        vision_dir = run_dir / "vision-image-analyzer"
        summary_dir = run_dir / "enzyme-extraction-summary"
        structure_dir.mkdir()
        extract_dir.mkdir()
        vision_dir.mkdir()
        summary_dir.mkdir()

        structure_task_dir = structure_dir / "1"
        extract_task_dir = extract_dir / "2a_r1"
        vision_task_dir = vision_dir / "2b_r1"
        summary_task_dir = summary_dir / "3"
        structure_task_dir.mkdir()
        extract_task_dir.mkdir()
        vision_task_dir.mkdir()
        summary_task_dir.mkdir()

        (structure_task_dir / "1_result.json").write_text(
            json.dumps({
                "parsed_output": {
                    "sections": [{
                        "section_name": "Results"
                    }],
                    "images": []
                }
            }),
            encoding="utf-8",
        )
        (structure_task_dir / "1_tables.csv").write_text(
            "table_id,is_reaction_related\n1,true\n", encoding="utf-8")
        (extract_task_dir / "2a_r1_result.json").write_text(
            json.dumps({"parsed_output": {
                "reactions": [{
                    "enzyme_name": "Des27.7"
                }]
            }}),
            encoding="utf-8",
        )
        (extract_task_dir / "2a_r1_reactions.csv").write_text(
            "enzyme_name,kcat_KM\nDes27.7,12696\n",
            encoding="utf-8",
        )
        (vision_task_dir / "2b_r1_result.json").write_text(
            json.dumps({
                "parsed_output": {
                    "analysis_results": [{
                        "image_number": 4,
                        "figure_id": "Figure 3b: Michaelis-Menten kinetics",
                        "content": "MM curve"
                    }],
                    "extracted_tables": [{
                        "image_number": 4,
                        "figure_id": "Figure 3b",
                        "csv_data": "Parameter,Value\nKM,0.21"
                    }],
                }
            }),
            encoding="utf-8",
        )
        (vision_task_dir / "2b_r1_analysis_results.csv").write_text(
            "figure_id,summary\nFigure 3b,MM curve\n",
            encoding="utf-8",
        )
        (vision_task_dir / "table_4.csv").write_text(
            "Parameter,Value\nKM,0.21\n",
            encoding="utf-8",
        )
        (summary_task_dir / "3_result.json").write_text(
            json.dumps({
                "parsed_output": {
                    "summary_report": "# Summary",
                    "top_performers": [{
                        "variant": "Des27.7"
                    }],
                    "statistics": {
                        "total_variants": 1
                    },
                }
            }),
            encoding="utf-8",
        )

    monkeypatch.setenv("GPTASE_WORKSPACE_ROOTS", str(workspace_root))
    return {
        "workspace_root": workspace_root,
        "document_name": document_name,
        "plan_id": plan_id,
        "run_old": run_old,
        "run_new": run_new,
    }


async def test_get_workspace_document_resolves_document_and_latest_run(
        workspace_fixture):
    result = await server.get_workspace_document(
        plan_id=workspace_fixture["plan_id"],
        workspace_root=str(workspace_fixture["workspace_root"]),
        document_name=workspace_fixture["document_name"],
        run_id=None,
    )

    assert result.document_name == "listov2025"
    assert result.pdf_path and result.pdf_path.endswith("listov2025.pdf")
    assert result.markdown_path and result.markdown_path.endswith("listov2025.md")
    assert result.selected_run_id == workspace_fixture["run_new"].name
    assert len(result.runs) == 2
    assert {task.agent_name
            for task in result.runs[0].tasks} == {
                "enzyme-kinetics-extractor",
                "vision-image-analyzer",
            }
    kinetics_task = next(task for task in result.runs[0].tasks
                         if task.agent_name == "enzyme-kinetics-extractor")
    assert kinetics_task.extraction_items
    assert kinetics_task.extraction_items[0]["anchors"]
    vision_task = next(task for task in result.runs[0].tasks
                       if task.agent_name == "vision-image-analyzer")
    assert all(task.task_id != "table_4" for task in result.runs[0].tasks)
    assert any(path.endswith("table_4.csv") for path in vision_task.csv_files)
    assert vision_task.extraction_items[0]["anchors"]


async def test_get_workspace_document_can_autodetect_root_when_workspace_root_is_blank(
        workspace_fixture):
    result = await server.get_workspace_document(
        plan_id=workspace_fixture["plan_id"],
        workspace_root="",
        document_name=workspace_fixture["document_name"],
        run_id=None,
    )

    assert result.workspace_root == str(workspace_fixture["workspace_root"])
    assert result.selected_run_id == workspace_fixture["run_new"].name


async def test_get_workspace_document_can_select_explicit_run(workspace_fixture):
    result = await server.get_workspace_document(
        plan_id=workspace_fixture["plan_id"],
        workspace_root=str(workspace_fixture["workspace_root"]),
        document_name=workspace_fixture["document_name"],
        run_id=workspace_fixture["run_old"].name,
    )

    assert result.selected_run_id == workspace_fixture["run_old"].name
    assert result.selected_run_path == str(workspace_fixture["run_old"])


async def test_get_workspace_file_returns_csv_payload(workspace_fixture):
    csv_path = (workspace_fixture["run_new"] / "enzyme-kinetics-extractor" / "2a_r1"
                / "2a_r1_reactions.csv")
    response = await server.get_workspace_file(path=str(csv_path))

    assert response.body
    payload = json.loads(response.body)
    assert payload["type"] == "csv"
    assert payload["columns"] == ["enzyme_name", "kcat_KM"]
    assert payload["rows"][0]["enzyme_name"] == "Des27.7"


async def test_get_workspace_file_rejects_outside_allowed_root(workspace_fixture):
    outside = workspace_fixture["workspace_root"].parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(server.HTTPException) as exc_info:
        await server.get_workspace_file(path=str(outside))

    assert exc_info.value.status_code == 403


async def test_resolve_workspace_root_rejects_outside_allowed_root(
        workspace_fixture, tmp_path):
    outside = tmp_path / "other_workspace"
    outside.mkdir()

    with pytest.raises(server.HTTPException) as exc_info:
        workspace._resolve_workspace_root(str(outside))

    assert exc_info.value.status_code == 403


class TestBuildExtractionItems:
    """Unit tests for workspace._build_extraction_items."""

    def test_kinetics_extractor_populates_items(self):
        parsed_output = {
            "reactions": [{
                "enzyme_name": "Des27",
                "kinetics": {
                    "kcat/KM": 130,
                    "Km": None
                },
            }]
        }
        markdown_lines = ["Mutation Des27 was analyzed.", "kcat/KM value: 130 M-1s-1."]
        items = workspace._build_extraction_items("enzyme-kinetics-extractor",
                                                  parsed_output, markdown_lines)

        assert len(items) == 1
        item = items[0]
        assert item["item_type"] == "reaction"
        assert item["title"] == "Des27"
        assert item["anchors"]  # should match "Des27" on line 1
        assert item["anchors"][0]["line_number"] == 1

    def test_kinetics_extractor_no_anchor_when_no_match(self):
        parsed_output = {"reactions": [{"enzyme_name": "XYZ999", "kinetics": {}}]}
        items = workspace._build_extraction_items("enzyme-kinetics-extractor",
                                                  parsed_output, [])
        assert items[0]["anchors"] == []

    def test_vision_analyzer_populates_items(self):
        parsed_output = {
            "extracted_tables": [{
                "figure_id": "Figure 3a",
                "image_number": 1
            }],
            "analysis_results": [{
                "figure_id": "Figure 3a: MM kinetics",
                "image_number": 1
            }],
        }
        markdown_lines = ["Figure 3a shows Michaelis-Menten curves."]
        items = workspace._build_extraction_items("vision-image-analyzer",
                                                  parsed_output, markdown_lines)

        assert len(items) == 2
        table_item = next(i for i in items if i["item_type"] == "vision_table")
        assert table_item["anchors"]
        analysis_item = next(i for i in items if i["item_type"] == "vision_analysis")
        assert analysis_item["anchors"]

    def test_unknown_agent_returns_empty(self):
        items = workspace._build_extraction_items("unknown-agent", {"data": [1, 2, 3]},
                                                  ["line1"])
        assert items == []
