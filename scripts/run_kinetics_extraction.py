"""Step 3 driver: per-item kinetics extraction across the corpus.

Reads Step 1's per-paper has_kinetic_data verdicts and Step 2's
sections.{main,si.X}.json item tags. For each TRUE item, dispatches to
the appropriate extractor (table → enzyme-kinetics-table-extractor;
figure → enzyme-kinetics-figure-extractor; section → enzyme-kinetics-text-extractor).
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


async def _run_figure(item, force, timeout, outline_mod, figure_agent):
    """Phase 2: dispatch one figure to enzyme-kinetics-figure-extractor.

    The figure agent is a singleton passed in so we don't pay
    Agent.from_markdown + Model() init costs per call. Each figure is
    one Task(image_paths=[abs_path]) — the framework embeds the image
    as multimodal content; the agent's pre_run hook injects metadata
    text (caption / parent section / page_idx) into the prompt. The
    LLM emits canonical reaction rows matching the table extractor's
    schema so the normalizer merges figure-derived rows by variant_name.
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

    # Drive the agent's inputs_schema: document_path + item_id. The
    # hook resolves the figure metadata and injects it; image bytes
    # flow through Task.image_paths.
    task_desc = json.dumps({
        "document_path": item["document_path"],
        "item_id": item["item_id"],
    })

    task = Task(
        description=task_desc,
        agent_id="enzyme-kinetics-figure-extractor",
        workspace_dir=str(md_dir),
        image_paths=[str(img_abs)],
    )

    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(figure_agent.process_task(task),
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
        artifact.with_suffix(".raw.log").write_text(content_str, encoding="utf-8")
        return {"item": item, "status": "no_json", "duration_s": elapsed}

    artifact.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return {"item": item, "status": "ok", "duration_s": elapsed, "result": parsed}


def _load_text_payload_module():
    spec = importlib.util.spec_from_file_location(
        "_kx_text_payload",
        BASE / ".claude/agents/enzyme-kinetics-text-extractor/payload.py",
    )
    m = importlib.util.module_from_spec(spec)
    sys.modules["_kx_text_payload"] = m
    spec.loader.exec_module(m)
    return m


_TEXT_PAYLOAD_MOD = None

import re as _re

_NUM_TOKEN_RE = _re.compile(r"\d+(?:\.\d+)?")
_LEADING_VAL_RE = _re.compile(r"^[\s\(]*([\d.,]+(?:\s*[±]\s*[\d.,]+)?)")
_SPACED_DIGITS_RE = _re.compile(r"(\d)\s+(\d)")


def _normalize_for_validator(s: str) -> str:
    """Collapse MinerU's LaTeX-residue spaced-digit rendering.

    MinerU often outputs LaTeX math with whitespace between every digit
    (`1 7 0 0` for 1700, `1 0 ^ 5` for 10⁵). Substring matching fails
    on the spaced form; we iteratively collapse ``\\d\\s+\\d`` until
    stable.
    """
    if not s:
        return s
    prev = None
    while prev != s:
        prev = s
        s = _SPACED_DIGITS_RE.sub(r"\1\2", s)
    return s


def _scientific_mantissas(n: float) -> List[str]:
    """For n=430000, return ['4', '4.3', '4.30', '4.300'] etc.

    Body text often writes large/small kinetic constants in scientific
    notation ("4.3·10⁵") where only the mantissa is the matchable
    numeric token. We generate a few rounded mantissa renderings so
    validator accepts when the body uses any of them.
    """
    if n == 0 or not isinstance(n, (int, float)):
        return []
    try:
        import math
        if abs(n) < 10:
            return []
        exp = int(math.floor(math.log10(abs(n))))
        if exp < 1:
            return []
        mantissa = n / (10**exp)
        out: List[str] = []
        for digits in (0, 1, 2, 3, 4):
            s = f"{mantissa:.{digits}f}"
            out.append(s)
            # Strip trailing zeros after dot, but keep one digit after dot
            if "." in s:
                stripped = s.rstrip("0").rstrip(".")
                if stripped:
                    out.append(stripped)
        return out
    except (ValueError, OverflowError):
        return []


def _extract_numbers_from_any(v) -> List[str]:
    """Recursively collect numeric tokens from nested value shapes.

    Handles the case where the LLM emits ``kinetics.kcat`` as a dict
    (``{"value": 1700, "uncertainty": 230, "unit": "s⁻¹"}``) instead of
    a plain number, and lists of values.
    """
    out: List[str] = []
    if v is None or isinstance(v, bool):
        return out
    if isinstance(v, (int, float)):
        out.append(f"{v:g}")
        if isinstance(v, float):
            out.append(str(v))
            out.append(f"{v:.4g}")
            out.append(f"{v:.3g}")
            out.append(f"{v:.2g}")
        # Scientific-notation mantissa candidates for large numbers.
        out.extend(_scientific_mantissas(float(v)))
        return out
    if isinstance(v, str):
        s = v.strip()
        if s:
            out.append(s)
            m = _LEADING_VAL_RE.match(s)
            if m:
                core = m.group(1).strip()
                if core:
                    out.append(core)
            out.extend(_NUM_TOKEN_RE.findall(s))
        return out
    if isinstance(v, dict):
        for key in ("value", "mean", "best", "central"):
            if key in v:
                out.extend(_extract_numbers_from_any(v[key]))
        if not out:
            for val in v.values():
                out.extend(_extract_numbers_from_any(val))
        return out
    if isinstance(v, list):
        for x in v:
            out.extend(_extract_numbers_from_any(x))
        return out
    out.append(str(v))
    return out


def _stringify_kinetic_value(v) -> List[str]:
    """Render a kinetic value into substring candidates the body might use.

    LLMs misformat in several ways: units glued in ("1700 ± 230 s⁻¹"),
    nested dicts ({"value": 1700, ...}), scientific notation. We try
    every plausible rendering so the validator accepts when ANY matches.
    """
    candidates = set(_extract_numbers_from_any(v))
    return [c for c in candidates if c]


def _validate_text_reactions(reactions: List[Dict[str, Any]], body_text: str) -> tuple:
    """Drop reactions whose kinetic numbers aren't substrings of body_text.

    Returns (kept, dropped) where dropped[i] = {"reaction", "missing_fields"}.
    A reaction passes when EVERY non-null kinetic field's stringified value
    appears as a substring of body_text under at least one candidate
    rendering. Reactions with zero non-null kinetic fields are kept (the
    LLM emitted a row for variant identity / mutations only, which is
    fine).
    """
    body = body_text or ""
    body_norm = _normalize_for_validator(body)
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for r in reactions:
        k = (r.get("kinetics") or {})
        missing: List[str] = []
        any_field = False
        for fld in ("kcat", "Km", "kcat_over_Km"):
            v = k.get(fld)
            if v is None or v == "":
                continue
            any_field = True
            candidates = _stringify_kinetic_value(v)
            # Match against both the raw body and the digit-collapsed
            # version so MinerU's "1 7 0 0" rendering still validates
            # against a candidate like "1700".
            hit = any((c in body) or (_normalize_for_validator(c) in body_norm)
                      for c in candidates if c)
            if not hit:
                missing.append(f"{fld}={v!r} (tried: {candidates})")
        if not any_field:
            kept.append(r)
            continue
        if not missing:
            kept.append(r)
        else:
            dropped.append({"reaction": r, "missing_fields": missing})
    return kept, dropped


async def _run_text(item, force, timeout):
    """Phase 3: dispatch one section to enzyme-kinetics-text-extractor.

    After the LLM returns, the driver re-resolves the section payload
    (deterministically) and runs a literal-substring validator that
    drops any reaction row whose kinetic numbers aren't verbatim in
    body_text. Dropped rows go to <artifact>.dropped.json.
    """
    artifact = _artifact_path(item["paper"], item["source_file"], item["item_id"],
                              "section")
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
        "item_id": item["item_id"],
    })
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "gptase",
            "agent",
            "-n",
            "enzyme-kinetics-text-extractor",
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

    # Post-call validator: drop reaction rows whose kinetic numbers aren't
    # substrings of the body_text we fed in. body_text is re-resolved
    # deterministically from content_list.json (the source of truth).
    global _TEXT_PAYLOAD_MOD
    if _TEXT_PAYLOAD_MOD is None:
        _TEXT_PAYLOAD_MOD = _load_text_payload_module()
    try:
        payload = _TEXT_PAYLOAD_MOD.resolve_section_payload(item["document_path"],
                                                            item["item_id"])
        body = payload.body_text or ""
    except Exception as exc:
        body = ""
        log.warning(
            "text-extractor validator: payload re-resolve failed for "
            "%s/item=%s: %s", item["paper"], item["item_id"], exc)

    reactions = parsed.get("reactions") or []
    kept, dropped = _validate_text_reactions(reactions, body)
    if dropped:
        artifact.with_suffix(".dropped.json").write_text(
            json.dumps(
                {
                    "item_id": item["item_id"],
                    "n_dropped": len(dropped),
                    "dropped": dropped,
                    "body_chars": len(body),
                },
                indent=2,
                ensure_ascii=False),
            encoding="utf-8",
        )
    parsed["reactions"] = kept
    parsed["validator_dropped"] = len(dropped)

    artifact.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return {"item": item, "status": "ok", "duration_s": elapsed, "result": parsed}


# ---------------------------------------------------------------------------
# Per-paper aggregation + normalizer call
# ---------------------------------------------------------------------------


def _figure_variant_names(results: List[Dict[str, Any]]) -> set:
    """All variant_names appearing in successful figure-extractor reactions.

    Figure captions rarely carry footnote letters — vision-derived names are
    a high-trust canonical roster against which we can validate table names.
    """
    names: set = set()
    for r in results:
        if r["item"]["kind"] != "figure":
            continue
        if r["status"] not in ("ok", "cached"):
            continue
        for rx in (r.get("result") or {}).get("reactions") or []:
            n = (rx.get("variant_name") or "").strip()
            if n:
                names.add(n)
    return names


def _build_normalizer_input(
    paper: str,
    results: List[Dict[str, Any]],
    outline_mod,
) -> Dict[str, Any]:
    """Aggregate per-call extractions into the normalizer's expected shape.
    The ``figure_variant_names`` field carries the figure-extractor's variant
    roster so the normalizer can do vision-confirmed footnote-letter dedup
    against ALL row sources (text / vision / html_main / html_si).
    """
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

    figure_names = sorted(_figure_variant_names(results))

    for r in results:
        if r["status"] not in ("ok", "cached"):
            continue
        kind = r["item"]["kind"]
        result = r["result"]
        if kind in ("table", "section", "figure"):
            # All three extractors now emit canonical reactions[] +
            # protein_sequences[]. Figure-extractor also emits
            # figure_analysis (audit-only, normalizer ignores).
            text_extraction_data.append({
                "reactions":
                result.get("reactions", []),
                "protein_sequences":
                result.get("protein_sequences", []),
            })

    inputs: Dict[str, Any] = {
        "text_extraction_data": text_extraction_data,
        "vision_extraction_data": vision_extraction_data,
        "document_path": main_doc_path or "",
        "figure_variant_names": figure_names,
    }
    if si_doc_paths:
        # Normalizer takes a single si_document_path; if multiple SIs, use the first
        # and add the rest into text via separate replicas (already in
        # text_extraction_data above).
        inputs["si_document_path"] = si_doc_paths[0]
    return inputs


def _aggregate_paper_sequences(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect protein_sequences[] from every (table | section | figure) call,
    deduplicate by (design_name, sequence) so duplicates from text + table
    paths collapse, preserve all source-attribution metadata."""
    by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in results:
        if r["status"] not in ("ok", "cached"):
            continue
        result = r.get("result") or {}
        seqs = result.get("protein_sequences") or []
        for s in seqs:
            seq_text = (s.get("sequence") or "").strip()
            name = (s.get("design_name") or "").strip()
            if not seq_text:
                continue
            key = (name, seq_text)
            entry = by_key.get(key)
            source = {
                "kind": r["item"]["kind"],
                "source_file": r["item"]["source_file"],
                "item_id": r["item"]["item_id"],
            }
            if entry is None:
                by_key[key] = {
                    "design_name": name or None,
                    "sequence": seq_text,
                    "length": len(seq_text),
                    "scaffold_pdb_id": s.get("scaffold_pdb_id"),
                    "num_design_mutations": s.get("num_design_mutations"),
                    "sources": [source],
                }
            else:
                # Merge — keep first scaffold/mutations, accumulate sources.
                entry["sources"].append(source)
                if not entry.get("scaffold_pdb_id") and s.get("scaffold_pdb_id"):
                    entry["scaffold_pdb_id"] = s.get("scaffold_pdb_id")
    return sorted(by_key.values(), key=lambda e: (e["design_name"] or "", -e["length"]))


def _per_paper_output(
    paper: str,
    results: List[Dict[str, Any]],
    normalizer_input: Dict[str, Any],
    normalized: Dict[str, Any],
    elapsed_s: float,
    vision_dedup_audit: Optional[List[Dict[str, Any]]] = None,
    unresolved_footnote_candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
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

    paper_sequences = _aggregate_paper_sequences(results)

    return {
        "paper_id":
        paper,
        "main_document_path":
        normalizer_input.get("document_path"),
        "si_document_paths": ([normalizer_input["si_document_path"]]
                              if normalizer_input.get("si_document_path") else []),
        "paper_sequences":
        paper_sequences,
        "vision_dedup_audit":
        vision_dedup_audit or [],
        "unresolved_footnote_candidates":
        unresolved_footnote_candidates or [],
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
            "n_paper_sequences":
            len(paper_sequences),
            "n_vision_dedup":
            len(vision_dedup_audit or []),
            "n_unresolved_footnote_candidates":
            len(unresolved_footnote_candidates or []),
            "elapsed_s":
            elapsed_s,
        },
    }


# ---------------------------------------------------------------------------
# Step 5 — Flatten kinetics.json into a per-variant CSV
# ---------------------------------------------------------------------------

CSV_FIELDS: List[str] = [
    "paper_id",
    "variant_name",
    "enzyme_name",
    "aliases",
    # Mutation info
    "canonical_mutations",
    "num_canonical_mutations",
    # Sequence info — prefers paper-asserted, falls back to PDB-reconstructed
    "sequence",
    "sequence_source",
    "sequence_length",
    "scaffold_pdb_id",
    # Reaction
    "reaction_name",
    "substrates",
    "products",
    # Kinetics
    "kcat",
    "kcat_unit",
    "Km",
    "Km_unit",
    "kcat_over_Km",
    "kcat_over_Km_unit",
    "Tm",
    "Tm_unit",
    # Provenance
    "normalization_status",
    "n_issues",
    "evidence_sources",
]


def _coerce_str_list(values: Any) -> List[str]:
    """Normalize a substrate/product list to strings.

    Different extractors emit different shapes — sometimes plain strings,
    sometimes ``{"name": ..., "smiles": ...}`` dicts. Pick the most
    descriptive textual field per item.
    """
    out: List[str] = []
    if not values:
        return out
    if not isinstance(values, list):
        values = [values]
    for v in values:
        if isinstance(v, str):
            if v.strip():
                out.append(v.strip())
        elif isinstance(v, dict):
            for key in ("name", "compound", "label", "value", "id"):
                val = v.get(key)
                if isinstance(val, str) and val.strip():
                    out.append(val.strip())
                    break
            else:
                out.append(json.dumps(v, ensure_ascii=False))
        elif v is not None:
            out.append(str(v))
    return out


def _index_paper_sequences(paper_sequences: List[Dict[str, Any]]) -> Dict[str, str]:
    """Index paper_sequences by case-insensitive design_name → sequence."""
    by_name: Dict[str, str] = {}
    for entry in paper_sequences or []:
        name = (entry.get("design_name") or "").strip()
        seq = (entry.get("sequence") or "").strip()
        if name and seq:
            by_name.setdefault(name.lower(), seq)
    return by_name


def _pick_sequence(variant: Dict[str, Any],
                   paper_seq_index: Dict[str, str]) -> Tuple[str, str]:
    """Choose the best sequence and tag its source.

    Priority: paper-asserted (verbatim from paper) > normalizer-reconstructed
    via PDB API + apply_mutations > scaffold-only > none.
    """
    name = (variant.get("variant_name") or "").strip().lower()
    paper_seq = paper_seq_index.get(name)
    if paper_seq:
        return paper_seq, "paper_asserted"
    var_seq = (variant.get("variant_sequence") or "").strip()
    if var_seq:
        return var_seq, "pdb_reconstructed"
    full_seq = (variant.get("full_sequence") or "").strip()
    if full_seq:
        return full_seq, "scaffold_only"
    return "", "none"


def _flatten_variant_to_csv_row(paper: str, variant: Dict[str, Any],
                                paper_seq_index: Dict[str, str]) -> Dict[str, Any]:
    """Project one normalized_variant into a single CSV row."""
    kinetics = variant.get("kinetics") or {}
    reaction = variant.get("reaction") or {}
    sequence, sequence_source = _pick_sequence(variant, paper_seq_index)

    canonical_mutations = variant.get("canonical_mutations") or []
    aliases = variant.get("aliases") or []
    evidence_sources = [
        s.get("source_id", "")
        for s in (variant.get("evidence") or {}).get("sources", [])
        if isinstance(s, dict) and s.get("source_id")
    ]

    return {
        "paper_id":
        paper,
        "variant_name":
        variant.get("variant_name") or "",
        "enzyme_name":
        variant.get("enzyme_name") or "",
        "aliases":
        "|".join(aliases),
        "canonical_mutations":
        "|".join(canonical_mutations),
        "num_canonical_mutations":
        len(canonical_mutations),
        "sequence":
        sequence,
        "sequence_source":
        sequence_source,
        "sequence_length":
        len(sequence) if sequence else 0,
        "scaffold_pdb_id":
        variant.get("scaffold_pdb_id") or "",
        "reaction_name":
        reaction.get("reaction_name") or "",
        "substrates":
        "|".join(_coerce_str_list(reaction.get("substrates"))),
        "products":
        "|".join(_coerce_str_list(reaction.get("products"))),
        "kcat":
        kinetics.get("kcat") if kinetics.get("kcat") is not None else "",
        "kcat_unit":
        kinetics.get("kcat_unit") or "",
        "Km":
        kinetics.get("Km") if kinetics.get("Km") is not None else "",
        "Km_unit":
        kinetics.get("Km_unit") or "",
        "kcat_over_Km":
        kinetics.get("kcat_over_Km")
        if kinetics.get("kcat_over_Km") is not None else "",
        "kcat_over_Km_unit":
        kinetics.get("kcat_over_Km_unit") or "",
        "Tm":
        kinetics.get("Tm") if kinetics.get("Tm") is not None else "",
        "Tm_unit":
        kinetics.get("Tm_unit") or "",
        "normalization_status":
        variant.get("normalization_status") or "",
        "n_issues":
        len(variant.get("issues") or []),
        "evidence_sources":
        "|".join(evidence_sources),
    }


def _flatten_paper_to_csv_rows(paper_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the entire kinetics.json output into per-variant CSV rows."""
    paper_id = paper_output["paper_id"]
    paper_seq_index = _index_paper_sequences(paper_output.get("paper_sequences") or [])
    variants = paper_output.get("normalized", {}).get("normalized_variants") or []
    return [_flatten_variant_to_csv_row(paper_id, v, paper_seq_index) for v in variants]


def _write_paper_variants_csv(paper: str, rows: List[Dict[str, Any]]) -> Path:
    """Write per-paper kinetics.csv. Always overwrites."""
    out_path = EXTR / paper / "kinetics.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return out_path


def _write_corpus_variants_csv(all_rows: List[Dict[str, Any]]) -> Path:
    """Write corpus-wide aggregator at papers/extractions/_summary.kinetics_variants.csv."""
    out_path = EXTR / "_summary.kinetics_variants.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_paper(paper: str,
                    args,
                    outline_mod,
                    normalize_fn,
                    sem: asyncio.Semaphore,
                    figure_agent=None) -> Dict[str, Any]:
    paper_t0 = time.monotonic()
    items = enumerate_items(paper, outline_mod)

    async def _bound(coro):
        async with sem:
            return await coro

    coros = []
    for it in items:
        if it["kind"] == "table":
            coros.append(_bound(_run_table(it, args.force, args.timeout)))
        elif it["kind"] == "figure" and args.enable_figures and figure_agent is not None:
            coros.append(
                _bound(
                    _run_figure(it, args.force, args.timeout, outline_mod,
                                figure_agent)))
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

    vision_dedup_audit = normalized.pop("vision_dedup_audit", []) or []
    unresolved_footnote_candidates = normalized.pop("unresolved_footnote_candidates",
                                                    []) or []

    elapsed = round(time.monotonic() - paper_t0, 1)
    out = _per_paper_output(paper, results, normalizer_input, normalized, elapsed,
                            vision_dedup_audit, unresolved_footnote_candidates)
    out_path = EXTR / paper / "kinetics.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_rows = _flatten_paper_to_csv_rows(out)
    _write_paper_variants_csv(paper, csv_rows)

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
        "csv_rows": csv_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="Only run these paper names")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--force",
                    action="store_true",
                    help="Re-run even when artifact exists")
    ap.add_argument(
        "--enable-figures",
        action="store_true",
        help="Phase 2 — dispatch figures to enzyme-kinetics-figure-extractor")
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
    figure_agent = None
    if args.enable_figures:
        from gptase.agents.base import Agent
        from gptase.models.model import Model
        vision_model = Model()
        figure_agent = Agent.from_markdown("enzyme-kinetics-figure-extractor",
                                           model_manager=vision_model)
        print(
            f"  enzyme-kinetics-figure-extractor loaded; "
            f"model={figure_agent.model_name}",
            flush=True)

    async def _run_all() -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(args.workers)
        return await asyncio.gather(*[
            run_paper(
                p, args, outline_mod, normalize_fn, sem, figure_agent=figure_agent)
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
        # Drop csv_rows before writing — the summary csv has its own narrow schema.
        w.writerows([{k: v for k, v in r.items() if k != "csv_rows"} for r in rows])

    # Step 5 — corpus-wide flat variant table (one row per normalized variant).
    all_csv_rows: List[Dict[str, Any]] = []
    for r in rows:
        all_csv_rows.extend(r.get("csv_rows", []))
    variants_csv = _write_corpus_variants_csv(all_csv_rows)

    n_ok = sum(r["n_ok"] for r in rows)
    n_fail = sum(r["n_fail"] for r in rows)
    n_var = sum(r["n_variants"] for r in rows)
    print(
        f"\n=== Done in {total}s — {len(rows)} papers, {n_ok} calls ok, "
        f"{n_fail} failed, {n_var} normalized variants. ===",
        flush=True,
    )
    print(f"    per-paper metadata: {summary}", flush=True)
    print(f"    per-variant table:  {variants_csv} ({len(all_csv_rows)} rows)",
          flush=True)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
