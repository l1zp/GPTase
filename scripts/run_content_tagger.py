"""Step 2 driver: dispatch enzyme-kinetics-content-tagger across the corpus.

Walks ``screener.json`` for ``has_kinetic_data: true`` papers, then for
each TRUE paper invokes the content-tagger on its main markdown and
every SI markdown. Writes ``sections.<source>.json`` artifacts under
``papers/extractions/<paper>/`` exactly as the original (lost) Step 2
driver did, so downstream Step 3 / 3.5 consumers don't need to change.

This script is idempotent: skip when ``sections.<source>.json`` already
exists, unless ``--force`` is passed. Use ``--only <paper>`` to scope.

Typical invocation after a tagger prompt change:
    python scripts/run_content_tagger.py --force --only bhattacharya_2022_nmr_guided_directed_evolution
    # validate output, then full corpus:
    python scripts/run_content_tagger.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.WARNING,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE = Path("/Users/ryanxu/CodeBase/GPTase")
EXTR = BASE / "papers/extractions"
SRC = BASE / "papers/markdowns"
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = 360


def _extract_final_json(stdout: str) -> Optional[Dict[str, Any]]:
    """Find the last balanced top-level JSON object in stdout."""
    depth = 0
    in_str = False
    esc = False
    start = -1
    last: Optional[Dict[str, Any]] = None
    for i, c in enumerate(stdout):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start != -1:
                blob = stdout[start:i + 1]
                try:
                    obj = json.loads(blob)
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict) and "items" in obj:
                    last = obj
                start = -1
    return last


def _true_papers() -> List[str]:
    """Papers where screener.json reports has_kinetic_data=true."""
    out: List[str] = []
    for p in sorted(EXTR.iterdir()):
        if not p.is_dir():
            continue
        screener = p / "screener.json"
        if not screener.is_file():
            continue
        try:
            data = json.loads(screener.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("has_kinetic_data") is True:
            out.append(p.name)
    return out


def _resolve_main_md(paper: str) -> Optional[Path]:
    paper_dir = SRC / paper / "main"
    if not paper_dir.is_dir():
        return None
    for cand in (paper_dir / "full.md", paper_dir / "main.md"):
        if cand.is_file():
            return cand
    return None


def _resolve_si_mds(paper: str) -> List[Tuple[str, Path]]:
    """List (si_filename, path) for every SI markdown found.

    si_filename is the SI subdirectory name (e.g. "SI_jp9069114_si_001"),
    matching what the tagger emits in its output's `si_filename` field
    and what downstream Step 3 / 3.5 consumers expect via the
    sections.si.<si_filename>.json naming convention.
    """
    si_root = SRC / paper / "SI"
    if not si_root.is_dir():
        return []
    out: List[Tuple[str, Path]] = []
    for si_subdir in sorted(si_root.iterdir()):
        if not si_subdir.is_dir():
            continue
        for cand in (si_subdir / "full.md", si_subdir / "main.md",
                     si_subdir / f"{si_subdir.name}.md"):
            if cand.is_file():
                out.append((si_subdir.name, cand))
                break
        else:
            # Fallback: first .md anywhere in the SI subdir.
            mds = sorted(si_subdir.rglob("*.md"))
            if mds:
                out.append((si_subdir.name, mds[0]))
    return out


def _artifact_path(paper: str, source: str, si_filename: str) -> Path:
    if source == "main":
        return EXTR / paper / "sections.main.json"
    return EXTR / paper / f"sections.si.{si_filename}.json"


async def _run_one(paper: str, md_path: Path, source: str, si_filename: str,
                   force: bool, timeout: int) -> Dict[str, Any]:
    artifact = _artifact_path(paper, source, si_filename)
    if artifact.exists() and not force:
        return {
            "paper": paper,
            "source": source,
            "si_filename": si_filename,
            "status": "cached"
        }

    desc = json.dumps({"document_path": str(md_path)})
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "gptase",
            "agent",
            "-n",
            "enzyme-kinetics-content-tagger",
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
            "paper": paper,
            "source": source,
            "si_filename": si_filename,
            "status": "timeout",
            "duration_s": round(time.monotonic() - t0, 1)
        }

    elapsed = round(time.monotonic() - t0, 1)
    parsed = _extract_final_json(stdout_b.decode("utf-8", errors="replace"))
    if parsed is None:
        artifact.with_suffix(".raw.log").write_text(
            stdout_b.decode("utf-8", errors="replace") + "\n[STDERR]\n"
            + stderr_b.decode("utf-8", errors="replace"),
            encoding="utf-8",
        )
        return {
            "paper": paper,
            "source": source,
            "si_filename": si_filename,
            "status": "no_json",
            "duration_s": elapsed
        }

    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    n_items = len(parsed.get("items") or [])
    n_kin = sum(1 for it in (parsed.get("items") or []) if it.get("is_relevant"))
    n_scaffold = sum(1 for it in (parsed.get("items") or [])
                     if it.get("is_scaffold_related"))
    return {
        "paper": paper,
        "source": source,
        "si_filename": si_filename,
        "status": "ok",
        "duration_s": elapsed,
        "n_items": n_items,
        "n_kin_relevant": n_kin,
        "n_scaffold_related": n_scaffold,
    }


async def _run_paper(paper: str, force: bool, timeout: int,
                     sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    main_md = _resolve_main_md(paper)
    tasks: List = []
    if main_md is not None:
        tasks.append(_run_one(paper, main_md, "main", "", force, timeout))
    for si_name, si_md in _resolve_si_mds(paper):
        tasks.append(_run_one(paper, si_md, "si", si_name, force, timeout))

    async def _bound(coro):
        async with sem:
            return await coro

    return await asyncio.gather(*[_bound(t) for t in tasks])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="Only run these paper names")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--force",
                    action="store_true",
                    help="Re-run even when sections.<source>.json exists")
    ap.add_argument("--skip-preflight",
                    action="store_true",
                    help="Skip the LLM endpoint health check before launching")
    args = ap.parse_args()

    if not args.skip_preflight:
        # Same preflight as scripts/run_kinetics_extraction.py — fail fast on
        # auth/network issues instead of stalling on conda-buffered retries.
        from gptase.models.model import Model

        async def _probe() -> int:
            m = Model()
            try:
                r = await m.health_check(timeout_s=15)
            finally:
                await m.shutdown()
            marker = "[OK]" if r["ok"] else "[FAIL]"
            print(
                f"{marker} preflight: status={r['status']} model={r['model_name']} "
                f"latency={r['latency_s']}s " +
                (f"({r['error']})" if r["error"] else ""),
                flush=True,
            )
            return 0 if r["ok"] else 1

        if asyncio.run(_probe()) != 0:
            print(
                "Aborting tagger: LLM endpoint health check failed. "
                "Re-run with --skip-preflight to bypass.",
                flush=True,
            )
            return 2

    papers = _true_papers()
    if args.only:
        papers = [p for p in papers if p in set(args.only)]
    print(f"Step 2 driver: {len(papers)} TRUE papers (workers={args.workers})\n",
          flush=True)

    async def _run_all() -> List[List[Dict[str, Any]]]:
        sem = asyncio.Semaphore(args.workers)
        return await asyncio.gather(
            *[_run_paper(p, args.force, args.timeout, sem) for p in papers])

    t_start = time.monotonic()
    results = asyncio.run(_run_all())
    total = round(time.monotonic() - t_start, 1)

    flat = [r for paper_results in results for r in paper_results]
    n_ok = sum(1 for r in flat if r["status"] == "ok")
    n_cached = sum(1 for r in flat if r["status"] == "cached")
    n_fail = sum(1 for r in flat if r["status"] not in ("ok", "cached"))
    n_scaffold = sum(
        r.get("n_scaffold_related", 0) for r in flat if r["status"] == "ok")
    n_kin = sum(r.get("n_kin_relevant", 0) for r in flat if r["status"] == "ok")

    # Print per-paper summary, sorted by paper name.
    by_paper: Dict[str, List[Dict[str, Any]]] = {}
    for r in flat:
        by_paper.setdefault(r["paper"], []).append(r)
    for paper, rs in sorted(by_paper.items()):
        kin = sum(r.get("n_kin_relevant", 0) for r in rs if r["status"] == "ok")
        sc = sum(r.get("n_scaffold_related", 0) for r in rs if r["status"] == "ok")
        bad = [r for r in rs if r["status"] not in ("ok", "cached")]
        bad_s = f" [FAIL: {[r['status'] for r in bad]}]" if bad else ""
        print(f"  {paper[:55]:55s} kin={kin:>3} scaffold={sc:>3}{bad_s}", flush=True)

    print(
        f"\n=== Done in {total}s — {n_ok} ok, {n_cached} cached, "
        f"{n_fail} failed. Total kinetic-tagged: {n_kin}, scaffold-tagged: "
        f"{n_scaffold}. ===",
        flush=True)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
