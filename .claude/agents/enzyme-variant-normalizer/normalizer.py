"""Deterministic normalization for enzyme extraction variant records.

This module reconciles raw extraction replicas into a stable
"sequence -> mutations -> reaction -> kinetics" record shape.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import io
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlopen

logger = logging.getLogger(__name__)

_MUTATION_RE = re.compile(r"^([A-Z])(\d+)([A-Z])$")
_PDB_ID_RE = re.compile(r"^[0-9][A-Za-z0-9]{3}$")
_KINETICS_VALUE_KEYS = {
    "kcat": "kcat",
    "km": "Km",
    "tm": "Tm",
    "kcat/km": "kcat_over_Km",
    "kcat_km": "kcat_over_Km",
    "kcat_over_km": "kcat_over_Km",
}


def normalize_variant_payload(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw extraction payloads into stable variant records."""
    text_extraction_data = inputs.get("text_extraction_data")
    vision_extraction_data = inputs.get("vision_extraction_data")
    document_path = inputs.get("document_path")
    si_document_path = inputs.get("si_document_path")
    # Optional: variant names seen in figure-extractor reactions. Used as the
    # canonical roster for vision-confirmed footnote-letter dedup (Step 3
    # driver passes this in).
    figure_variant_names = set(inputs.get("figure_variant_names") or [])

    document_context = _build_document_context(document_path)
    text_rows = _collect_text_rows(text_extraction_data)
    vision_rows = _collect_vision_rows(vision_extraction_data)
    if vision_rows:
        logger.info(
            "Collected %d vision-extracted rows from CSV tables",
            len(vision_rows),
        )
        text_rows = text_rows + vision_rows
    # MinerU's content_list.json carries the raw <table> HTML for every table
    # it detected. Parsing this directly is loss-free (vs. vision OCR which
    # often skips rows on wide or small-font tables).
    html_rows = _collect_html_table_rows(document_path, source_label="main")
    si_html_rows = _collect_html_table_rows(si_document_path, source_label="si")
    if html_rows or si_html_rows:
        logger.info(
            "Collected %d main + %d SI HTML-table rows from MinerU content_list",
            len(html_rows),
            len(si_html_rows),
        )
        text_rows = text_rows + html_rows + si_html_rows

    vision_dedup_audit: List[Dict[str, Any]] = []
    unresolved_footnote_candidates: List[Dict[str, Any]] = []
    _apply_vision_footnote_dedup(text_rows, figure_variant_names, vision_dedup_audit,
                                 unresolved_footnote_candidates)

    normalized_variants = _merge_variant_rows(text_rows, document_context)

    vision_flags = _summarize_vision_data(vision_extraction_data)
    for record in normalized_variants:
        if vision_flags:
            record.setdefault("evidence", {})["vision_support"] = vision_flags

    return {
        "normalized_variants": normalized_variants,
        "normalization_summary": {
            "variant_count":
            len(normalized_variants),
            "sequence_count":
            sum(1 for item in normalized_variants
                if item.get("scaffold", {}).get("full_sequence")),
            "unresolved_count":
            sum(1 for item in normalized_variants
                if item.get("normalization_status") != "resolved"),
        },
        "vision_dedup_audit": vision_dedup_audit,
        "unresolved_footnote_candidates": unresolved_footnote_candidates,
    }


def _apply_vision_footnote_dedup(
    text_rows: List[Tuple[Dict[str, Any], str]],
    figure_variant_names: set,
    audit: List[Dict[str, Any]],
    unresolved: List[Dict[str, Any]],
) -> None:
    """Rewrite ``<base><single-letter>`` variant names → ``<base>`` when the
    figure-extractor confirms the long form is a footnote-letter artifact.

    Two outputs (both as out-parameters):

    - ``audit``: each row that was rewritten, with source attribution.
    - ``unresolved``: ``<base><letter>`` forms that have a sibling ``<base>``
      anywhere in the extraction but where vision evidence is missing or
      contradictory. Surfaced for human review — they may be legitimate
      siblings (HG3.3b vs HG3.3 both in figures), mutation codes (M172I),
      or true footnotes the figure simply doesn't display.
    """
    all_names: set = set()
    for row, _src in text_rows:
        if not isinstance(row, dict):
            continue
        n = (row.get("variant_name") or "").strip()
        if n:
            all_names.add(n)

    seen_unresolved: set = set()
    rewrites_applied = 0
    for row, src in text_rows:
        if not isinstance(row, dict):
            continue
        n = (row.get("variant_name") or "").strip()
        if len(n) < 2 or not n[-1].isalpha():
            continue
        base = n[:-1]
        if not base:
            continue
        base_in_fig = base in figure_variant_names
        longer_in_fig = n in figure_variant_names

        if base_in_fig and not longer_in_fig:
            row["variant_name"] = base
            row.setdefault("source_context", {})["footnote_letter_stripped"] = n[-1]
            rewrites_applied += 1
            audit.append({
                "source": src,
                "original": n,
                "rewritten": base,
                "evidence": "vision-confirms-dedup",
            })
            continue

        if base not in all_names:
            continue
        key = (n, base, src)
        if key in seen_unresolved:
            continue
        seen_unresolved.add(key)
        evidence = ("vision-rejects-dedup" if
                    (base_in_fig and longer_in_fig) else "no-vision-evidence")
        unresolved.append({
            "source": src,
            "original": n,
            "candidate_base": base,
            "trailing": n[-1],
            "evidence": evidence,
        })

    if rewrites_applied:
        logger.info("Vision-confirmed footnote dedup: %d row(s) rewritten",
                    rewrites_applied)


def flatten_normalized_variants(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten normalized variant records into analysis-friendly rows."""
    rows: List[Dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        reaction = record.get("reaction", {})
        kinetics = record.get("kinetics", {})
        mutation_codes = []
        for mutation in record.get("mutations", []):
            if isinstance(mutation, dict) and mutation.get("mutation_code"):
                mutation_codes.append(str(mutation["mutation_code"]))
        evidence = record.get("evidence", {}).get("sources", [])
        evidence_sources = []
        for source in evidence:
            if isinstance(source, dict):
                source_id = source.get("source_id")
                if source_id:
                    evidence_sources.append(str(source_id))
        rows.append({
            "variant_name":
            record.get("variant_name", ""),
            "aliases":
            ",".join(record.get("aliases", [])) if isinstance(
                record.get("aliases"), list) else "",
            "scaffold_pdb_id":
            record.get("scaffold_pdb_id", ""),
            "full_sequence":
            record.get("full_sequence", ""),
            "variant_sequence":
            record.get("variant_sequence", ""),
            "mutation_codes":
            ",".join(mutation_codes),
            "reaction_name":
            reaction.get("reaction_name", ""),
            "substrates":
            ",".join(reaction.get("substrates", [])) if isinstance(
                reaction.get("substrates"), list) else "",
            "products":
            ",".join(reaction.get("products", [])) if isinstance(
                reaction.get("products"), list) else "",
            "kcat":
            kinetics.get("kcat", ""),
            "kcat_unit":
            kinetics.get("kcat_unit", ""),
            "Km":
            kinetics.get("Km", ""),
            "Km_unit":
            kinetics.get("Km_unit", ""),
            "kcat_over_Km":
            kinetics.get("kcat_over_Km", ""),
            "kcat_over_Km_unit":
            kinetics.get("kcat_over_Km_unit", ""),
            "normalization_status":
            record.get("normalization_status", ""),
            "issues":
            " | ".join(record.get("issues", [])) if isinstance(
                record.get("issues"), list) else "",
            "evidence_sources":
            ",".join(evidence_sources),
        })
    return rows


def _build_document_context(document_path: Any) -> Dict[str, Any]:
    context = {
        "reaction_name": None,
        "products": [],
        "variant_to_pdb": {},
        "base_variant_to_pdb": {},
        "variant_mutations": defaultdict(list),
    }
    if not isinstance(document_path, str) or not document_path:
        return context

    path = Path(document_path)
    if not path.exists():
        return context

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return context

    lowered = text.lower()
    if "kemp elimination" in lowered:
        context["reaction_name"] = "Kemp elimination"

    product_match = re.search(
        r"2-cyano-4-nitrophenolate ion|2-nitrophenol|2-cyano-4-nitrophenol",
        text,
        re.IGNORECASE,
    )
    if product_match:
        context["products"] = [product_match.group(0)]

    table_match = re.search(r"<table>(.*?)</table>", text, re.IGNORECASE | re.DOTALL)
    if table_match:
        rows = re.findall(r"<tr>(.*?)</tr>", table_match.group(1), re.DOTALL)
        for raw_row in rows[1:]:
            cells = re.findall(r"<td>(.*?)</td>", raw_row, re.DOTALL)
            if len(cells) < 3:
                continue
            variant_name = _clean_cell_text(cells[0])
            pdb_code = _clean_cell_text(cells[1]).upper()
            key_residues = _clean_cell_text(cells[2])
            if variant_name and pdb_code:
                context["variant_to_pdb"][variant_name] = pdb_code
                context["base_variant_to_pdb"][_variant_base_name(
                    variant_name)] = pdb_code
    for variant_name in re.findall(r"(KE\d+\s*\([A-Z]\d+[A-Z]\))", text):
        parsed = _extract_mutations_from_variant_name(variant_name)
        if parsed:
            context["variant_mutations"][variant_name].extend(parsed)

    return context


def _clean_cell_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _collect_text_rows(text_extraction_data: Any) -> List[Tuple[Dict[str, Any], str]]:
    rows: List[Tuple[Dict[str, Any], str]] = []
    if isinstance(text_extraction_data, list):
        for index, entry in enumerate(text_extraction_data, start=1):
            source = f"text_replica_{index}"
            if isinstance(entry, dict):
                replica_rows = entry.get("reactions", [])
                if isinstance(replica_rows, list):
                    for row in replica_rows:
                        if isinstance(row, dict):
                            rows.append((row, source))
                continue
            if isinstance(entry, list):
                for row in entry:
                    if isinstance(row, dict):
                        rows.append((row, source))
    elif isinstance(text_extraction_data, dict):
        for row in text_extraction_data.get("reactions", []):
            if isinstance(row, dict):
                rows.append((row, "text"))
    return rows


_VISION_VARIANT_HEADERS = {
    "variant",
    "variants",
    "clone",
    "clones",
    "design",
    "designs",
    "name",
    "id",
    "enzyme",
    "mutant",
    "mutants",
    "construct",
}
_VISION_KINETIC_HEADERS = {
    "kcat": "kcat",
    "k_cat": "kcat",
    "km": "Km",
    "k_m": "Km",
    "tm": "Tm",
    "t_m": "Tm",
    "tdenat": "Tm",
    "kcat_km": "kcat_over_Km",
    "kcat_over_km": "kcat_over_Km",
    "k_cat_k_m": "kcat_over_Km",
    "kcatkm": "kcat_over_Km",
    "specificity": "kcat_over_Km",
}


def _identify_kinetic_column(header: str) -> Tuple[Optional[str], Optional[str]]:
    """Map a CSV column header to (canonical_field, unit) -- None if not kinetic."""
    if not header:
        return None, None
    unit_match = re.search(r"\(([^)]+)\)", header)
    unit = unit_match.group(1).strip() if unit_match else None
    stripped = re.sub(r"\([^)]*\)", "", header).strip()
    # MinerU table HTML often emits "kcat, s-1" with the unit comma-separated
    # (no parens). Treat the trailing comma as a unit boundary.
    if "," in stripped and not unit:
        head, tail = stripped.split(",", 1)
        stripped = head.strip()
        unit = tail.strip() or None
    stripped = stripped.lower()
    compact = re.sub(r"[\s/\-_·.]+", "_", stripped).strip("_")
    canonical = _VISION_KINETIC_HEADERS.get(compact)
    if canonical:
        return canonical, unit
    compact2 = compact.replace("__", "_")
    return _VISION_KINETIC_HEADERS.get(compact2), unit


def _score_kinetic_header(cells: List[str]) -> int:
    """Count how many cells in a candidate header row map to kinetic fields."""
    return sum(1 for c in cells if c and _identify_kinetic_column(c)[0])


def _strip_uncertainty(value: str) -> Optional[float]:
    """Return the central numeric value from a string like '5.1±0.8' or '2.1·10⁴'.

    Returns None for empty / 'ND' / non-numeric tokens.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nd", "n.d.", "n/a", "na", "-", "—"}:
        return None
    for sep in ("±", "+/-", "+-"):
        if sep in text:
            text = text.split(sep)[0].strip()
            break
    text = text.replace("·10", "e").replace("×10", "e").replace("⋅10", "e")
    sup = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
    text = text.translate(sup)
    text = text.replace(",", "")
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _parse_csv_to_rows(csv_data: str, *, figure_id: str = "") -> List[Dict[str, Any]]:
    """Parse a CSV string into row dicts matching the text extraction schema.

    Handles two-tier MinerU table headers (group label on row 0, real column
    names on row 1) by scoring the first two rows for kinetic-column matches.
    """
    rows: List[Dict[str, Any]] = []
    if not csv_data or not isinstance(csv_data, str):
        return rows
    try:
        all_rows = list(csv.reader(io.StringIO(csv_data)))
    except Exception:
        return rows
    if len(all_rows) < 2:
        return rows

    # Decide which row is the real header. Prefer the row with the most
    # kinetic-column matches; fall back to the first row.
    score0 = _score_kinetic_header(all_rows[0])
    score1 = _score_kinetic_header(all_rows[1]) if len(all_rows) > 1 else 0
    if score1 > score0 and score1 >= 1:
        fieldnames = all_rows[1]
        data_rows = all_rows[2:]
    else:
        fieldnames = all_rows[0]
        data_rows = all_rows[1:]

    if not fieldnames:
        return rows

    # Pick the first column that looks like a variant identifier.
    variant_idx: Optional[int] = None
    for i, col in enumerate(fieldnames):
        compact = re.sub(r"[\s_]+", "", str(col).lower().strip())
        if compact in _VISION_VARIANT_HEADERS or compact.endswith(
                "name") or compact.endswith("code"):
            variant_idx = i
            break
    if variant_idx is None:
        variant_idx = 0  # fall back to first column

    # Pre-compute kinetic column mapping by index.
    kinetic_map: Dict[int, Tuple[str, Optional[str]]] = {}
    for i, col in enumerate(fieldnames):
        if i == variant_idx:
            continue
        canonical, unit = _identify_kinetic_column(str(col))
        if canonical:
            kinetic_map[i] = (canonical, unit)

    # If no kinetic columns are detected, this is almost certainly a
    # non-kinetic table (PDB metadata, sequence, etc.). Skip the whole table.
    if not kinetic_map:
        return rows

    for raw in data_rows:
        if not raw or len(raw) <= variant_idx:
            continue
        variant_name = str(raw[variant_idx] or "").strip()
        if not variant_name:
            continue
        kinetics: Dict[str, Any] = {}
        for i, (canonical, unit) in kinetic_map.items():
            if i >= len(raw):
                continue
            value = _strip_uncertainty(raw[i])
            if value is None:
                continue
            kinetics[canonical] = value
            if unit:
                kinetics[f"{canonical}_unit"] = unit
        # Keep variants that appear in a kinetic table even if every cell is
        # NA -- the variant name itself is evidence that the enzyme exists
        # and downstream merging may pick up kinetics from another source.
        rows.append({
            "variant_name": variant_name,
            "enzyme_name": variant_name,
            "kinetics": kinetics,
            "source_context": {
                "from_table": True,
                "from_text": False,
                "from_vision": True,
                "vision_figure_id": figure_id,
            },
        })
    return rows


_HTML_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_HTML_CELL_RE = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _html_table_to_csv(table_body: str) -> str:
    """Convert MinerU's `<table><tr><td>...</td></tr></table>` to CSV.

    The CSV is then parsed by `_parse_csv_to_rows` for header-driven kinetic
    extraction. MinerU emits uniform structure (rowspan=1 colspan=1 per cell),
    so naive regex extraction works.
    """
    rows = _HTML_TR_RE.findall(table_body)
    if not rows:
        return ""
    csv_rows: List[str] = []
    for r in rows:
        cells = _HTML_CELL_RE.findall(r)
        cleaned: List[str] = []
        for c in cells:
            text = _HTML_TAG_RE.sub("", c)
            text = re.sub(r"\s+", " ", text).strip()
            text = text.replace('"', '""')
            cleaned.append(f'"{text}"')
        csv_rows.append(",".join(cleaned))
    return "\n".join(csv_rows)


def _collect_html_table_rows(
    md_path: Any,
    source_label: str = "main",
) -> List[Tuple[Dict[str, Any], str]]:
    """Parse MinerU table HTML into row tuples.

    Prefers the `paper_data.json` sidecar (produced by
    `.claude/skills/pdf-extractor/scripts/structurize_paper.py`) which
    carries pre-parsed `csv_preview` per table -- avoids re-running the
    HTML->CSV conversion. Falls back to reading `*_content_list.json`
    directly if the sidecar is missing, preserving v8 behavior.

    `md_path` is the path to `main.md` of either the main paper or an SI
    subdirectory; we look for `paper_data.json` and `*_content_list.json`
    next to it.
    """
    rows: List[Tuple[Dict[str, Any], str]] = []
    if not isinstance(md_path, str) or not md_path:
        return rows
    base = Path(md_path).parent
    if not base.exists():
        return rows

    # Preferred path: structured sidecar from pdf-extractor skill.
    sidecar = base / "paper_data.json"
    if sidecar.exists():
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        if isinstance(payload, dict):
            for tbl in payload.get("tables", []) or []:
                if not isinstance(tbl, dict):
                    continue
                csv_data = tbl.get("csv_preview") or ""
                if not csv_data:
                    # Ghost tables (image-only) carry empty csv_preview;
                    # skip them here -- the figure-vision path handles them.
                    continue
                table_id = tbl.get("table_id") or ""
                page_idx = tbl.get("page_idx")
                caption = tbl.get("caption") or ""
                figure_id = (
                    table_id or "Table"
                ) if not caption else f"{table_id or 'Table'} ({caption[:40]})"
                source = f"html_{source_label}_{table_id or 'table'}_p{page_idx}"
                for parsed in _parse_csv_to_rows(csv_data, figure_id=figure_id):
                    parsed.setdefault("source_context", {}).update({
                        "from_table": True,
                        "from_text": False,
                        "from_html_table": True,
                        "from_vision": False,
                        "html_table_id": table_id,
                        "page_idx": page_idx,
                    })
                    rows.append((parsed, source))
            return rows

    # Fallback path: read MinerU's content_list.json directly (v8 behavior).
    cl_files = list(base.glob("*_content_list.json"))
    if not cl_files:
        return rows
    cl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    try:
        items = json.loads(cl_files[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return rows

    table_idx = 0
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "table":
            continue
        body = item.get("table_body") or ""
        if not body:
            continue
        table_idx += 1
        page_idx = item.get("page_idx")
        caption = ""
        cap_list = item.get("table_caption")
        if isinstance(cap_list, list) and cap_list:
            caption = str(cap_list[0])
        figure_id = f"Table {table_idx}"
        if caption:
            figure_id = f"{figure_id} ({caption[:40]})"
        csv_data = _html_table_to_csv(body)
        if not csv_data:
            continue
        source = f"html_{source_label}_table_{table_idx}_p{page_idx}"
        for parsed in _parse_csv_to_rows(csv_data, figure_id=figure_id):
            parsed.setdefault("source_context", {}).update({
                "from_table": True,
                "from_text": False,
                "from_html_table": True,
                "from_vision": False,
                "html_table_index": table_idx,
                "page_idx": page_idx,
            })
            rows.append((parsed, source))
    return rows


def _collect_vision_rows(
    vision_extraction_data: Any, ) -> List[Tuple[Dict[str, Any], str]]:
    """Parse vision-extracted CSV tables into row tuples.

    Accepts either a flat list of `{csv_data, figure_id, image_number}` dicts
    or a list-of-lists from replicated step output.
    """
    rows: List[Tuple[Dict[str, Any], str]] = []
    if not isinstance(vision_extraction_data, list):
        return rows

    def _absorb(table_dict: Any, replica_idx: int) -> None:
        if not isinstance(table_dict, dict):
            return
        csv_data = table_dict.get("csv_data")
        if not csv_data:
            return
        figure_id = str(table_dict.get("figure_id") or "").strip()
        source = f"vision_replica_{replica_idx}"
        if figure_id:
            source = f"{source}_{figure_id}"
        for parsed in _parse_csv_to_rows(csv_data, figure_id=figure_id):
            rows.append((parsed, source))

    for replica_idx, entry in enumerate(vision_extraction_data, start=1):
        if isinstance(entry, dict):
            _absorb(entry, replica_idx)
        elif isinstance(entry, list):
            for nested in entry:
                _absorb(nested, replica_idx)
    return rows


def _merge_variant_rows(
    rows: Iterable[Tuple[Dict[str, Any], str]],
    document_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Tuple[Dict[str, Any], str]]] = defaultdict(list)
    display_names: Dict[str, str] = {}
    aliases: Dict[str, List[str]] = defaultdict(list)
    for row, source in rows:
        variant_name = str(row.get("variant_name") or row.get("enzyme_name")
                           or "").strip()
        if not variant_name:
            continue
        group_key = _variant_group_key(variant_name, row)
        grouped[group_key].append((row, source))
        aliases[group_key].append(variant_name)
        preferred_name = display_names.get(group_key)
        candidate_name = _preferred_variant_name(preferred_name, variant_name)
        if candidate_name:
            display_names[group_key] = candidate_name

    normalized: List[Dict[str, Any]] = []
    for group_key in sorted(grouped):
        merged = _normalize_single_variant(
            display_names[group_key],
            grouped[group_key],
            document_context,
        )
        merged["aliases"] = sorted(dict.fromkeys(aliases[group_key]))
        normalized.append(merged)
    return normalized


def _normalize_single_variant(
    variant_name: str,
    entries: List[Tuple[Dict[str, Any], str]],
    document_context: Dict[str, Any],
) -> Dict[str, Any]:
    canonical_row = max(entries, key=lambda item: _row_completeness(item[0]))[0]
    canonical_mutations = _collect_canonical_mutations(variant_name, entries,
                                                       document_context)
    kinetics = _normalize_kinetics(canonical_row.get("kinetics"))
    issues: List[str] = []

    paper_pdb = _select_scaffold_pdb(variant_name, entries, document_context)
    scaffold_pdb_id = str(paper_pdb).upper() if paper_pdb else None

    scaffold_sequence = None
    sequence_source = None
    if scaffold_pdb_id:
        scaffold_sequence = _fetch_pdb_sequence(scaffold_pdb_id)
        if scaffold_sequence:
            sequence_source = f"rcsb:{scaffold_pdb_id}"
        else:
            issues.append(f"Unable to fetch sequence for PDB {scaffold_pdb_id}")

    variant_sequence = None
    if scaffold_sequence and canonical_mutations:
        variant_sequence, mutation_issues = _apply_mutations(scaffold_sequence,
                                                             canonical_mutations)
        issues.extend(mutation_issues)
    else:
        variant_sequence = scaffold_sequence

    reaction_name = (canonical_row.get("reaction_name")
                     or document_context.get("reaction_name"))
    products = canonical_row.get("products")
    if not isinstance(products, list) or not products:
        products = document_context.get("products") or []

    evidence_sources = [{
        "source_type": "text_extraction",
        "source_id": source,
    } for _, source in entries]
    if sequence_source:
        evidence_sources.append({
            "source_type": "database",
            "source_id": sequence_source,
        })

    normalization_status = "resolved"
    if issues:
        normalization_status = "partially_resolved" if scaffold_sequence else "unresolved"

    record = {
        "variant_name": variant_name,
        "enzyme_name": canonical_row.get("enzyme_name") or variant_name,
        "paper_asserted_variant_name": variant_name,
        "canonical_mutations": [item["mutation_code"] for item in canonical_mutations],
        "mutations": canonical_mutations,
        "scaffold": {
            "pdb_id": scaffold_pdb_id,
            "full_sequence": scaffold_sequence,
            "variant_sequence": variant_sequence,
        },
        "scaffold_pdb_id": scaffold_pdb_id,
        "full_sequence": scaffold_sequence,
        "variant_sequence": variant_sequence,
        "reaction": {
            "reaction_name": reaction_name,
            "substrates": _ensure_list(canonical_row.get("substrates")),
            "products": _ensure_list(products),
        },
        "kinetics": kinetics,
        "normalization_status": normalization_status,
        "issues": sorted(dict.fromkeys(issue for issue in issues if issue)),
        "evidence": {
            "sources": evidence_sources,
        },
    }
    return record


def _select_scaffold_pdb(
    variant_name: str,
    entries: List[Tuple[Dict[str, Any], str]],
    document_context: Dict[str, Any],
) -> Optional[str]:
    candidates: List[str] = []
    for row, _source in entries:
        direct = row.get("scaffold_pdb_id")
        if direct:
            candidates.append(str(direct))
        pdb_ids = row.get("pdb_ids")
        if isinstance(pdb_ids, list):
            candidates.extend(str(item) for item in pdb_ids if item)
    exact = document_context["variant_to_pdb"].get(variant_name)
    if exact:
        candidates.append(str(exact))
    base = _variant_base_name(variant_name)
    base_match = document_context["base_variant_to_pdb"].get(base)
    if base_match:
        candidates.append(str(base_match))
    for candidate in candidates:
        normalized = _normalize_pdb_id(candidate)
        if normalized:
            return normalized
    return None


def _normalize_pdb_id(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    normalized = str(value).strip().upper()
    if _PDB_ID_RE.fullmatch(normalized):
        return normalized
    return None


def _variant_group_key(variant_name: str, row: Dict[str, Any]) -> str:
    base_name = _variant_base_name(variant_name)
    mutation_codes = []
    for mutation in row.get("mutation_annotations", []) or []:
        if isinstance(mutation, dict) and mutation.get("mutation_code"):
            mutation_codes.append(str(mutation["mutation_code"]))
    if not mutation_codes:
        for mutation in row.get("mutations", []) or []:
            if isinstance(mutation, str):
                mutation_codes.append(mutation)
    mutation_codes.extend(_extract_mutations_from_variant_name(variant_name))
    canonical = ",".join(sorted(dict.fromkeys(mutation_codes)))
    return f"{base_name}|{canonical}"


def _variant_base_name(variant_name: str) -> str:
    normalized = re.sub(r"\s+", " ", variant_name).strip()
    normalized = re.sub(r"\([^)]*\)", "", normalized).strip()
    return normalized or variant_name.strip()


def _preferred_variant_name(current: Optional[str], candidate: str) -> str:
    if not current:
        return candidate
    current_score = _variant_name_score(current)
    candidate_score = _variant_name_score(candidate)
    if candidate_score > current_score:
        return candidate
    return current


def _variant_name_score(value: str) -> Tuple[int, int]:
    score = 0
    if "(" in value and ")" in value:
        score += 2
    if "wild type" in value.lower() or "reference" in value.lower():
        score += 1
    return score, len(value)


def _collect_canonical_mutations(
    variant_name: str,
    entries: List[Tuple[Dict[str, Any], str]],
    document_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    candidates: List[str] = []
    candidates.extend(_extract_mutations_from_variant_name(variant_name))
    for row, _source in entries:
        mutations = row.get("mutations")
        if isinstance(mutations, list):
            candidates.extend(str(item).strip() for item in mutations if item)
        elif isinstance(mutations, str) and mutations.strip():
            candidates.append(mutations.strip())
        for annotation in row.get("mutation_annotations", []) or []:
            if isinstance(annotation, dict) and annotation.get("mutation_code"):
                candidates.append(str(annotation["mutation_code"]).strip())
    candidates.extend(document_context["variant_mutations"].get(variant_name, []))

    structured = []
    seen = set()
    for code in candidates:
        parsed = _parse_mutation_code(code)
        if parsed is None:
            continue
        mutation_code = parsed["mutation_code"]
        if mutation_code in seen:
            continue
        seen.add(mutation_code)
        structured.append(parsed)
    return structured


def _extract_mutations_from_variant_name(variant_name: str) -> List[str]:
    matches = re.findall(r"\(([A-Z]\d+[A-Z](?:,[A-Z]\d+[A-Z])*)\)", variant_name)
    mutations: List[str] = []
    for match in matches:
        mutations.extend(part.strip() for part in match.split(",") if part.strip())
    return mutations


def _parse_mutation_code(value: str) -> Optional[Dict[str, Any]]:
    match = _MUTATION_RE.fullmatch(value)
    if not match:
        return None
    return {
        "from_residue": match.group(1),
        "position": int(match.group(2)),
        "to_residue": match.group(3),
        "mutation_code": value,
    }


def _normalize_kinetics(raw: Any) -> Dict[str, Any]:
    kinetics = raw if isinstance(raw, dict) else {}
    normalized = {
        "kcat": None,
        "kcat_unit": None,
        "Km": None,
        "Km_unit": None,
        "kcat_over_Km": None,
        "kcat_over_Km_unit": None,
        "Tm": None,
        "Tm_unit": None,
    }
    for key, value in kinetics.items():
        canonical = normalize_kinetics_key(key)
        if canonical in normalized:
            normalized[canonical] = value
    return normalized


def normalize_kinetics_key(key: Any) -> str:
    """Return the canonical kinetics field name for a given raw key.

    Handles case and separator variants (``kcat/KM``, ``kcat_Km``,
    ``kcat_over_KM``, …) and their ``_unit`` counterparts.
    """
    raw_key = str(key)
    if raw_key.endswith("_unit"):
        prefix = raw_key[:-5]
        return f"{normalize_kinetics_key(prefix)}_unit"

    compact = raw_key.lower().replace(" ", "").replace("\\", "/")
    compact = compact.replace("-", "_")
    if compact in _KINETICS_VALUE_KEYS:
        return _KINETICS_VALUE_KEYS[compact]
    return raw_key


def _row_completeness(row: Dict[str, Any]) -> int:
    score = 0
    for key in ("variant_name", "enzyme_name", "substrates", "products", "pdb_ids"):
        value = row.get(key)
        if value:
            score += 1
    kinetics = row.get("kinetics")
    if isinstance(kinetics, dict):
        score += sum(1 for value in kinetics.values() if value not in (None, "", []))
    mutations = row.get("mutations")
    if mutations:
        score += len(mutations) if isinstance(mutations, list) else 1
    return score


def _apply_mutations(sequence: str,
                     mutations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    seq_chars = list(sequence)
    issues: List[str] = []
    for mutation in mutations:
        position = mutation["position"]
        if position < 1 or position > len(seq_chars):
            issues.append(
                f"Mutation {mutation['mutation_code']} is outside sequence length {len(seq_chars)}"
            )
            continue
        current = seq_chars[position - 1]
        if current != mutation["from_residue"]:
            issues.append(
                f"Mutation {mutation['mutation_code']} conflicts with scaffold residue {current}{position}"
            )
            continue
        seq_chars[position - 1] = mutation["to_residue"]
    return "".join(seq_chars), issues


def _fetch_pdb_sequence(pdb_id: str) -> Optional[str]:
    url = f"https://www.rcsb.org/fasta/entry/{pdb_id}/display"
    try:
        with urlopen(url, timeout=10) as response:
            fasta = response.read().decode("utf-8")
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("Failed to fetch FASTA for %s: %s", pdb_id, exc)
        return None
    sequences: List[str] = []
    current: List[str] = []
    for line in fasta.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            if current:
                sequences.append("".join(current))
                current = []
            continue
        current.append(stripped)
    if current:
        sequences.append("".join(current))
    if not sequences:
        return None
    return max(sequences, key=len)


def _summarize_vision_data(vision_extraction_data: Any) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    if not isinstance(vision_extraction_data, list):
        return summaries
    for index, entry in enumerate(vision_extraction_data, start=1):
        if isinstance(entry, dict):
            figure_id = entry.get("figure_id")
            image_number = entry.get("image_number")
            if figure_id or image_number:
                summaries.append({
                    "source_id": f"vision_replica_{index}",
                    "figure_id": figure_id,
                    "image_number": image_number,
                })
        elif isinstance(entry, list):
            for nested in entry:
                if not isinstance(nested, dict):
                    continue
                figure_id = nested.get("figure_id")
                image_number = nested.get("image_number")
                if figure_id or image_number:
                    summaries.append({
                        "source_id": f"vision_replica_{index}",
                        "figure_id": figure_id,
                        "image_number": image_number,
                    })
    return summaries


def _first_list_item(value: Any) -> Optional[Any]:
    if isinstance(value, list) and value:
        return value[0]
    return value if value else None


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]
