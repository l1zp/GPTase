import math
import re
from typing import Any, Dict, List

from .enzyme_terms import CATEGORY_ZH, TERMS


def normalize_text(text: str) -> str:
    t = text.replace("\r", "\n")
    t = re.sub(r"\n{2,}", "\n", t)
    return t


def _score_snippet(snippet: str, keywords: List[str]) -> float:
    s = snippet.lower()
    hits = sum(1 for k in keywords if k.lower() in s)
    if hits == 0:
        return 0.0
    length_penalty = min(1.0, 1000 / max(50, len(snippet)))
    base = min(1.0, 0.6 * hits)
    return round(base * length_penalty, 3)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def extract_steps(text: str) -> Dict[str, Any]:
    txt = normalize_text(text)
    paragraphs = [p.strip() for p in re.split(r"\n+", txt) if p.strip()]
    results: List[Dict[str, Any]] = []
    step_id = 1
    for p in paragraphs:
        cat_scores = {cat: _score_snippet(p, kws) for cat, kws in TERMS.items()}
        for cat, score in cat_scores.items():
            if score >= 0.3:
                results.append(
                    {
                        "step_id": str(step_id),
                        "category": cat,
                        "label_zh": CATEGORY_ZH.get(cat, cat),
                        "description": p,
                        "evidence": p[:240],
                        "confidence": score,
                    }
                )
                step_id += 1
    overall_conf = round(
        sum(r["confidence"] for r in results) / max(1, len(results)), 3
    )
    components = {
        "Design": [r["description"] for r in results if r["category"] == "Design"],
        "Assay": [r["description"] for r in results if r["category"] == "Assay"],
        "Optimization": [
            r["description"] for r in results if r["category"] == "Optimization"
        ],
    }
    return {
        "status": "success",
        "steps": results,
        "components": components,
        "confidence_overall": overall_conf,
    }


def extract_from_html(html: str) -> Dict[str, Any]:
    return extract_steps(_strip_html(html))
