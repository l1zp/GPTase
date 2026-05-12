"""Step 3 driver: per-item kinetics extraction across the corpus.

Reads Step 1's per-paper has_kinetic_data verdicts and Step 2's
sections.{main,si.X}.json item tags. For each TRUE item, dispatches to
the appropriate extractor (table → enzyme-kinetics-table-extractor;
figure → vision-image-analyzer; section → enzyme-kinetics-text-extractor).
Aggregates per-paper results, calls enzyme-variant-normalizer
programmatically, writes kinetics.json with both raw extractions and
the normalized output.

Phase 1 scope: --skip-figures and --skip-text default ON until the
table path is validated. Use --enable-figures / --enable-text once
those phases ship.

Per-call artifacts go to papers/extractions/<paper>/.kinetics_workdir/
for idempotency (skip when present, override with --force).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import importlib.util
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.WARNING,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE = Path("/Users/ryanxu/CodeBase/GPTase")
EXTR = BASE / "papers/extractions"
SRC = BASE / "papers/markdowns"
DEFAULT_TIMEOUT = 360  # Per-call ceiling. Doubao Seed-2.0-pro under 4-worker
# concurrency can take 200+s on tables with deep reasoning; 240s was
# borderline on the Phase 1 batch (6 timeouts mostly near 240s).
DEFAULT_WORKERS = 4

# ---------------------------------------------------------------------------
# Lazy imports — gptase machinery + agent-local helpers
# ---------------------------------------------------------------------------


def _load_outline_module():
    spec = importlib.util.spec_from_file_location(
        "_kx_outline",
        BASE / ".claude/agents/enzyme-kinetics-content-tagger/outline.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_kx_outline"] = m
    spec.loader.exec_module(m)
    return m


def _load_normalizer():
    spec = importlib.util.spec_from_file_location(
        "_kx_normalizer",
        BASE / ".claude/agents/enzyme-variant-normalizer/normalizer.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_kx_normalizer"] = m
    spec.loader.exec_module(m)
    return m.normalize_variant_payload


# ---------------------------------------------------------------------------
# Paper / item enumeration
# ---------------------------------------------------------------------------


def true_papers() -> List[str]:
    out = []
    for d in sorted(EXTR.iterdir()):
        if not d.is_dir():
            continue
        sj = d / "screener.json"
        if not sj.exists():
            continue
        try:
            data = json.loads(sj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("has_kinetic_data") is True:
            out.append(d.name)
    return out


def _resolve_md_dir(paper: str, sections_data: Dict[str, Any]) -> Path:
    """Where to find the content_list.json for this sections.X.json."""
    if sections_data["source"] == "main":
        return SRC / paper / "main"
    return SRC / paper / "SI" / sections_data["si_filename"]


def enumerate_items(paper: str, outline_mod) -> List[Dict[str, Any]]:
    """Return [{paper, source_file, kind, item_id, document_path}] for each TRUE item."""
    paper_dir = EXTR / paper
    out: List[Dict[str, Any]] = []
    for sf in sorted(paper_dir.glob("sections.*.json")):
        sd = json.loads(sf.read_text(encoding="utf-8"))
        md_dir = _resolve_md_dir(paper, sd)
        cl = outline_mod.find_content_list_for(md_dir)
        if cl is None:
            log.warning("No content_list.json for %s/%s; skipping", paper, sf.name)
            continue
        outline = outline_mod.build_outline(cl)
        kind_by_id = {o.id: o.kind for o in outline}
        for it in sd["items"]:
            if not it.get("is_relevant"):
                continue
            kind = kind_by_id.get(it["id"])
            if kind is None:
                log.warning("paper=%s item_id=%d not in outline (stale tag?)", paper,
                            it["id"])
                continue
            out.append({
                "paper": paper,
                "source_file": sf.name,
                "kind": kind,
                "item_id": it["id"],
                "document_path": str(md_dir),
            })
    return out


# ---------------------------------------------------------------------------
# Extractor dispatch — one async function per kind
# ---------------------------------------------------------------------------


def _workdir(paper: str) -> Path:
    d = EXTR / paper / ".kinetics_workdir"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifact_path(paper: str, source_file: str, item_id: int, kind: str) -> Path:
    # source_file is "sections.main.json" or "sections.si.<dirname>.json"
    src_tag = source_file.replace("sections.", "").replace(".json", "")
    return _workdir(paper) / f"{kind}__{src_tag}__{item_id:03d}.json"


def _extract_final_json(stdout: str) -> Optional[Dict[str, Any]]:
    text = stdout.rstrip()
    end = text.rfind("}")
    if end == -1:
        return None
    search = text[:end + 1]
    while True:
        start = search.rfind("{")
        if start == -1:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            search = search[:start]


async def _run_table(item: Dict[str, Any], force: bool, timeout: int) -> Dict[str, Any]:
    artifact = _artifact_path(item["paper"], item["source_file"], item["item_id"],
                              "table")
    if artifact.exists() and not force:
        try:
            return {
                "item": item,
                "status": "cached",
                "result": json.loads(artifact.read_text(encoding="utf-8")),
            }
        except json.JSONDecodeError:
            pass

    desc = json.dumps({
        "document_path": item["document_path"],
        "item_id": item["item_id"]
    })
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "gptase",
            "agent",
            "-n",
            "enzyme-kinetics-table-extractor",
            "-d",
            desc,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return {
            "item": item,
            "status": "timeout",
            "duration_s": round(time.monotonic() - t0, 1),
        }

    elapsed = round(time.monotonic() - t0, 1)
    parsed = _extract_final_json(stdout_b.decode("utf-8", errors="replace"))
    if parsed is None:
        artifact.with_suffix(".raw.log").write_text(
            stdout_b.decode("utf-8", errors="replace") + "\n[STDERR]\n"
            + stderr_b.decode("utf-8", errors="replace"),
            encoding="utf-8",
        )
        return {"item": item, "status": "no_json", "duration_s": elapsed}
    artifact.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return {"item": item, "status": "ok", "duration_s": elapsed, "result": parsed}


async def _run_figure(item, force, timeout, outline_mod, vision_agent):
    """Phase 2: dispatch one figure to vision-image-analyzer programmatically.

    The vision agent is a singleton passed in so we don't pay
    Agent.from_markdown + Model() init costs per call. Each figure is
    one Task(image_paths=[abs_path], workspace_dir=...) — the framework
    loads the image as multimodal content and embeds it in the prompt.
    """
    artifact = _artifact_path(item["paper"], item["source_file"], item["item_id"],
                              "figure")
    if artifact.exists() and not force:
        try:
            return {
                "item": item,
                "status": "cached",
                "result": json.loads(artifact.read_text(encoding="utf-8")),
            }
        except json.JSONDecodeError:
            pass

    md_dir = Path(item["document_path"])
    cl = outline_mod.find_content_list_for(md_dir)
    if cl is None:
        return {"item": item, "status": "no_content_list"}
    outline = outline_mod.build_outline(cl)
    item_obj = next((o for o in outline if o.id == item["item_id"]), None)
    if item_obj is None:
        return {"item": item, "status": "item_not_in_outline"}
    if not item_obj.img_path:
        return {"item": item, "status": "no_img_path"}

    img_abs = (md_dir / item_obj.img_path).resolve()
    if not img_abs.is_file():
        return {
            "item": item,
            "status": "img_missing",
            "img_path_tried": str(img_abs),
        }

    from gptase.agents.types import Task

    caption_text = (item_obj.caption or "").strip() or "(no caption)"
    task_desc = json.dumps({
        "instruction":
        "Extract kinetic data from this single scientific figure.",
        "context": {
            "paper_id": item["paper"],
            "item_id": item["item_id"],
            "page_idx": item_obj.page_idx,
            "caption": caption_text,
        },
        "images": [{
            "image_path": str(img_abs),
            "image_number": 1,
            "figure_id": caption_text[:80],
            "is_table_image": False,
            "is_reaction_related": True,
        }],
    })

    task = Task(
        description=task_desc,
        agent_id="vision-image-analyzer",
        workspace_dir=str(md_dir),
        image_paths=[str(img_abs)],
    )

    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(vision_agent.process_task(task),
                                        timeout=timeout)
    except asyncio.TimeoutError:
        return {
            "item": item,
            "status": "timeout",
            "duration_s": round(time.monotonic() - t0, 1),
        }
    except Exception as exc:
        return {
            "item": item,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "duration_s": round(time.monotonic() - t0, 1),
        }

    elapsed = round(time.monotonic() - t0, 1)
    if result.get("status") != "success":
        return {
            "item": item,
            "status": result.get("status", "error"),
            "error": result.get("error", ""),
            "duration_s": elapsed,
        }

    content_str = (result.get("data") or {}).get("content", "") or ""
    parsed = _extract_final_json(content_str) if content_str else None
    if parsed is None:
        # Save raw for debugging
        artifact.with_suffix(".raw.log").write_text(content_str, encoding="utf-8")
        return {"item": item, "status": "no_json", "duration_s": elapsed}

    artifact.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return {"item": item, "status": "ok", "duration_s": elapsed, "result": parsed}


async def _run_text(item, force, timeout):
    # Stub for Phase 3
    return {"item": item, "status": "skipped", "reason": "phase 3 not yet wired"}


# ---------------------------------------------------------------------------
# Per-paper aggregation + normalizer call
# ---------------------------------------------------------------------------


def _build_normalizer_input(paper: str, results: List[Dict[str, Any]],
                            outline_mod) -> Dict[str, Any]:
    """Aggregate per-call extractions into the normalizer's expected shape."""
    text_extraction_data: List[Dict[str, Any]] = []
    vision_extraction_data: List[Dict[str, Any]] = []

    # Group by source_file → main vs each SI
    paper_dir = EXTR / paper
    main_doc_path: Optional[str] = None
    si_doc_paths: List[str] = []
    for sf in sorted(paper_dir.glob("sections.*.json")):
        sd = json.loads(sf.read_text(encoding="utf-8"))
        md_dir = _resolve_md_dir(paper, sd)
        cl = outline_mod.find_content_list_for(md_dir)
        if cl is None:
            continue
        # Resolve actual .md file path that the normalizer can scan
        for cand in (md_dir / "full.md", md_dir / "main.md"):
            if cand.is_file():
                if sd["source"] == "main":
                    main_doc_path = str(cand)
                else:
                    si_doc_paths.append(str(cand))
                break

    for r in results:
        if r["status"] not in ("ok", "cached"):
            continue
        kind = r["item"]["kind"]
        result = r["result"]
        if kind == "table" or kind == "section":
            text_extraction_data.append({
                "reactions":
                result.get("reactions", []),
                "protein_sequences":
                result.get("protein_sequences", []),
            })
        elif kind == "figure":
            vision_extraction_data.append({
                "extracted_tables":
                result.get("extracted_tables", []),
                "analysis_results":
                result.get("analysis_results", []),
            })

    inputs: Dict[str, Any] = {
        "text_extraction_data": text_extraction_data,
        "vision_extraction_data": vision_extraction_data,
        "document_path": main_doc_path or "",
    }
    if si_doc_paths:
        # Normalizer takes a single si_document_path; if multiple SIs, use the first
        # and add the rest into text via separate replicas (already in
        # text_extraction_data above).
        inputs["si_document_path"] = si_doc_paths[0]
    return inputs


def _per_paper_output(paper: str, results: List[Dict[str, Any]],
                      normalizer_input: Dict[str, Any], normalized: Dict[str, Any],
                      elapsed_s: float) -> Dict[str, Any]:
    raw = {"tables": [], "sections": [], "figures": []}
    for r in results:
        kind = r["item"]["kind"]
        bucket = {"table": "tables", "section": "sections", "figure": "figures"}[kind]
        entry = {
            "item_id": r["item"]["item_id"],
            "source_file": r["item"]["source_file"],
            "status": r["status"],
            "duration_s": r.get("duration_s"),
        }
        if r["status"] in ("ok", "cached"):
            entry["result"] = r["result"]
        raw[bucket].append(entry)

    return {
        "paper_id":
        paper,
        "main_document_path":
        normalizer_input.get("document_path"),
        "si_document_paths": ([normalizer_input["si_document_path"]]
                              if normalizer_input.get("si_document_path") else []),
        "raw_extractions":
        raw,
        "normalized":
        normalized,
        "stats": {
            "n_table_calls":
            sum(1 for r in results if r["item"]["kind"] == "table"),
            "n_section_calls":
            sum(1 for r in results if r["item"]["kind"] == "section"),
            "n_figure_calls":
            sum(1 for r in results if r["item"]["kind"] == "figure"),
            "n_failed_calls":
            sum(1 for r in results if r["status"] not in ("ok", "cached", "skipped")),
            "n_skipped":
            sum(1 for r in results if r["status"] == "skipped"),
            "elapsed_s":
            elapsed_s,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_paper(paper: str,
                    args,
                    outline_mod,
                    normalize_fn,
                    sem: asyncio.Semaphore,
                    vision_agent=None) -> Dict[str, Any]:
    paper_t0 = time.monotonic()
    items = enumerate_items(paper, outline_mod)

    async def _bound(coro):
        async with sem:
            return await coro

    coros = []
    for it in items:
        if it["kind"] == "table":
            coros.append(_bound(_run_table(it, args.force, args.timeout)))
        elif it["kind"] == "figure" and args.enable_figures and vision_agent is not None:
            coros.append(
                _bound(
                    _run_figure(it, args.force, args.timeout, outline_mod,
                                vision_agent)))
        elif it["kind"] == "section" and args.enable_text:
            coros.append(_bound(_run_text(it, args.force, args.timeout)))

    results = await asyncio.gather(*coros) if coros else []

    normalizer_input = _build_normalizer_input(paper, results, outline_mod)
    try:
        normalized = normalize_fn(normalizer_input)
    except Exception as exc:
        log.error("normalize failed for %s: %s", paper, exc)
        normalized = {
            "normalized_variants": [],
            "normalization_summary": {
                "error": str(exc)
            },
        }

    elapsed = round(time.monotonic() - paper_t0, 1)
    out = _per_paper_output(paper, results, normalizer_input, normalized, elapsed)
    out_path = EXTR / paper / "kinetics.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    n_ok = sum(1 for r in results if r["status"] in ("ok", "cached"))
    n_fail = sum(1 for r in results if r["status"] not in ("ok", "cached", "skipped"))
    n_var = len(normalized.get("normalized_variants", []))
    print(
        f"[{paper[:55]:55s}] {len(results):>3} calls, {n_ok:>3} ok, "
        f"{n_fail:>2} fail, {n_var:>3} variants ({elapsed}s)",
        flush=True,
    )
    return {
        "paper": paper,
        "n_calls": len(results),
        "n_ok": n_ok,
        "n_fail": n_fail,
        "n_variants": n_var,
        "elapsed_s": elapsed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="Only run these paper names")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--force",
                    action="store_true",
                    help="Re-run even when artifact exists")
    ap.add_argument("--enable-figures",
                    action="store_true",
                    help="Phase 2 — dispatch figures to vision-image-analyzer")
    ap.add_argument("--enable-text",
                    action="store_true",
                    help="Phase 3 — dispatch sections to text-extractor")
    args = ap.parse_args()

    outline_mod = _load_outline_module()
    normalize_fn = _load_normalizer()

    papers = true_papers()
    if args.only:
        papers = [p for p in papers if p in set(args.only)]
        missing = set(args.only) - set(papers)
        if missing:
            log.warning("--only filter dropped non-TRUE/missing papers: %s", missing)
    print(
        f"Step 3 driver: {len(papers)} papers (workers={args.workers}, "
        f"figures={'on' if args.enable_figures else 'OFF'}, "
        f"text={'on' if args.enable_text else 'OFF'})\n",
        flush=True)

    # Vision agent singleton — only when figures are enabled. Loaded
    # lazily here so the table-only path doesn't pay the Agent +
    # Model() init cost.
    vision_agent = None
    if args.enable_figures:
        from gptase.agents.base import Agent
        from gptase.models.model import Model
        vision_model = Model()
        vision_agent = Agent.from_markdown("vision-image-analyzer",
                                           model_manager=vision_model)
        print(f"  vision-image-analyzer loaded; image model={vision_agent.model_name}",
              flush=True)

    async def _run_all() -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(args.workers)
        return await asyncio.gather(*[
            run_paper(
                p, args, outline_mod, normalize_fn, sem, vision_agent=vision_agent)
            for p in papers
        ])

    t_start = time.monotonic()
    rows = asyncio.run(_run_all())
    total = round(time.monotonic() - t_start, 1)

    summary = EXTR / "_summary.kinetics.csv"
    with summary.open("w", newline="") as f:
        w = csv.DictWriter(f,
                           fieldnames=[
                               "paper", "n_calls", "n_ok", "n_fail", "n_variants",
                               "elapsed_s"
                           ])
        w.writeheader()
        w.writerows(rows)

    n_ok = sum(r["n_ok"] for r in rows)
    n_fail = sum(r["n_fail"] for r in rows)
    n_var = sum(r["n_variants"] for r in rows)
    print(
        f"\n=== Done in {total}s — {len(rows)} papers, {n_ok} calls ok, "
        f"{n_fail} failed, {n_var} normalized variants. Summary: {summary} ===",
        flush=True,
    )
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
