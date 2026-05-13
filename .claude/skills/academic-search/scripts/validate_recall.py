"""validate_recall.py — Stage 4: cold-start recall validation.

Empties the seed set, then runs the full backward-sweep algorithm starting
from start_year, tracking which CSV DOIs are recovered and via which path
(direct keyword search vs reference-pool expansion).

Output: stdout report including recall %, per-year breakdown, list of
missed DOIs.

Usage:
    python validate_recall.py \
        --csv <existing_csv> --topic <spec.json> \
        --start-year 2025 --end-year 1997
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from expand_citations import fetch_json  # type: ignore[import-not-found]
from expand_citations import fetch_works_by_wid
from expand_citations import is_garbage_doi
from expand_citations import kemp_relevant
from expand_citations import normalize_doi
from expand_citations import normalize_title
from expand_citations import OPENALEX


def search_year(year: int, spec: dict) -> dict[str, dict]:
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
            if doi and w.get("title") is not None:
                out[doi] = w
        time.sleep(0.05)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--start-year", type=int, required=True)
    p.add_argument("--end-year", type=int, default=1997)
    args = p.parse_args()

    spec = json.loads(Path(args.topic).read_text())

    # Target set (CSV may have extra tracking columns beyond name,doi)
    import csv as _csv
    csv_dois: set[str] = set()
    with Path(args.csv).open(newline="") as f:
        for row in _csv.DictReader(f):
            doi = (row.get("doi") or "").strip().lower()
            if doi:
                csv_dois.add(doi)
    print(f"Target CSV DOIs: {len(csv_dois)}")

    # Cold-start state
    seed_works: dict[str, dict] = {}
    seed_wids: set[str] = set()
    refs_fetched: dict[str, dict] = {}
    recovered: dict[str, tuple[int, str]] = {}  # doi -> (year, source)

    for year in range(args.start_year, args.end_year - 1, -1):
        added_direct = 0
        added_ref = 0
        recovered_now: list[tuple[str, str]] = []

        # 1) Direct search
        direct = search_year(year, spec)
        for doi, w in direct.items():
            if doi in seed_works:
                continue
            in_csv = doi in csv_dois
            if in_csv or kemp_relevant(w, seed_wids, spec):
                seed_works[doi] = w
                wid = (w.get("id") or "").replace("https://openalex.org/", "")
                if wid:
                    seed_wids.add(wid)
                added_direct += 1
                if in_csv and doi not in recovered:
                    recovered[doi] = (year, "direct")
                    recovered_now.append((doi, "direct"))

        # 2) Refresh refs cache for newly added seeds
        pending: set[str] = set()
        for w in seed_works.values():
            for r in w.get("referenced_works") or []:
                wid = r.replace("https://openalex.org/", "")
                if wid not in refs_fetched and wid not in seed_wids:
                    pending.add(wid)
        if pending:
            for w in fetch_works_by_wid(list(pending)):
                wid = (w.get("id") or "").replace("https://openalex.org/", "")
                if wid:
                    refs_fetched[wid] = w

        # 3) Reference-pool: items with publication_year == this year
        for wid, w in refs_fetched.items():
            if w.get("publication_year") != year:
                continue
            doi = normalize_doi(w.get("doi"))
            if not doi or doi in seed_works:
                continue
            in_csv = doi in csv_dois
            if in_csv or kemp_relevant(w, seed_wids, spec):
                seed_works[doi] = w
                seed_wids.add(wid)
                added_ref += 1
                if in_csv and doi not in recovered:
                    recovered[doi] = (year, "ref")
                    recovered_now.append((doi, "ref"))

        print(f"Year {year}: +direct={added_direct} +ref={added_ref} | "
              f"recovered={len(recovered)}/{len(csv_dois)} "
              f"(seeds={len(seed_works)} ref-cache={len(refs_fetched)})")
        for doi, source in recovered_now:
            print(f"    [{source}] {doi}")

    # Final report
    print("\n=== FINAL ===")
    missed = csv_dois - set(recovered.keys())
    print(
        f"Recovered: {len(recovered)}/{len(csv_dois)}  ({100*len(recovered)/max(1,len(csv_dois)):.1f}%)"
    )
    print(f"Missed:    {len(missed)}")
    if missed:
        print("\nMissed DOIs:")
        for doi in sorted(missed):
            print(f"  {doi}")
    via_direct = sum(1 for v in recovered.values() if v[1] == "direct")
    via_ref = sum(1 for v in recovered.values() if v[1] == "ref")
    print(f"\nVia direct search:     {via_direct}")
    print(f"Via reference pool:    {via_ref}")


if __name__ == "__main__":
    main()
