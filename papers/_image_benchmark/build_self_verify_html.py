"""Generate a 3-column self-verify viewer for kinetic_table_with_csv items.

Layout (per row):
1. metadata (paper, table id, caption, page)
2. original cropped image (from MinerU)
3. MinerU CSV (rendered as table + raw CSV in <details>)
4. other model column (placeholder, fillable via sidecar JSON later)

The HTML is self-contained: open it directly in a browser. Image paths
use relative `../markdowns/<paper>/images/...` so the HTML must stay
under `papers/_image_benchmark/`.
"""
from __future__ import annotations

import csv as csv_mod
import html as html_mod
import io
import json
from pathlib import Path

ROOT = Path("/Users/ryanxu/CodeBase/GPTase")
BENCH = ROOT / "papers" / "_image_benchmark"


def csv_to_html_table(csv_str: str) -> str:
    if not csv_str:
        return ""
    try:
        rows = list(csv_mod.reader(io.StringIO(csv_str)))
    except Exception:
        return f"<pre>{html_mod.escape(csv_str)}</pre>"
    if not rows:
        return ""
    out: list[str] = ['<table class="csv-table">']
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cells = "".join(f"<{tag}>{html_mod.escape(c)}</{tag}>" for c in row)
        out.append(f"<tr>{cells}</tr>")
    out.append("</table>")
    return "\n".join(out)


def render_row(i: int, item: dict, override: dict | None) -> str:
    img_rel = f"../markdowns/{item['paper']}/{item['image_path_rel']}"
    if override and override.get("ground_truth_csv"):
        csv_data = override["ground_truth_csv"]
        override_note = override.get("notes") or override.get(
            "source") or "manual override"
    else:
        csv_data = item.get("ground_truth_csv") or ""
        override_note = ""
    csv_html = csv_to_html_table(csv_data)
    n_rows = len(csv_data.splitlines()) - 1 if csv_data else 0
    paper_short = item["paper"].replace("/", "/<br/>")
    badge = (f'<div class="override-badge" title="{html_mod.escape(override_note)}">'
             f'manual override</div>' if override_note else '')
    return f"""
<tr id="row-{i}" data-paper="{html_mod.escape(item['paper'])}">
  <td class="meta">
    <div class="row-num">#{i}</div>
    <div class="meta-id">{html_mod.escape(item['id'])}</div>
    <div class="meta-paper">{paper_short}</div>
    <div class="meta-caption">{html_mod.escape(item.get('caption') or '(no caption)')}</div>
    <div class="meta-page">page {item.get('page_idx', '?')} · {n_rows} rows</div>
  </td>
  <td class="image-col"><img src="{img_rel}" loading="lazy" alt="{html_mod.escape(item['id'])}"/></td>
  <td class="csv-col">
    {badge}
    {csv_html}
    <details><summary>raw CSV ({len(csv_data)} chars)</summary><pre>{html_mod.escape(csv_data)}</pre></details>
  </td>
  <td class="model-col" data-id="{html_mod.escape(item['id'])}">
    <div class="placeholder">— pending: paste another model's CSV here —</div>
  </td>
</tr>
"""


def main() -> None:
    bench = json.loads((BENCH / "benchmark.json").read_text())
    overrides_path = BENCH / "manual_overrides.json"
    overrides = (json.loads(overrides_path.read_text())
                 if overrides_path.exists() else {})
    items = [it for it in bench["items"] if it["category"] == "kinetic_table_with_csv"]
    items.sort(key=lambda it: (it["paper"], it["id"]))

    rows_html = "".join(
        render_row(i, it, overrides.get(it["id"])) for i, it in enumerate(items, 1))

    html_doc = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Self-Verify: {len(items)} kinetic tables with MinerU CSV ground truth</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    margin: 0; padding: 1em; color: #222;
  }}
  h1 {{ font-size: 1.3em; margin: 0 0 0.5em; }}
  .toolbar {{
    position: sticky; top: 0; z-index: 10;
    background: #fff; padding: 8px 0; margin-bottom: 1em;
    border-bottom: 1px solid #ddd;
  }}
  .toolbar input {{ padding: 4px 8px; font-size: 0.95em; }}
  .toolbar .stats {{ margin-left: 1em; color: #666; }}
  table.layout {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
  table.layout th, table.layout td {{
    vertical-align: top; padding: 8px;
    border: 1px solid #ccc;
  }}
  table.layout th {{
    background: #f5f5f5; position: sticky; top: 50px; z-index: 1;
    text-align: left;
  }}
  .image-col {{ width: 32%; }}
  .image-col img {{ width: 100%; height: auto; border: 1px solid #ddd; }}
  .csv-col {{ width: 32%; }}
  .csv-col table.csv-table {{ border-collapse: collapse; font-size: 0.85em; width: 100%; }}
  .csv-col td, .csv-col th {{ padding: 2px 6px; border: 1px solid #ccc; word-break: break-word; }}
  .csv-col th {{ background: #eef; }}
  .csv-col details {{ margin-top: 6px; }}
  .csv-col details summary {{ cursor: pointer; color: #555; }}
  .csv-col pre {{
    font-size: 0.78em; max-height: 220px; overflow: auto;
    background: #f9f9f9; padding: 6px; margin-top: 4px;
    white-space: pre-wrap; word-break: break-all;
  }}
  .meta {{ width: 12%; font-size: 0.82em; }}
  .row-num {{ font-weight: bold; color: #888; font-size: 1.2em; }}
  .meta-id {{ font-family: monospace; font-size: 0.82em; color: #666; word-break: break-all; }}
  .meta-paper {{ font-weight: 600; margin-top: 6px; word-break: break-all; }}
  .meta-caption {{ color: #444; margin-top: 6px; line-height: 1.35; }}
  .meta-page {{ color: #888; margin-top: 6px; font-size: 0.85em; }}
  .model-col {{ width: 24%; }}
  .placeholder {{
    color: #aaa; font-style: italic; padding: 1em;
    text-align: center; border: 1px dashed #ccc;
  }}
  .override-badge {{
    display: inline-block; background: #d4edda; color: #155724;
    border: 1px solid #c3e6cb; padding: 2px 8px; border-radius: 3px;
    font-size: 0.78em; font-weight: 600; margin-bottom: 6px; cursor: help;
  }}
</style>
</head><body>

<h1>Self-Verify Benchmark — {len(items)} kinetic tables with MinerU CSV ground truth</h1>
<div class="toolbar">
  <input type="text" id="filter" placeholder="filter by paper or caption..." size="50"/>
  <span class="stats">{len(items)} rows total · <span id="visible-count">{len(items)}</span> visible</span>
</div>

<table class="layout">
<thead><tr>
  <th>metadata</th>
  <th>cropped image (MinerU)</th>
  <th>MinerU CSV (ground truth)</th>
  <th>other model</th>
</tr></thead>
<tbody id="tbody">
{rows_html}
</tbody>
</table>

<script>
const tbody = document.getElementById('tbody');
const filterInput = document.getElementById('filter');
const visibleCount = document.getElementById('visible-count');
filterInput.addEventListener('input', () => {{
  const q = filterInput.value.toLowerCase();
  let n = 0;
  tbody.querySelectorAll('tr').forEach(tr => {{
    const show = !q || tr.textContent.toLowerCase().includes(q);
    tr.style.display = show ? '' : 'none';
    if (show) n++;
  }});
  visibleCount.textContent = n;
}});

// Allow pasting another model's CSV: click a model-col, paste, and the
// page renders it. Persist in localStorage keyed by item id.
document.querySelectorAll('.model-col').forEach(col => {{
  const itemId = col.dataset.id;
  const stored = localStorage.getItem('model:' + itemId);
  if (stored) renderModelCsv(col, stored);
  col.addEventListener('paste', e => {{
    const text = (e.clipboardData || window.clipboardData).getData('text');
    if (!text) return;
    e.preventDefault();
    localStorage.setItem('model:' + itemId, text);
    renderModelCsv(col, text);
  }});
  col.addEventListener('dblclick', () => {{
    if (confirm('Clear pasted result for ' + itemId + '?')) {{
      localStorage.removeItem('model:' + itemId);
      col.innerHTML = '<div class="placeholder">— pending: paste another model\\'s CSV here —</div>';
    }}
  }});
}});

function renderModelCsv(col, csvText) {{
  // Parse CSV minimal-style and render as table
  const rows = csvText.trim().split('\\n').map(line => {{
    // basic split — for fancy CSV use Papa Parse later
    const fields = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {{
      const c = line[i];
      if (c === '"') {{
        if (inQ && line[i+1] === '"') {{ cur += '"'; i++; }} else inQ = !inQ;
      }} else if (c === ',' && !inQ) {{ fields.push(cur); cur = ''; }}
      else cur += c;
    }}
    fields.push(cur);
    return fields;
  }});
  let html = '<table class="csv-table">';
  rows.forEach((r, i) => {{
    const tag = i === 0 ? 'th' : 'td';
    html += '<tr>' + r.map(c => `<${{tag}}>${{escapeHtml(c)}}</${{tag}}>`).join('') + '</tr>';
  }});
  html += '</table><details><summary>raw (' + csvText.length + ' chars) · double-click cell to clear</summary><pre>' + escapeHtml(csvText) + '</pre></details>';
  col.innerHTML = html;
}}

function escapeHtml(s) {{
  return s.replace(/[&<>"']/g, c => ({{
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  }}[c]));
}}
</script>
</body></html>
"""

    out = BENCH / "self_verify.html"
    out.write_text(html_doc, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(items)} rows)")
    print(f"open with: open {out}")


if __name__ == "__main__":
    main()
