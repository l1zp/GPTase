"""backward_sweep.py — Stage 3: year-by-year backward sweep.

For each year Y from start_year down to end_year:
  1. Direct keyword search for year Y (multi-query)
  2. From accumulated seeds' referenced_works, filter to publication_year == Y
  3. Apply topic filter, dedupe vs current CSV
  4. Append new entries; treat them as seeds for year Y-1

Usage:
    python backward_sweep.py \
        --csv <seed.csv> --topic <spec.json> \
        --start-year 2025 --end-year 2008 \
        --out <updated.csv>

Reuses helpers in expand_citations.py via direct import.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

# Reuse helpers
sys.path.insert(0, str(Path(__file__).parent))
from expand_citations import abs_has_topic  # type: ignore[import-not-found]
from expand_citations import fetch_json
from expand_citations import fetch_works_by_wid
from expand_citations import is_garbage_doi
from expand_citations import kemp_relevant
from expand_citations import normalize_doi
from expand_citations import normalize_title
from expand_citations import OPENALEX
from expand_citations import overlap_count
from expand_citations import resolve_dois_to_wids


def search_year(year: int, spec: dict) -> dict[str, dict]:
    """Direct keyword search restricted to year, deduped by DOI."""
    out: dict[str, dict] = {}
    for q in spec.get("queries") or []:
        url = (
            f"{OPENALEX}?search={q}"
            f"&filter=from_publication_date:{year}-01-01,to_publication_date:{year}-12-31"
            f"&per-page=100"
            f"&select=id,doi,title,publication_year,authorships,referenced_works,abstract_inverted_index"
        )
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  [warn] search({q}, {year}) failed: {e}", file=sys.stderr)
            continue
        for w in data.get("results", []) or []:
            doi = normalize_doi(w.get("doi"))
            if doi:
                out[doi] = w
        time.sleep(0.05)
    return out


def name_from_work(work: dict) -> str:
    """Construct firstauthor_year_keywords name."""
    authors = work.get("authorships") or []
    if authors:
        full = authors[0].get("author", {}).get("display_name") or "unknown"
    else:
        full = "unknown"
    parts = full.lower().split()
    last = parts[-1] if parts else "unknown"
    last = "".join(c for c in last.replace("-", "_")
                   if c.isascii() and (c.isalnum() or c == "_"))
    year = work.get("publication_year") or 0
    title = (work.get("title") or "").lower()
    title = "".join(c if c.isalnum() or c.isspace() else " " for c in title)
    stop = {"the", "a", "of", "for", "in", "on", "with", "and", "to", "by", "an"}
    words = [w for w in title.split() if w and w not in stop and w.isascii()]
    keywords = "_".join(words[:3]) if words else "paper"
    return f"{last}_{year}_{keywords}"[:80]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--start-year", type=int, required=True)
    p.add_argument("--end-year", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--dry-run",
                   action="store_true",
                   help="Don't append to CSV; just print candidates")
    args = p.parse_args()

    spec = json.loads(Path(args.topic).read_text())
    csv_path = Path(args.csv)
    out_path = Path(args.out)

    # Load existing CSV (may have extra tracking columns beyond name,doi)
    import csv as _csv
    csv_lines = csv_path.read_text().splitlines()
    header = csv_lines[0] if csv_lines else "name,doi"
    existing_rows = [line for line in csv_lines[1:] if "," in line]
    known_dois: set[str] = set()
    with csv_path.open(newline="") as f:
        for row in _csv.DictReader(f):
            doi = (row.get("doi") or "").strip().lower()
            if doi:
                known_dois.add(doi)
    print(f"Loaded CSV: {len(existing_rows)} rows", file=sys.stderr)

    # Resolve seeds to W-IDs and fetch metadata
    doi_to_wid = resolve_dois_to_wids(list(known_dois))
    seed_wids = set(doi_to_wid.values())
    seed_works_by_wid = {
        (w.get("id") or "").replace("https://openalex.org/", ""): w
        for w in fetch_works_by_wid(list(seed_wids))
    }
    print(f"Resolved seed W-IDs: {len(seed_wids)}", file=sys.stderr)

    # Refs cache: wid -> work
    refs_cache: dict[str, dict] = {}

    new_entries: list[tuple[str, str]] = []  # (name, doi)

    years = range(args.start_year, args.end_year - 1, -1)
    for Y in years:
        added_direct = 0
        added_ref = 0

        # Stage 1: direct search
        direct = search_year(Y, spec)
        new_seed_works: list[dict] = []
        for doi, w in direct.items():
            if doi in known_dois:
                # Already in CSV — refresh metadata cache for citation expansion
                wid = (w.get("id") or "").replace("https://openalex.org/", "")
                if wid:
                    seed_works_by_wid[wid] = w
                    seed_wids.add(wid)
                continue
            if not kemp_relevant(w, seed_wids, spec):
                continue
            wid = (w.get("id") or "").replace("https://openalex.org/", "")
            if wid:
                seed_works_by_wid[wid] = w
                seed_wids.add(wid)
            known_dois.add(doi)
            new_entries.append((name_from_work(w), doi))
            new_seed_works.append(w)
            added_direct += 1

        # Stage 2: refresh refs cache from any seed metadata not yet expanded
        pending_wids: set[str] = set()
        for w in seed_works_by_wid.values():
            for r in w.get("referenced_works") or []:
                wid = r.replace("https://openalex.org/", "")
                if wid not in refs_cache and wid not in seed_wids:
                    pending_wids.add(wid)
        if pending_wids:
            new_meta = fetch_works_by_wid(list(pending_wids))
            for w in new_meta:
                wid = (w.get("id") or "").replace("https://openalex.org/", "")
                if wid:
                    refs_cache[wid] = w

        # Stage 2b: from refs_cache, take items with publication_year == Y
        for wid, w in list(refs_cache.items()):
            if w.get("publication_year") != Y:
                continue
            doi = normalize_doi(w.get("doi"))
            if not doi or doi in known_dois:
                continue
            if not kemp_relevant(w, seed_wids, spec):
                continue
            seed_works_by_wid[wid] = w
            seed_wids.add(wid)
            known_dois.add(doi)
            new_entries.append((name_from_work(w), doi))
            added_ref += 1

        print(
            f"Year {Y}: +direct={added_direct} +ref={added_ref} | "
            f"total seeds={len(seed_wids)} refs-cache={len(refs_cache)}",
            file=sys.stderr,
        )

    # Output
    if args.dry_run:
        print(f"\nDRY RUN — would add {len(new_entries)} new entries:")
        for name, doi in new_entries:
            print(f"  {name},{doi}")
        return

    # Append new entries with empty values for any extra tracking columns
    # so the schema stays consistent with the existing rows.
    header_cols = [c.strip() for c in header.split(",")]
    extra_cols = len(header_cols) - 2  # beyond name,doi
    padding = ("," + ",".join([""] * extra_cols)) if extra_cols > 0 else ""
    new_rows = [f"{n},{d}{padding}" for n, d in new_entries]
    all_rows = existing_rows + new_rows
    all_rows.sort(key=lambda r: r.split(",", 1)[0])
    out_path.write_text(header + "\n" + "\n".join(all_rows) + "\n")
    print(f"\nWrote {len(all_rows)} rows to {out_path} (+{len(new_entries)} new)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
