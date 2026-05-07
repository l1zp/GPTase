"""Apply structurize_paper to every MinerU paper directory under a root.

Walks recursively, picking any directory that has both a `main.md` and a
`*_content_list.json` sibling. SI subdirectories qualify and are processed.

Usage:
    python batch_structurize.py <root_dir> [--dry-run]

Aggregate report is printed as JSON on stdout; per-paper paper_data.json
files are written next to each main.md.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from structurize_paper import write_paper_data  # noqa: E402


def find_paper_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    for md in root.rglob("main.md"):
        d = md.parent
        if list(d.glob("*_content_list.json")):
            dirs.append(d)
    return sorted(dirs)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: batch_structurize.py <root_dir> [--dry-run]")
        sys.exit(1)
    root = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv[2:]

    dirs = find_paper_dirs(root)
    print(f"[INFO] found {len(dirs)} paper dirs under {root}", flush=True)

    summary = {
        "root": str(root),
        "dry_run": dry,
        "dirs_total": len(dirs),
        "section_total": 0,
        "table_total": 0,
        "table_ghost_total": 0,
        "figure_total": 0,
        "equation_total": 0,
        "errors": [],
        "results": [],
    }

    for i, d in enumerate(dirs, 1):
        rel = d.relative_to(root) if root in d.parents or root == d.parent else d
        try:
            payload = write_paper_data(d, dry_run=dry)
        except Exception as e:
            print(f"[FAIL] {rel}: {e!r}", flush=True)
            summary["errors"].append({"dir": str(rel), "error": repr(e)})
            continue
        meta = payload.get("metadata", {})
        summary["section_total"] += meta.get("section_count", 0)
        summary["table_total"] += meta.get("table_count", 0)
        summary["table_ghost_total"] += meta.get("table_ghost_count", 0)
        summary["figure_total"] += meta.get("figure_count", 0)
        summary["equation_total"] += meta.get("equation_count", 0)
        summary["results"].append({"dir": str(rel), "metadata": meta})
        print(
            f"[{i:>2}/{len(dirs)}] ✓ {rel}: "
            f"sec={meta.get('section_count', 0)} "
            f"tbl={meta.get('table_count', 0)} "
            f"(ghost={meta.get('table_ghost_count', 0)}) "
            f"fig={meta.get('figure_count', 0)} "
            f"eq={meta.get('equation_count', 0)}",
            flush=True,
        )

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
