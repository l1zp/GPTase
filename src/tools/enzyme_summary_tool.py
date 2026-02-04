"""Enzyme Extraction Summary and Statistical Analysis Tool.

This tool provides data synthesis, statistical analysis (via pandas),
and report generation (MD/HTML/JSON) for enzyme kinetics data.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


class EnzymeSummaryTool(BaseTool):
    """Tool for summarizing and analyzing enzyme reaction data."""

    def __init__(self):
        super().__init__(
            name="enzyme_summary_tool",
            description=
            "Generate statistical summaries and multi-format reports from enzyme kinetics data.",
        )

    async def execute(self,
                      reactions: List[Dict[str, Any]],
                      document_name: str = "Unknown",
                      **kwargs) -> ToolResult:
        """Analyze reactions and generate summary data."""
        try:
            if not reactions:
                return ToolResult.success({
                    "summary": "No data found",
                    "total_variants": 0
                })

            # 1. Statistics Calculation
            stats = self._calculate_stats(reactions)

            # 2. Top Performers
            top = self._find_top(reactions)

            # 3. Report Compilation
            summary = {
                "document_name": document_name,
                "timestamp": datetime.now().isoformat(),
                "statistics": stats,
                "top_performers": top,
                "total_variants": len(reactions)
            }

            return ToolResult.success(summary)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return ToolResult.error(str(e))

    def _calculate_stats(self, reactions: List[Dict]) -> Dict:
        df = pd.DataFrame([r.get("kinetics", {}) for r in reactions])
        stats = {}
        for col in ["Km", "kcat", "kcat_over_KM", "Tm"]:
            if col in df.columns:
                series = pd.to_numeric(df[col], errors='coerce').dropna()
                if not series.empty:
                    stats[col] = {
                        "count": len(series),
                        "mean": round(series.mean(), 2),
                        "min": round(series.min(), 2),
                        "max": round(series.max(), 2)
                    }
        return stats

    def _find_top(self, reactions: List[Dict]) -> Dict:
        # Simplified top performer logic
        sorted_reactions = sorted([
            r
            for r in reactions if r.get("kinetics", {}).get("kcat_over_KM") is not None
        ],
                                  key=lambda x: float(x["kinetics"]["kcat_over_KM"]),
                                  reverse=True)
        return {
            "kcat_over_KM": [{
                "name": r["enzyme_name"],
                "value": r["kinetics"]["kcat_over_KM"]
            } for r in sorted_reactions[:5]]
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reactions": {
                    "type": "array",
                    "description": "List of reaction objects"
                },
                "document_name": {
                    "type": "string"
                }
            },
            "required": ["reactions"]
        }
