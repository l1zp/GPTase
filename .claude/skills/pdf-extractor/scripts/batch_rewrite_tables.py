"""Apply rewrite_tables_as_images to every MinerU paper dir under a root.

Walks recursively, picking any directory that has BOTH `main.md` and a
`*_content_list.json` sibling. SI subdirectories qualify and are processed.

Usage:
    python batch_rewrite_tables.py <root_dir> [--dry-run]

Aggregate report is printed as JSON on stdout.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

# Local import - this script lives next to rewrite_tables_as_images.py
sys.path.insert(0, str(Path(__file__).parent))
from rewrite_tables_as_images import rewrite  # noqa: E402


def find_paper_dirs(root: Path) -> list[Path]:
    """Yield every dir that has main.md AND a *_content_list.json."""
    dirs = []
    for md in root.rglob("main.md"):
        d = md.parent
        if list(d.glob("*_content_list.json")):
            dirs.append(d)
    return sorted(dirs)


def main():
    if len(sys.argv) < 2:
        print("usage: batch_rewrite_tables.py <root_dir> [--dry-run]")
        sys.exit(1)
    root = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv[2:]

    dirs = find_paper_dirs(root)
    print(f"[INFO] found {len(dirs)} paper dirs under {root}", flush=True)

    summary = {
        "root": str(root),
        "dry_run": dry,
        "dirs_total": len(dirs),
        "tables_total": 0,
        "tables_replaced": 0,
        "tables_html_not_found": 0,
        "dirs_no_tables": 0,
        "dirs_with_warning": [],
        "results": [],
    }

    for i, d in enumerate(dirs, 1):
        rel = d.relative_to(root) if root in d.parents or root == d.parent else d
        try:
            r = rewrite(d, dry_run=dry)
        except Exception as e:
            print(f"[FAIL] {rel}: {e!r}", flush=True)
            summary["dirs_with_warning"].append({
                "dir": str(rel),
                "error": repr(e),
            })
            continue

        summary["tables_total"] += r["tables_total"]
        summary["tables_replaced"] += r["replaced"]
        summary["tables_html_not_found"] += r["html_not_found"]
        if r["tables_total"] == 0:
            summary["dirs_no_tables"] += 1
        if r["html_not_found"] > 0 or r["missing_img"] > 0:
            summary["dirs_with_warning"].append({
                "dir": str(rel),
                "html_not_found": r["html_not_found"],
                "missing_img": r["missing_img"],
            })

        summary["results"].append({
            "dir": str(rel),
            "tables_total": r["tables_total"],
            "replaced": r["replaced"],
            "html_not_found": r["html_not_found"],
            "missing_img": r["missing_img"],
            "new_main_md_chars": r["new_main_md_chars"],
        })
        status = "✓" if r["replaced"] == r["tables_total"] else "!"
        print(
            f"[{i:>2}/{len(dirs)}] {status} {rel}: {r['replaced']}/{r['tables_total']} tables",
            flush=True)

    print()
    print(
        json.dumps({
            k: v
            for k, v in summary.items() if k != "results"
        },
                   indent=2,
                   ensure_ascii=False))


if __name__ == "__main__":
    main()
