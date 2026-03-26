import asyncio
import csv
import json
import logging
import os
import re
from io import StringIO
from mimetypes import guess_type
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pathlib import Path

from gptase.agents.plan_loader import PlanRegistry
from gptase.core.orchestrator import AgentOrchestrator
from gptase.models.model import Model
from gptase.utils.config import FrameworkConfig

_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "agents"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GPTase Web UI API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared resources
config = FrameworkConfig()
model_manager = Model()
orchestrator = AgentOrchestrator(config)
plan_registry = PlanRegistry.get_instance()


# Pydantic Models
class ChatRequest(BaseModel):
    agent_id: str
    message: str
    image_paths: Optional[List[str]] = None
    auto_execute: bool = False


class PlanStartRequest(BaseModel):
    plan_id: str
    input_data: Dict[str, Any]
    document_path: Optional[str] = None
    auto_execute: bool = True
    auto_replan: bool = False


class SessionActionRequest(BaseModel):
    feedback: Optional[str] = None
    auto_replan: Optional[bool] = None


class WorkspaceArtifact(BaseModel):
    task_id: str
    agent_name: str
    artifact_type: Literal["json", "csv", "markdown", "pdf", "image", "directory", "other"]
    label: str
    path: str
    name: str
    size_bytes: int


class WorkspaceTaskSummary(BaseModel):
    task_id: str
    agent_name: str
    files: List[WorkspaceArtifact]
    primary_json: Optional[str] = None
    parsed_json: Optional[str] = None
    csv_files: List[str] = []
    summary: Optional[Dict[str, Any]] = None
    extraction_items: List[Dict[str, Any]] = []


class WorkspaceRunSummary(BaseModel):
    run_id: str
    run_path: str
    created_at: str
    tasks: List[WorkspaceTaskSummary]


class WorkspaceDocumentResponse(BaseModel):
    plan_id: str
    workspace_root: str
    document_name: str
    document_dir: str
    pdf_path: Optional[str] = None
    markdown_path: Optional[str] = None
    images_dir: Optional[str] = None
    runs: List[WorkspaceRunSummary]
    selected_run_id: Optional[str] = None
    selected_run_path: Optional[str] = None
    available_plans: List[str] = []


# API Routes
@app.get("/api/agents")
async def list_agents():
    """List all available agents."""
    agents = await orchestrator.list_available_agents()
    return [{
        "id": "auto",
        "name": "Auto (Orchestrator)"
    }] + [{
        "id": agent["agent_id"],
        "name": agent["agent_id"],
        "description": agent.get("description", ""),
    } for agent in agents]


@app.get("/api/plans")
async def list_plans():
    """List all available plans."""
    return plan_registry.list_plans()


def _default_workspace_roots() -> List[Path]:
    configured = os.environ.get("GPTASE_WORKSPACE_ROOTS", "").strip()
    roots: List[Path] = []
    if configured:
        for value in configured.split(os.pathsep):
            if value.strip():
                roots.append(Path(value.strip()).expanduser().resolve())
    roots.append(Path.cwd().resolve())
    external_default = Path("/Users/ryanxu/CodeBase/GPTase").resolve()
    if external_default not in roots:
        roots.append(external_default)
    deduped: List[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root not in seen:
            deduped.append(root)
            seen.add(root)
    return deduped


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_workspace_root(workspace_root: str) -> Path:
    resolved = Path(workspace_root).expanduser().resolve()
    allowed_roots = _default_workspace_roots()
    if any(_is_relative_to(resolved, allowed) or resolved == allowed for allowed in allowed_roots):
        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"Workspace root not found: {resolved}")
        return resolved
    raise HTTPException(status_code=403, detail="Workspace root is outside allowed roots")


def _resolve_workspace_root_for_document(workspace_root: str, document_name: str) -> Path:
    """Resolve an explicit root, or auto-detect one that contains the requested document."""
    if workspace_root.strip():
        return _resolve_workspace_root(workspace_root)

    for root in _default_workspace_roots():
        if (root / "data" / "input" / document_name).exists():
            return root

    raise HTTPException(
        status_code=404,
        detail=f"Document directory not found in allowed workspace roots: {document_name}",
    )


def _resolve_safe_file_path(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    allowed_roots = _default_workspace_roots()
    if not any(_is_relative_to(resolved, allowed) or resolved == allowed for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail="Requested file is outside allowed roots")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {resolved}")
    if resolved.is_dir():
        raise HTTPException(status_code=400, detail="Expected a file path, not a directory")
    return resolved


def _artifact_type_for_path(
    path: Path,
) -> Literal["json", "csv", "markdown", "pdf", "image", "directory", "other"]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    if suffix == ".md":
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "image"
    return "other"


def _task_id_from_file_name(name: str) -> str:
    stem = Path(name).stem
    for suffix in ("_result", "_parsed", "_reactions", "_analysis_results"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _extract_json_payload(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _load_markdown_lines(markdown_path: Optional[Path]) -> List[str]:
    if markdown_path is None or not markdown_path.exists():
        return []
    return markdown_path.read_text(encoding="utf-8").splitlines()


def _build_markdown_excerpt(lines: List[str], line_number: int, radius: int = 1) -> str:
    start = max(1, line_number - radius)
    end = min(len(lines), line_number + radius)
    excerpt = []
    for current in range(start, end + 1):
        excerpt.append(f"{current}: {lines[current - 1]}")
    return "\n".join(excerpt)


def _find_first_matching_line(lines: List[str], search_terms: List[str]) -> Optional[Dict[str, Any]]:
    normalized_terms = [term.strip() for term in search_terms if isinstance(term, str) and term.strip()]
    if not normalized_terms:
        return None
    for index, line in enumerate(lines, start=1):
        lower_line = line.lower()
        if any(term.lower() in lower_line for term in normalized_terms):
            return {
                "line_number": index,
                "snippet": line.strip(),
                "excerpt": _build_markdown_excerpt(lines, index),
                "matched_terms": normalized_terms,
            }
    return None


def _figure_search_terms(raw_figure_id: str) -> List[str]:
    figure_id = raw_figure_id.strip()
    terms = [figure_id]
    compact = figure_id.replace(":", " ").replace("|", " ")
    if compact not in terms:
        terms.append(compact)
    lowered = figure_id.lower()
    if lowered.startswith("figure "):
        suffix = figure_id.split(" ", 1)[1]
        terms.extend([f"Fig. {suffix}", f"Fig {suffix}"])
        if len(suffix) >= 2 and suffix[-1].isalpha():
            terms.append(f"Fig. {suffix[:-1]}")
            terms.append(f"Figure {suffix[:-1]}")
    return list(dict.fromkeys(term for term in terms if term))


def _normalize_figure_id(value: str) -> str:
    figure_id = value.strip()
    if ":" in figure_id:
        figure_id = figure_id.split(":", 1)[0].strip()
    return figure_id


def _figure_number_from_label(value: str) -> Optional[int]:
    match = re.search(r"(\d+)", value)
    if not match:
        return None
    return int(match.group(1))


def _build_extraction_items(
    agent_name: str,
    parsed_output: Dict[str, Any],
    markdown_lines: List[str],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if agent_name == "enzyme-kinetics-extractor":
        for index, reaction in enumerate(parsed_output.get("reactions", []), start=1):
            if not isinstance(reaction, dict):
                continue
            enzyme_name = str(reaction.get("enzyme_name", f"reaction-{index}"))
            kinetics = reaction.get("kinetics", {})
            search_terms = [enzyme_name]
            if isinstance(kinetics, dict):
                for key in ("kcat/KM", "kcat", "Km"):
                    value = kinetics.get(key)
                    if value is not None:
                        search_terms.append(str(value))
            anchor = _find_first_matching_line(markdown_lines, search_terms)
            items.append({
                "item_id": f"{agent_name}-{index}",
                "item_type": "reaction",
                "title": enzyme_name,
                "payload": reaction,
                "anchors": [anchor] if anchor else [],
            })

    if agent_name == "vision-image-analyzer":
        figure_anchors_by_image_number: Dict[int, Dict[str, Any]] = {}
        for index, table in enumerate(parsed_output.get("extracted_tables", []), start=1):
            if not isinstance(table, dict):
                continue
            figure_id = str(table.get("figure_id", f"figure-{index}"))
            image_number = table.get("image_number")
            normalized_figure_id = _normalize_figure_id(figure_id)
            anchor = _find_first_matching_line(markdown_lines, _figure_search_terms(normalized_figure_id))
            if anchor and isinstance(image_number, int):
                figure_anchors_by_image_number[image_number] = anchor
            items.append({
                "item_id": f"{agent_name}-table-{index}",
                "item_type": "vision_table",
                "title": normalized_figure_id,
                "payload": table,
                "anchors": [anchor] if anchor else [],
            })
        for index, analysis_result in enumerate(parsed_output.get("analysis_results", []), start=1):
            if not isinstance(analysis_result, dict):
                continue
            figure_id = str(analysis_result.get("figure_id", f"analysis-{index}"))
            image_number = analysis_result.get("image_number")
            normalized_figure_id = _normalize_figure_id(figure_id)
            anchor = _find_first_matching_line(markdown_lines, _figure_search_terms(normalized_figure_id))
            if anchor is None and isinstance(image_number, int):
                anchor = figure_anchors_by_image_number.get(image_number)
            if anchor is None and isinstance(image_number, int):
                figure_number = _figure_number_from_label(normalized_figure_id)
                if figure_number is not None:
                    anchor = _find_first_matching_line(markdown_lines, _figure_search_terms(f"Figure {figure_number}"))
            items.append({
                "item_id": f"{agent_name}-analysis-{index}",
                "item_type": "vision_analysis",
                "title": figure_id,
                "payload": analysis_result,
                "anchors": [anchor] if anchor else [],
            })

    return items


def _collect_vision_auxiliary_csvs(
    parsed_output: Dict[str, Any],
    auxiliary_csvs: List[Path],
) -> List[Path]:
    auxiliary_by_image_number = {
        int(match.group(1)): path
        for path in auxiliary_csvs
        if (match := re.fullmatch(r"table_(\d+)\.csv", path.name))
    }
    collected: List[Path] = []
    seen: set[Path] = set()
    for table in parsed_output.get("extracted_tables", []):
        if not isinstance(table, dict):
            continue
        image_number = table.get("image_number")
        if not isinstance(image_number, int):
            continue
        path = auxiliary_by_image_number.get(image_number)
        if path and path not in seen:
            seen.add(path)
            collected.append(path)
    return collected


def _extract_summary_from_task(agent_name: str, primary_json_path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if primary_json_path is None:
        return None
    payload = _extract_json_payload(primary_json_path)
    if not isinstance(payload, dict):
        return None
    parsed_output = payload.get("parsed_output")
    if not isinstance(parsed_output, dict):
        return None

    if agent_name == "enzyme-extraction-summary":
        return {
            "kind": "summary",
            "summary_report": parsed_output.get("summary_report"),
            "statistics": parsed_output.get("statistics"),
            "top_performers": parsed_output.get("top_performers"),
            "data_quality_flags": parsed_output.get("data_quality_flags"),
        }
    if agent_name == "enzyme-kinetics-extractor":
        reactions = parsed_output.get("reactions")
        return {
            "kind": "reactions",
            "reactions": reactions if isinstance(reactions, list) else [],
            "reaction_count": len(reactions) if isinstance(reactions, list) else 0,
        }
    if agent_name == "vision-image-analyzer":
        return {
            "kind": "vision",
            "analysis_results": parsed_output.get("analysis_results"),
            "extracted_tables": parsed_output.get("extracted_tables"),
            "total_images": parsed_output.get("total_images"),
        }
    if agent_name == "document-structure-analyzer":
        return {
            "kind": "document-structure",
            "source_file": parsed_output.get("source_file"),
            "sections": parsed_output.get("sections"),
            "tables": parsed_output.get("tables"),
            "images": parsed_output.get("images"),
        }
    return {"kind": "generic", "parsed_output": parsed_output}


def _build_task_summaries(agent_dir: Path, markdown_lines: List[str]) -> List[WorkspaceTaskSummary]:
    grouped: Dict[str, List[Path]] = {}
    auxiliary_vision_csvs: List[Path] = []
    for entry in sorted(agent_dir.iterdir()):
        if entry.is_dir():
            task_files = sorted(path for path in entry.iterdir() if path.is_file())
            if task_files:
                grouped[entry.name] = task_files
            continue
        if not entry.is_file():
            continue
        if agent_dir.name == "vision-image-analyzer" and re.fullmatch(r"table_\d+\.csv", entry.name):
            auxiliary_vision_csvs.append(entry)
            continue
        task_id = _task_id_from_file_name(entry.name)
        grouped.setdefault(task_id, []).append(entry)

    task_summaries: List[WorkspaceTaskSummary] = []
    for task_id, files in grouped.items():
        artifact_paths = list(files)
        primary_json = next((str(path) for path in artifact_paths if path.name.endswith("_result.json")), None)
        parsed_json = next((str(path) for path in artifact_paths if path.name.endswith("_parsed.json")), None)
        primary_json_path = Path(primary_json) if primary_json else None
        primary_payload = _extract_json_payload(primary_json_path) if primary_json_path else None
        parsed_output = (
            primary_payload.get("parsed_output")
            if isinstance(primary_payload, dict) and isinstance(primary_payload.get("parsed_output"), dict)
            else {}
        )
        if agent_dir.name == "vision-image-analyzer":
            artifact_paths.extend(_collect_vision_auxiliary_csvs(parsed_output, auxiliary_vision_csvs))

        artifacts = [
            WorkspaceArtifact(
                task_id=task_id,
                agent_name=agent_dir.name,
                artifact_type=_artifact_type_for_path(file_path),
                label=file_path.name,
                path=str(file_path),
                name=file_path.name,
                size_bytes=file_path.stat().st_size,
            )
            for file_path in artifact_paths
        ]
        csv_files = [str(path) for path in artifact_paths if path.suffix.lower() == ".csv"]
        task_summaries.append(
            WorkspaceTaskSummary(
                task_id=task_id,
                agent_name=agent_dir.name,
                files=artifacts,
                primary_json=primary_json,
                parsed_json=parsed_json,
                csv_files=csv_files,
                summary=_extract_summary_from_task(agent_dir.name, primary_json_path),
                extraction_items=_build_extraction_items(agent_dir.name, parsed_output, markdown_lines),
            )
        )

    task_summaries.sort(key=lambda item: item.task_id)
    return task_summaries


def _parse_run_id_timestamp(run_id: str) -> float:
    parts = run_id.rsplit("_", 2)
    if len(parts) != 3:
        return 0.0
    date_part, time_part = parts[-2], parts[-1]
    digits = f"{date_part}{time_part}"
    return float(digits) if digits.isdigit() else 0.0


def _list_workspace_runs(workspace_root: Path, document_name: str, plan_id: str) -> List[WorkspaceRunSummary]:
    output_root = workspace_root / "data" / "output" / document_name
    if not output_root.exists():
        return []

    markdown_path = workspace_root / "data" / "input" / document_name / f"{document_name}.md"
    markdown_lines = _load_markdown_lines(markdown_path)

    runs: List[Tuple[float, WorkspaceRunSummary]] = []
    for run_dir in output_root.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith(f"{plan_id}_"):
            continue
        task_summaries: List[WorkspaceTaskSummary] = []
        for agent_dir in sorted(run_dir.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name not in {"enzyme-kinetics-extractor", "vision-image-analyzer"}:
                continue
            task_summaries.extend(_build_task_summaries(agent_dir, markdown_lines))
        run_summary = WorkspaceRunSummary(
            run_id=run_dir.name,
            run_path=str(run_dir),
            created_at=datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(),
            tasks=task_summaries,
        )
        runs.append((_parse_run_id_timestamp(run_dir.name), run_summary))

    runs.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in runs]


@app.get("/api/workspace/plans")
async def list_workspace_plans():
    """List plans available for plan workspace routing."""
    plans = plan_registry.list_plans()
    return [
        {
            "plan_id": item.get("plan_id"),
            "name": item.get("name"),
            "description": item.get("description"),
        }
        for item in plans
    ]


@app.get("/api/workspace/document", response_model=WorkspaceDocumentResponse)
async def get_workspace_document(
    plan_id: str = Query(...),
    workspace_root: str = Query(...),
    document_name: str = Query(...),
    run_id: Optional[str] = Query(None),
):
    """Resolve a document workspace for the dedicated plan explorer UI."""
    resolved_root = _resolve_workspace_root_for_document(workspace_root, document_name)
    document_dir = resolved_root / "data" / "input" / document_name
    if not document_dir.exists():
        raise HTTPException(status_code=404, detail=f"Document directory not found: {document_dir}")

    pdf_path = resolved_root / "data" / "input" / "documents" / f"{document_name}.pdf"
    markdown_path = document_dir / f"{document_name}.md"
    images_dir = document_dir / "images"
    runs = _list_workspace_runs(resolved_root, document_name, plan_id)

    selected_run = runs[0] if runs else None
    if run_id:
        selected_run = next((run for run in runs if run.run_id == run_id), None)
        if selected_run is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    available_plans = sorted({
        plan_dir.name.rsplit("_", 2)[0]
        for plan_dir in (resolved_root / "data" / "output" / document_name).iterdir()
        if plan_dir.is_dir() and "_" in plan_dir.name
    }) if (resolved_root / "data" / "output" / document_name).exists() else []

    return WorkspaceDocumentResponse(
        plan_id=plan_id,
        workspace_root=str(resolved_root),
        document_name=document_name,
        document_dir=str(document_dir),
        pdf_path=str(pdf_path) if pdf_path.exists() else None,
        markdown_path=str(markdown_path) if markdown_path.exists() else None,
        images_dir=str(images_dir) if images_dir.exists() else None,
        runs=runs,
        selected_run_id=selected_run.run_id if selected_run else None,
        selected_run_path=selected_run.run_path if selected_run else None,
        available_plans=available_plans,
    )


@app.get("/api/workspace/file")
async def get_workspace_file(path: str = Query(...)):
    """Serve workspace files with a safe allowlist rooted at configured workspace paths."""
    resolved = _resolve_safe_file_path(path)
    mime_type = guess_type(str(resolved))[0] or "application/octet-stream"
    suffix = resolved.suffix.lower()

    if suffix in {".md", ".txt", ".json", ".csv"}:
        content = resolved.read_text(encoding="utf-8")
        if suffix == ".json":
            return JSONResponse(content=json.loads(content))
        if suffix == ".csv":
            reader = csv.DictReader(StringIO(content))
            rows = list(reader)
            return JSONResponse({
                "type": "csv",
                "columns": reader.fieldnames or [],
                "rows": rows,
                "raw": content,
            })
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

    headers = {"Cache-Control": "public, max-age=3600"}
    if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        headers["Content-Disposition"] = "inline"
    return FileResponse(resolved, media_type=mime_type, headers=headers)


@app.get("/api/plans/{plan_id}")
async def get_plan_definition(plan_id: str):
    """Get full plan definition."""
    try:
        plan = plan_registry.get_plan(plan_id)
        return plan.model_dump()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    """Send a message to a specific agent."""
    try:
        if request.agent_id == "auto":
            result = await orchestrator.execute_task({
                "description": request.message,
                "auto_execute": request.auto_execute,
            })
        else:
            agent = orchestrator.agents.get(request.agent_id)
            if agent is None:
                raise ValueError(f"Agent not found: {request.agent_id}")
            result = await agent.run(request.message, image_paths=request.image_paths)
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan/run")
async def start_plan(request: PlanStartRequest):
    """Start a harness session from a predefined draft plan."""
    try:
        result = await orchestrator.execute_task({
            "description": request.input_data.get("text", f"Execute draft plan {request.plan_id}"),
            "goal": request.input_data.get("text", f"Execute draft plan {request.plan_id}"),
            "plan_id": request.plan_id,
            "input_data": request.input_data,
            "auto_execute": request.auto_execute,
            "auto_replan": request.auto_replan,
            "document_path": request.document_path or request.input_data.get("document_path"),
        })
        return result
    except Exception as e:
        logger.error(f"Plan start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    """List recent harness sessions."""
    return await orchestrator.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session status."""
    status = await orchestrator.get_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@app.get("/api/memory/{agent_id}")
async def get_agent_memory(agent_id: str):
    """Get the compressed working memory for a named agent."""
    try:
        return await orchestrator.get_agent_working_memory(agent_id)
    except Exception as e:
        logger.error(f"Agent memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/approve")
async def approve_session(session_id: str, request: SessionActionRequest):
    """Approve the current draft plan and optionally provide revision feedback."""
    result = await orchestrator.approve_plan(session_id, feedback=request.feedback)
    return result


@app.post("/api/sessions/{session_id}/input")
async def continue_session(session_id: str, request: SessionActionRequest):
    """Provide user feedback to revise or continue a goal session."""
    payload: Dict[str, Any] = {"session_id": session_id}
    if request.feedback:
        payload["feedback"] = request.feedback
    if request.auto_replan is not None:
        payload["auto_replan"] = request.auto_replan
    result = await orchestrator.execute_task(payload)
    return result


@app.get("/api/evals")
async def list_eval_agents():
    """List all agents that have eval trace files."""
    result = []
    if not _AGENTS_DIR.exists():
        return result
    for agent_dir in sorted(_AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        output_dir = agent_dir / "evals" / "output"
        traces = sorted(output_dir.glob("trace_*.json")) if output_dir.exists() else []
        if not traces:
            continue
        try:
            with open(traces[-1], encoding="utf-8") as f:
                summary = json.load(f).get("summary", {})
        except Exception:
            summary = {}
        result.append({
            "agent_name": agent_dir.name,
            "trace_count": len(traces),
            "latest_timestamp": summary.get("timestamp", ""),
            "latest_model": summary.get("model", ""),
            "latest_status": summary.get("final_status", ""),
        })
    return result


@app.get("/api/evals/{agent_name}/traces")
async def list_agent_traces(agent_name: str):
    """List trace summaries (no steps) for an agent, newest first."""
    output_dir = _AGENTS_DIR / agent_name / "evals" / "output"
    if not output_dir.exists():
        return []
    traces = []
    for trace_file in sorted(output_dir.glob("trace_*.json"), reverse=True):
        try:
            with open(trace_file, encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary", {})
            summary["filename"] = trace_file.name
            summary["step_count"] = len(data.get("steps", []))
            traces.append(summary)
        except Exception:
            continue
    return traces


@app.get("/api/evals/{agent_name}/traces/{filename}")
async def get_trace(agent_name: str, filename: str):
    """Get a full trace file including all steps."""
    if not filename.startswith("trace_") or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid trace filename")
    trace_file = _AGENTS_DIR / agent_name / "evals" / "output" / filename
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail="Trace not found")
    with open(trace_file, encoding="utf-8") as f:
        data = json.load(f)
    data["summary"]["filename"] = filename
    return data


@app.websocket("/ws/plan/{session_id}")
async def plan_websocket(websocket: WebSocket, session_id: str):
    """WebSocket for real-time plan updates."""
    await websocket.accept()
    try:
        await websocket.send_json({
            "type": "status",
            "data": "connected",
            "session_id": session_id
        })

        # Keep connection open
        while True:
            status = await orchestrator.get_session_status(session_id)
            if status:
                await websocket.send_json({"type": "update", "data": status})

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# Mount static files for the UI
ui_dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "ui", "dist")

if os.path.exists(ui_dist_path):
    assets_path = os.path.join(ui_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)

        index_file = os.path.join(ui_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": "UI build not found. Run 'cd ui && npm run build'"}
else:

    @app.get("/")
    async def root_info():
        return {"info": "GPTase API is running. UI not built."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
