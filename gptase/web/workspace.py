"""Workspace builder utilities for the plan explorer API.

All file-system access goes through the allowlist-based resolver functions
(_resolve_workspace_root, _resolve_safe_file_path) so that no path outside
the configured GPTASE_WORKSPACE_ROOTS can be reached.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WorkspaceArtifact(BaseModel):
    task_id: str
    agent_name: str
    artifact_type: Literal["json", "csv", "markdown", "pdf", "image", "directory",
                           "other"]
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


# ---------------------------------------------------------------------------
# Path safety helpers
# ---------------------------------------------------------------------------


def _default_workspace_roots() -> List[Path]:
    """Return the list of allowed workspace root paths.

    Reads GPTASE_WORKSPACE_ROOTS (colon-separated on POSIX, semicolon on
    Windows) and always appends the current working directory as a fallback.
    """
    configured = os.environ.get("GPTASE_WORKSPACE_ROOTS", "").strip()
    roots: List[Path] = []
    if configured:
        for value in configured.split(os.pathsep):
            if value.strip():
                roots.append(Path(value.strip()).expanduser().resolve())
    roots.append(Path.cwd().resolve())
    deduped: List[Path] = []
    seen: set = set()
    for root in roots:
        if root not in seen:
            deduped.append(root)
            seen.add(root)
    return deduped


def _is_safe_under_roots(path: Path, allowed_roots: List[Path]) -> bool:
    """Return True if *path* is equal to or under one of *allowed_roots*."""
    for root in allowed_roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            pass
        if path == root:
            return True
    return False


def _resolve_workspace_root(workspace_root: str) -> Path:
    """Resolve *workspace_root* and verify it is inside the allowed roots."""
    resolved = Path(workspace_root).expanduser().resolve()
    if _is_safe_under_roots(resolved, _default_workspace_roots()):
        if not resolved.exists():
            raise HTTPException(status_code=404,
                                detail=f"Workspace root not found: {resolved}")
        return resolved
    raise HTTPException(status_code=403,
                        detail="Workspace root is outside allowed roots")


def _resolve_workspace_root_for_document(workspace_root: str,
                                         document_name: str) -> Path:
    """Resolve an explicit root, or auto-detect one that contains the document."""
    if workspace_root.strip():
        return _resolve_workspace_root(workspace_root)

    for root in _default_workspace_roots():
        if (root / "data" / "input" / document_name).exists():
            return root

    raise HTTPException(
        status_code=404,
        detail=
        f"Document directory not found in allowed workspace roots: {document_name}",
    )


def _resolve_safe_file_path(path: str) -> Path:
    """Resolve *path* and verify it points to a file inside the allowed roots."""
    resolved = Path(path).expanduser().resolve()
    if not _is_safe_under_roots(resolved, _default_workspace_roots()):
        raise HTTPException(status_code=403,
                            detail="Requested file is outside allowed roots")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {resolved}")
    if resolved.is_dir():
        raise HTTPException(status_code=400,
                            detail="Expected a file path, not a directory")
    return resolved


# ---------------------------------------------------------------------------
# Artifact classification helpers
# ---------------------------------------------------------------------------


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
            return stem[:-len(suffix)]
    return stem


# ---------------------------------------------------------------------------
# JSON / Markdown helpers
# ---------------------------------------------------------------------------


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
    return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))


def _find_first_matching_line(lines: List[str],
                              search_terms: List[str]) -> Optional[Dict[str, Any]]:
    normalized_terms = [
        t.strip() for t in search_terms if isinstance(t, str) and t.strip()
    ]
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


# ---------------------------------------------------------------------------
# Figure ID helpers
# ---------------------------------------------------------------------------


def _figure_search_terms(raw_figure_id: str) -> List[str]:
    figure_id = raw_figure_id.strip()
    terms = [figure_id]
    compact = figure_id.replace(":", " ").replace("|", " ")
    if compact not in terms:
        terms.append(compact)
    if figure_id.lower().startswith("figure "):
        suffix = figure_id.split(" ", 1)[1]
        terms.extend([f"Fig. {suffix}", f"Fig {suffix}"])
        if len(suffix) >= 2 and suffix[-1].isalpha():
            terms.append(f"Fig. {suffix[:-1]}")
            terms.append(f"Figure {suffix[:-1]}")
    return list(dict.fromkeys(t for t in terms if t))


def _normalize_figure_id(value: str) -> str:
    figure_id = value.strip()
    if ":" in figure_id:
        figure_id = figure_id.split(":", 1)[0].strip()
    return figure_id


def _figure_number_from_label(value: str) -> Optional[int]:
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Extraction item builders
# ---------------------------------------------------------------------------


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
        for index, table in enumerate(parsed_output.get("extracted_tables", []),
                                      start=1):
            if not isinstance(table, dict):
                continue
            figure_id = str(table.get("figure_id", f"figure-{index}"))
            image_number = table.get("image_number")
            normalized = _normalize_figure_id(figure_id)
            anchor = _find_first_matching_line(markdown_lines,
                                               _figure_search_terms(normalized))
            if anchor and isinstance(image_number, int):
                figure_anchors_by_image_number[image_number] = anchor
            items.append({
                "item_id": f"{agent_name}-table-{index}",
                "item_type": "vision_table",
                "title": normalized,
                "payload": table,
                "anchors": [anchor] if anchor else [],
            })
        for index, analysis_result in enumerate(parsed_output.get(
                "analysis_results", []),
                                                start=1):
            if not isinstance(analysis_result, dict):
                continue
            figure_id = str(analysis_result.get("figure_id", f"analysis-{index}"))
            image_number = analysis_result.get("image_number")
            normalized = _normalize_figure_id(figure_id)
            anchor = _find_first_matching_line(markdown_lines,
                                               _figure_search_terms(normalized))
            if anchor is None and isinstance(image_number, int):
                anchor = figure_anchors_by_image_number.get(image_number)
            if anchor is None and isinstance(image_number, int):
                figure_number = _figure_number_from_label(normalized)
                if figure_number is not None:
                    anchor = _find_first_matching_line(
                        markdown_lines, _figure_search_terms(f"Figure {figure_number}"))
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
    seen: set = set()
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


def _extract_summary_from_task(
        agent_name: str, primary_json_path: Optional[Path]) -> Optional[Dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Task / run builders
# ---------------------------------------------------------------------------


def _build_task_summaries(agent_dir: Path,
                          markdown_lines: List[str]) -> List[WorkspaceTaskSummary]:
    grouped: Dict[str, List[Path]] = {}
    auxiliary_vision_csvs: List[Path] = []
    for entry in sorted(agent_dir.iterdir()):
        if entry.is_dir():
            task_files = sorted(p for p in entry.iterdir() if p.is_file())
            if task_files:
                grouped[entry.name] = task_files
            continue
        if not entry.is_file():
            continue
        if agent_dir.name == "vision-image-analyzer" and re.fullmatch(
                r"table_\d+\.csv", entry.name):
            auxiliary_vision_csvs.append(entry)
            continue
        task_id = _task_id_from_file_name(entry.name)
        grouped.setdefault(task_id, []).append(entry)

    task_summaries: List[WorkspaceTaskSummary] = []
    for task_id, files in grouped.items():
        artifact_paths = list(files)
        primary_json = next(
            (str(p) for p in artifact_paths if p.name.endswith("_result.json")), None)
        parsed_json = next(
            (str(p) for p in artifact_paths if p.name.endswith("_parsed.json")), None)
        primary_json_path = Path(primary_json) if primary_json else None
        primary_payload = _extract_json_payload(
            primary_json_path) if primary_json_path else None
        parsed_output = (
            primary_payload.get("parsed_output") if isinstance(primary_payload, dict)
            and isinstance(primary_payload.get("parsed_output"), dict) else {})
        if agent_dir.name == "vision-image-analyzer":
            artifact_paths.extend(
                _collect_vision_auxiliary_csvs(parsed_output, auxiliary_vision_csvs))

        artifacts = [
            WorkspaceArtifact(
                task_id=task_id,
                agent_name=agent_dir.name,
                artifact_type=_artifact_type_for_path(fp),
                label=fp.name,
                path=str(fp),
                name=fp.name,
                size_bytes=fp.stat().st_size,
            ) for fp in artifact_paths
        ]
        csv_files = [str(p) for p in artifact_paths if p.suffix.lower() == ".csv"]
        task_summaries.append(
            WorkspaceTaskSummary(
                task_id=task_id,
                agent_name=agent_dir.name,
                files=artifacts,
                primary_json=primary_json,
                parsed_json=parsed_json,
                csv_files=csv_files,
                summary=_extract_summary_from_task(agent_dir.name, primary_json_path),
                extraction_items=_build_extraction_items(agent_dir.name, parsed_output,
                                                         markdown_lines),
            ))

    task_summaries.sort(key=lambda item: item.task_id)
    return task_summaries


def _parse_run_id_timestamp(run_id: str) -> float:
    parts = run_id.rsplit("_", 2)
    if len(parts) != 3:
        return 0.0
    date_part, time_part = parts[-2], parts[-1]
    digits = f"{date_part}{time_part}"
    return float(digits) if digits.isdigit() else 0.0


def list_workspace_runs(workspace_root: Path, document_name: str,
                        plan_id: str) -> List[WorkspaceRunSummary]:
    """Return workspace run summaries for *document_name*, newest first."""
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
            if not agent_dir.is_dir() or agent_dir.name not in {
                    "enzyme-kinetics-extractor",
                    "vision-image-analyzer",
            }:
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
