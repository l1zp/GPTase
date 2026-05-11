"""expand_citations.py — Stage 2: 1-hop citation graph expansion.

Given a seed CSV (name,doi) and a topic spec, find Kemp/topic-relevant
neighbors that the seeds cite (outgoing) or that cite the seeds (incoming).
Score each candidate by:
  1. title regex match against positive_title_terms, OR
  2. multi-seed-overlap >= 3 AND abstract contains a positive term

Output: TSV with columns
    doi  first_author  year  title  overlap  abstract_has_topic  source

where source ∈ {"refs", "cites"}.

Usage:
    python expand_citations.py --csv <seed.csv> --topic <spec.json> --out <out.tsv>

The script reuses the cache directory ./citation_cache/ so reruns are fast.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

OPENALEX = "https://api.openalex.org/works"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "paper-collection-sweep"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return (doi.lower().replace("https://doi.org/", "").replace("http://doi.org/",
                                                                "").strip())


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    t = title.lower()
    for d in "‐–—":
        t = t.replace(d, "-")
    return t


def reconstruct_abstract(work: dict) -> str:
    idx = work.get("abstract_inverted_index") or {}
    return " ".join(idx.keys()).lower()


def is_garbage_doi(doi: str, exclude_prefixes: list[str]) -> bool:
    if any(doi.startswith(p) for p in exclude_prefixes):
        return True
    if re.search(r"\.s\d{3}$", doi):
        return True
    return False


def kemp_relevant(work: dict, seed_wids: set[str], spec: dict) -> bool:
    doi = normalize_doi(work.get("doi"))
    if not doi or is_garbage_doi(doi, spec.get("exclude_doi_prefixes") or []):
        return False
    title = work.get("title") or ""
    norm_t = normalize_title(title)
    for term in spec.get("exclude_title_terms") or []:
        if term.lower() in norm_t:
            return False
    for term in spec.get("positive_title_terms") or []:
        if term.lower() in norm_t:
            return True
    refs = work.get("referenced_works") or []
    overlap = sum(1 for r in refs
                  if r.replace("https://openalex.org/", "") in seed_wids)
    abs_text = reconstruct_abstract(work)
    if overlap >= 3 and any(t.lower() in abs_text
                            for t in (spec.get("positive_title_terms") or [])):
        return True
    return False


def overlap_count(work: dict, seed_wids: set[str]) -> int:
    refs = work.get("referenced_works") or []
    return sum(1 for r in refs if r.replace("https://openalex.org/", "") in seed_wids)


def abs_has_topic(work: dict, spec: dict) -> bool:
    abs_text = reconstruct_abstract(work)
    return any(t.lower() in abs_text for t in (spec.get("positive_title_terms") or []))


def resolve_dois_to_wids(dois: list[str]) -> dict[str, str]:
    """Batch DOI -> W-ID via OpenAlex filter=doi:<list>."""
    out: dict[str, str] = {}
    for i in range(0, len(dois), 25):
        batch = dois[i:i + 25]
        flt = urllib.parse.quote("|".join(batch), safe="/.-")
        url = f"{OPENALEX}?filter=doi:{flt}&per-page=200&select=id,doi"
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  [warn] resolve batch failed: {e}", file=sys.stderr)
            continue
        for w in data.get("results", []) or []:
            doi = normalize_doi(w.get("doi"))
            wid = (w.get("id") or "").replace("https://openalex.org/", "")
            if doi and wid:
                out[doi] = wid
        time.sleep(0.05)
    return out


def fetch_works_by_wid(wids: list[str]) -> list[dict]:
    """Batch fetch full metadata by W-ID."""
    out: list[dict] = []
    for i in range(0, len(wids), 50):
        batch = wids[i:i + 50]
        ids = "|".join(batch)
        url = (
            f"{OPENALEX}?filter=ids.openalex:{ids}&per-page=200"
            f"&select=id,doi,title,publication_year,authorships,referenced_works,abstract_inverted_index"
        )
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  [warn] fetch batch failed: {e}", file=sys.stderr)
            continue
        out.extend(data.get("results", []) or [])
        time.sleep(0.05)
    return out


def fetch_citing_papers(seed_wids: list[str], spec: dict) -> list[dict]:
    """For each set of seeds + each query, fetch papers citing seeds & matching query."""
    all_works: dict[str, dict] = {}
    queries = spec.get("queries") or ["Kemp+eliminase"]
    for i in range(0, len(seed_wids), 25):
        batch = seed_wids[i:i + 25]
        cites_filter = "|".join(batch)
        for q in queries:
            for page in (1, 2, 3):
                url = (
                    f"{OPENALEX}?filter=cites:{cites_filter}&search={q}"
                    f"&per-page=200&page={page}"
                    f"&select=id,doi,title,publication_year,authorships,referenced_works,abstract_inverted_index"
                )
                try:
                    data = fetch_json(url)
                except Exception as e:
                    print(f"  [warn] cites query failed: {e}", file=sys.stderr)
                    continue
                results = data.get("results", []) or []
                for w in results:
                    wid = (w.get("id") or "").replace("https://openalex.org/", "")
                    if wid:
                        all_works[wid] = w
                if len(results) < 200:
                    break
                time.sleep(0.05)
    return list(all_works.values())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="Seed CSV (name,doi)")
    p.add_argument("--topic", required=True, help="Topic spec JSON")
    p.add_argument("--out", required=True, help="Output TSV")
    args = p.parse_args()

    spec = json.loads(Path(args.topic).read_text())

    # Load seed DOIs (CSV may have extra tracking columns beyond name,doi)
    import csv as _csv
    seed_dois: list[str] = []
    with Path(args.csv).open(newline="") as f:
        for row in _csv.DictReader(f):
            doi = normalize_doi((row.get("doi") or "").strip())
            if doi:
                seed_dois.append(doi)
    print(f"Seeds: {len(seed_dois)}", file=sys.stderr)

    # Resolve to W-IDs
    doi_to_wid = resolve_dois_to_wids(seed_dois)
    seed_wids = set(doi_to_wid.values())
    print(f"Seed W-IDs: {len(seed_wids)}", file=sys.stderr)

    # Fetch full seed metadata (need referenced_works)
    seed_works = fetch_works_by_wid(list(seed_wids))
    print(f"Seed works fetched: {len(seed_works)}", file=sys.stderr)

    # Outgoing references
    ref_wids: set[str] = set()
    for w in seed_works:
        for r in w.get("referenced_works") or []:
            wid = r.replace("https://openalex.org/", "")
            if wid not in seed_wids:
                ref_wids.add(wid)
    print(f"Outgoing refs (deduped): {len(ref_wids)}", file=sys.stderr)
    ref_works = fetch_works_by_wid(list(ref_wids))

    # Incoming citations (filtered by topic queries)
    cite_works = fetch_citing_papers(list(seed_wids), spec)
    print(f"Incoming cites (filtered by query): {len(cite_works)}", file=sys.stderr)

    # Combine, dedupe, score
    all_candidates: dict[str, tuple[dict, str]] = {}
    for w in ref_works:
        wid = (w.get("id") or "").replace("https://openalex.org/", "")
        if wid and wid not in seed_wids:
            all_candidates[wid] = (w, "refs")
    for w in cite_works:
        wid = (w.get("id") or "").replace("https://openalex.org/", "")
        if wid and wid not in seed_wids and wid not in all_candidates:
            all_candidates[wid] = (w, "cites")

    # Filter and emit
    seed_dois_set = {d for d in seed_dois}
    rows = []
    for wid, (w, source) in all_candidates.items():
        doi = normalize_doi(w.get("doi"))
        if not doi or doi in seed_dois_set:
            continue
        if not kemp_relevant(w, seed_wids, spec):
            continue
        rows.append((
            doi,
            (w.get("authorships") or [{}])[0].get("author",
                                                  {}).get("display_name", "Unknown"),
            str(w.get("publication_year") or 0),
            w.get("title") or "",
            str(overlap_count(w, seed_wids)),
            str(abs_has_topic(w, spec)).lower(),
            source,
        ))
    rows.sort(key=lambda r: (r[2], r[0]))

    out_path = Path(args.out)
    with out_path.open("w") as f:
        for r in rows:
            f.write("\t".join(r) + "\n")
    print(f"\nWrote {len(rows)} candidates to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
