"""Enzyme Extraction Summary Agent.

This agent generates comprehensive summaries of enzyme kinetics extraction
results from scientific literature.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_ERROR, STATUS_SUCCESS
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry


class EnzymeExtractionSummaryAgent(BaseAgent):
    """Agent for summarizing enzyme kinetics extraction results.

    This agent processes extraction.json files and generates:
    - Statistical overview (counts, coverage, ranges)
    - Top performers (best kcat/KM, highest Tm)
    - Data quality assessment
    - Detailed tables
    - Key findings

    Supports multiple output formats: Markdown, JSON, HTML
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
        model_manager: Optional[Any] = None,
    ):
        """Initialize the EnzymeExtractionSummaryAgent.

        Args:
            agent_id: Unique identifier for this agent
            memory_manager: Memory manager for context storage
            tool_registry: Tool registry for available tools
            model_manager: Optional model manager for LLM operations
        """
        super().__init__(agent_id, memory_manager, tool_registry, model_manager)
        self.agent_id = agent_id

    async def process_task(
        self,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process a summary generation task.

        Args:
            task: Task dictionary containing:
                - extraction_path (str): Path to extraction.json
                - output_formats (List[str]): Desired output formats
                - output_dir (str, optional): Output directory path
                - document_name (str, optional): Document name for report

        Returns:
            Dictionary with status and generated summaries
        """
        try:
            # Extract parameters
            extraction_path = task.get("extraction_path")
            if not extraction_path:
                return self._error_response(
                    "Missing required parameter: extraction_path"
                )

            output_formats = task.get("output_formats", ["markdown"])
            document_name = task.get("document_name", Path(extraction_path).parent.parent.name)

            # Determine output directory
            if "output_dir" in task:
                output_dir = Path(task["output_dir"])
            else:
                output_dir = Path(f"data/output/{document_name}/summary")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Load extraction data
            extraction_data = await self._load_extraction(extraction_path)
            if not extraction_data:
                return self._error_response(f"Failed to load extraction from {extraction_path}")

            reactions = extraction_data.get("reactions", [])

            # Generate summary
            summary = self._generate_summary(reactions, document_name, extraction_path)

            # Generate outputs in requested formats
            outputs = {}
            for fmt in output_formats:
                if fmt == "markdown":
                    outputs["markdown"] = self._generate_markdown(summary)
                    md_path = output_dir / "summary.md"
                    self._write_output(md_path, outputs["markdown"])
                elif fmt == "json":
                    outputs["json"] = self._generate_json(summary)
                    json_path = output_dir / "summary.json"
                    self._write_output(json_path, outputs["json"])
                elif fmt == "html":
                    outputs["html"] = self._generate_html(summary)
                    html_path = output_dir / "summary.html"
                    self._write_output(html_path, outputs["html"])

            return {
                "status": STATUS_SUCCESS,
                "summary": summary,
                "outputs": outputs,
                "files_written": [str(output_dir / f"summary.{fmt}") for fmt in output_formats],
            }

        except Exception as e:
            return self._error_response(f"Error generating summary: {str(e)}")

    async def _load_extraction(self, path: str) -> Optional[Dict]:
        """Load extraction data from JSON file.

        Args:
            path: Path to extraction.json

        Returns:
            Extraction data dictionary or None if error
        """
        try:
            extraction_path = Path(path)
            if not extraction_path.exists():
                raise FileNotFoundError(f"Extraction file not found: {path}")

            with open(extraction_path, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading extraction: {e}")
            return None

    def _generate_summary(
        self, reactions: List[Dict], document_name: str, extraction_path: str
    ) -> Dict[str, Any]:
        """Generate comprehensive summary from reactions.

        Args:
            reactions: List of enzyme reaction dictionaries
            document_name: Name of the document
            extraction_path: Path to extraction file

        Returns:
            Summary dictionary with all analysis results
        """
        if not reactions:
            return self._empty_summary(document_name, extraction_path)

        # Infer missing products from substrates
        reactions = self._infer_products(reactions)

        # Statistics
        stats = self._calculate_statistics(reactions)

        # Top performers
        top_performers = self._find_top_performers(reactions)

        # Data quality
        data_quality = self._assess_data_quality(reactions)

        # Key findings
        findings = self._generate_findings(reactions, stats, top_performers)

        return {
            "document_name": document_name,
            "extraction_path": extraction_path,
            "timestamp": datetime.now().isoformat(),
            "overview": {
                "total_variants": len(reactions),
                "source_file": reactions[0].get("source_file", "Unknown"),
            },
            "statistics": stats,
            "top_performers": top_performers,
            "data_quality": data_quality,
            "key_findings": findings,
            "reactions": reactions,
        }

    def _calculate_statistics(self, reactions: List[Dict]) -> Dict[str, Any]:
        """Calculate statistical metrics.

        Args:
            reactions: List of reaction dictionaries

        Returns:
            Statistics dictionary with ranges, means, coverage
        """
        import pandas as pd

        df = pd.DataFrame(reactions)

        stats = {"total_variants": len(reactions)}

        # Kinetic parameters statistics
        for param in ["kcat", "Km", "kcat_over_KM", "Tm"]:
            values = []
            for r in reactions:
                val = r.get("kinetics", {}).get(param)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass

            if values:
                stats[param] = {
                    "count": len(values),
                    "coverage": len(values) / len(reactions) * 100,
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }
            else:
                stats[param] = {"count": 0, "coverage": 0.0}

        # Mutations statistics
        with_mutations = sum(1 for r in reactions if r.get("mutations"))
        stats["with_mutations"] = with_mutations
        stats["mutation_coverage"] = with_mutations / len(reactions) * 100 if reactions else 0

        # PDB statistics
        with_pdb = sum(1 for r in reactions if r.get("pdb_ids"))
        stats["with_pdb"] = with_pdb
        stats["pdb_coverage"] = with_pdb / len(reactions) * 100 if reactions else 0

        return stats

    def _find_top_performers(self, reactions: List[Dict]) -> Dict[str, Any]:
        """Identify top performing variants.

        Args:
            reactions: List of reaction dictionaries

        Returns:
            Dictionary with top performers for each metric
        """
        top = {}

        # Top kcat/KM (catalytic efficiency)
        kcatkm_list = []
        for r in reactions:
            val = r.get("kinetics", {}).get("kcat_over_KM")
            if val is not None:
                try:
                    kcatkm_list.append((r["enzyme_name"], float(val)))
                except (ValueError, TypeError):
                    pass

        if kcatkm_list:
            top["kcat_over_KM"] = sorted(kcatkm_list, key=lambda x: x[1], reverse=True)[:5]

        # Highest Tm (thermal stability)
        tm_list = []
        for r in reactions:
            val = r.get("kinetics", {}).get("Tm")
            if val is not None:
                try:
                    tm_list.append((r["enzyme_name"], float(val)))
                except (ValueError, TypeError):
                    pass

        if tm_list:
            top["Tm"] = sorted(tm_list, key=lambda x: x[1], reverse=True)[:5]

        # Highest kcat (turnover rate)
        kcat_list = []
        for r in reactions:
            val = r.get("kinetics", {}).get("kcat")
            if val is not None:
                try:
                    kcat_list.append((r["enzyme_name"], float(val)))
                except (ValueError, TypeError):
                    pass

        if kcat_list:
            top["kcat"] = sorted(kcat_list, key=lambda x: x[1], reverse=True)[:5]

        return top

    def _assess_data_quality(self, reactions: List[Dict]) -> Dict[str, Any]:
        """Assess data quality and completeness.

        Args:
            reactions: List of reaction dictionaries

        Returns:
            Data quality assessment dictionary
        """
        total = len(reactions)

        # Count missing critical fields
        missing_kcatkm = sum(
            1 for r in reactions if r.get("kinetics", {}).get("kcat_over_KM") is None
        )
        missing_tm = sum(1 for r in reactions if r.get("kinetics", {}).get("Tm") is None)
        missing_substrates = sum(1 for r in reactions if not r.get("substrates"))

        quality = {
            "total_variants": total,
            "complete_variants": total - missing_kcatkm - missing_tm,
            "missing_kcat_over_KM": missing_kcatkm,
            "missing_Tm": missing_tm,
            "missing_substrate": missing_substrates,
        }

        # Identify variants with most missing data
        variant_scores = []
        for r in reactions:
            missing_count = 0
            if r.get("kinetics", {}).get("kcat_over_KM") is None:
                missing_count += 1
            if r.get("kinetics", {}).get("Tm") is None:
                missing_count += 1
            if not r.get("substrates"):
                missing_count += 1

            variant_scores.append((r["enzyme_name"], missing_count))

        quality["variants_with_missing_data"] = [
            name for name, count in sorted(variant_scores, key=lambda x: x[1], reverse=True)
            if count > 0
        ]

        return quality

    def _generate_findings(
        self, reactions: List[Dict], stats: Dict, top: Dict
    ) -> List[str]:
        """Generate key findings from data.

        Args:
            reactions: List of reaction dictionaries
            stats: Statistics dictionary
            top: Top performers dictionary

        Returns:
            List of finding strings
        """
        findings = []

        # Total variants
        findings.append(f"Extracted {stats['total_variants']} enzyme variants")

        # Coverage
        kcatkm_cov = stats.get("kcat_over_KM", {}).get("coverage", 0)
        findings.append(f"kcat/KM data available for {kcatkm_cov:.1f}% of variants")

        tm_cov = stats.get("Tm", {}).get("coverage", 0)
        findings.append(f"Tm data available for {tm_cov:.1f}% of variants")

        # Top performers
        if "kcat_over_KM" in top and top["kcat_over_KM"]:
            best_name, best_val = top["kcat_over_KM"][0]
            findings.append(f"Best catalytic efficiency: {best_name} (kcat/KM = {best_val:.0f} M^-1s^-1)")

        if "Tm" in top and top["Tm"]:
            best_name, best_val = top["Tm"][0]
            findings.append(f"Highest thermal stability: {best_name} (Tm = {best_val:.1f} C)")

        # Mutations
        if stats.get("mutation_coverage", 0) > 0:
            findings.append(f"{stats.get('with_mutations', 0)} variants include mutations")

        return findings

    def _generate_markdown(self, summary: Dict) -> str:
        """Generate Markdown report.

        Args:
            summary: Summary dictionary

        Returns:
            Markdown formatted string
        """
        lines = []
        lines.append(f"# Enzyme Kinetics Extraction Summary: {summary['document_name']}")
        lines.append("")
        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Document**: {summary['document_name']}")
        lines.append(f"- **Total Variants**: {summary['overview']['total_variants']}")
        lines.append(f"- **Source**: {summary['overview']['source_file']}")
        lines.append(f"- **Generated**: {summary['timestamp']}")
        lines.append("")

        # Statistics
        lines.append("## Statistics")
        lines.append("")
        stats = summary["statistics"]
        for param in ["kcat", "Km", "kcat_over_KM", "Tm"]:
            if param in stats:
                s = stats[param]
                if s["count"] > 0:
                    lines.append(f"### {param}")
                    lines.append(f"- Coverage: {s['coverage']:.1f}% ({s['count']}/{stats['total_variants']})")
                    lines.append(f"- Range: {s['min']:.2f} - {s['max']:.2f}")
                    lines.append(f"- Mean: {s['mean']:.2f}")
                    lines.append("")

        # Top Performers
        lines.append("## Top Performers")
        lines.append("")
        top = summary["top_performers"]

        if "kcat_over_KM" in top and top["kcat_over_KM"]:
            lines.append("### Catalytic Efficiency (kcat/KM)")
            for name, val in top["kcat_over_KM"]:
                lines.append(f"- {name}: {val:.0f} M^-1s^-1")
            lines.append("")

        if "Tm" in top and top["Tm"]:
            lines.append("### Thermal Stability (Tm)")
            for name, val in top["Tm"]:
                lines.append(f"- {name}: {val:.1f} C")
            lines.append("")

        # Data Quality
        lines.append("## Data Quality")
        lines.append("")
        dq = summary["data_quality"]
        lines.append(f"- Complete variants: {dq['complete_variants']}/{dq['total_variants']}")
        lines.append(f"- Missing kcat/KM: {dq['missing_kcat_over_KM']}")
        lines.append(f"- Missing Tm: {dq['missing_Tm']}")
        lines.append("")

        # Key Findings
        lines.append("## Key Findings")
        lines.append("")
        for finding in summary["key_findings"]:
            lines.append(f"- {finding}")
        lines.append("")

        # Detailed Table
        lines.append("## Detailed Data")
        lines.append("")
        lines.append(
            "| Enzyme | Substrate | Product | kcat (s^-1) | Km (mM) | kcat/KM (M^-1s^-1) | Tm (C) | Mutations |"
        )
        lines.append(
            "|--------|-----------|---------|-------------|---------|-------------------|--------|-----------|"
        )

        for r in summary["reactions"]:
            enzyme = r["enzyme_name"]
            substrate = ", ".join(r.get("substrates", ["N/A"]))
            product = ", ".join(r.get("products", ["N/A"]))
            kcat = r.get("kinetics", {}).get("kcat")
            km = r.get("kinetics", {}).get("Km")
            kcatkm = r.get("kinetics", {}).get("kcat_over_KM")
            tm = r.get("kinetics", {}).get("Tm")
            mutations = ", ".join(r.get("mutations", [])) if r.get("mutations") else "None"

            lines.append(
                f"| {enzyme} | {substrate} | {product} | {kcat or 'N/A'} | {km or 'N/A'} | "
                f"{kcatkm or 'N/A'} | {tm or 'N/A'} | {mutations} |"
            )

        return "\n".join(lines)

    def _generate_json(self, summary: Dict) -> str:
        """Generate JSON report.

        Args:
            summary: Summary dictionary

        Returns:
            JSON formatted string
        """
        return json.dumps(summary, indent=2)

    def _generate_html(self, summary: Dict) -> str:
        """Generate HTML report.

        Args:
            summary: Summary dictionary

        Returns:
            HTML formatted string
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Enzyme Extraction Summary: {summary['document_name']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .stat {{ margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>Enzyme Kinetics Extraction Summary</h1>
    <h2>{summary['document_name']}</h2>

    <div class="overview">
        <p><strong>Total Variants:</strong> {summary['overview']['total_variants']}</p>
        <p><strong>Generated:</strong> {summary['timestamp']}</p>
    </div>

    <h2>Top Performers</h2>
"""

        # Top performers
        top = summary["top_performers"]
        if "kcat_over_KM" in top and top["kcat_over_KM"]:
            html += "<h3>Catalytic Efficiency (kcat/KM)</h3><ul>"
            for name, val in top["kcat_over_KM"][:5]:
                html += f"<li>{name}: {val:.0f} M^-1s^-1</li>"
            html += "</ul>"

        if "Tm" in top and top["Tm"]:
            html += "<h3>Thermal Stability (Tm)</h3><ul>"
            for name, val in top["Tm"][:5]:
                html += f"<li>{name}: {val:.1f} C</li>"
            html += "</ul>"

        # Key findings
        html += "<h2>Key Findings</h2><ul>"
        for finding in summary["key_findings"]:
            html += f"<li>{finding}</li>"
        html += "</ul>"

        # Detailed table
        html += """
    <h2>Detailed Data</h2>
    <table>
        <tr>
            <th>Enzyme</th>
            <th>Substrate</th>
            <th>Product</th>
            <th>kcat (s^-1)</th>
            <th>Km (mM)</th>
            <th>kcat/KM (M^-1s^-1)</th>
            <th>Tm (C)</th>
            <th>Mutations</th>
        </tr>
"""

        for r in summary["reactions"]:
            enzyme = r["enzyme_name"]
            substrate = ", ".join(r.get("substrates", ["N/A"]))
            product = ", ".join(r.get("products", ["N/A"]))
            kcat = r.get("kinetics", {}).get("kcat") or "N/A"
            km = r.get("kinetics", {}).get("Km") or "N/A"
            kcatkm = r.get("kinetics", {}).get("kcat_over_KM") or "N/A"
            tm = r.get("kinetics", {}).get("Tm") or "N/A"
            mutations = ", ".join(r.get("mutations", [])) if r.get("mutations") else "None"

            html += f"""
        <tr>
            <td>{enzyme}</td>
            <td>{substrate}</td>
            <td>{product}</td>
            <td>{kcat}</td>
            <td>{km}</td>
            <td>{kcatkm}</td>
            <td>{tm}</td>
            <td>{mutations}</td>
        </tr>"""

        html += """
    </table>
</body>
</html>
"""
        return html

    def _write_output(self, path: Path, content: str) -> None:
        """Write content to file.

        Args:
            path: Output file path
            content: Content to write
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            self.logger.info(f"Output written to {path}")
        except Exception as e:
            self.logger.error(f"Error writing output to {path}: {e}")
            raise

    def _empty_summary(self, document_name: str, extraction_path: str) -> Dict:
        """Generate empty summary when no reactions found.

        Args:
            document_name: Document name
            extraction_path: Path to extraction file

        Returns:
            Empty summary dictionary
        """
        return {
            "document_name": document_name,
            "extraction_path": extraction_path,
            "timestamp": datetime.now().isoformat(),
            "overview": {"total_variants": 0, "source_file": "Unknown"},
            "statistics": {},
            "top_performers": {},
            "data_quality": {"total_variants": 0, "complete_variants": 0},
            "key_findings": ["No enzyme variants found in extraction"],
            "reactions": [],
        }

    def _infer_products(self, reactions: List[Dict]) -> List[Dict]:
        """Infer products from substrates using biochemical knowledge.

        This method fills in missing product information based on common
        enzymatic reactions. It does not modify reactions that already
        have products specified.

        Args:
            reactions: List of enzyme reaction dictionaries

        Returns:
            List of reactions with inferred products added
        """
        # Define common substrate-product mappings
        # Based on known enzymatic reactions from biochemistry literature
        reaction_mappings = {
            # Ketosteroid isomerase reaction (listov2025)
            "5-nitrobenzisoxazole": ["2-nitrophenol"],
            # Add more mappings as needed for other papers
            # "substrate_name": ["product1", "product2"],
        }

        # Track inference statistics
        inferred_count = 0
        already_has_products = 0

        # Process each reaction
        for reaction in reactions:
            # Skip if products already exist
            if reaction.get("products") and len(reaction.get("products", [])) > 0:
                already_has_products += 1
                continue

            # Get substrates
            substrates = reaction.get("substrates", [])
            if not substrates:
                continue

            # Infer products for each substrate
            inferred_products = set()
            for substrate in substrates:
                # Check if we have a mapping for this substrate
                if substrate in reaction_mappings:
                    inferred_products.update(reaction_mappings[substrate])

            # Add inferred products to reaction
            if inferred_products:
                reaction["products"] = sorted(list(inferred_products))
                reaction["_inferred_products"] = True  # Mark as inferred
                inferred_count += 1

        # Log inference results
        if inferred_count > 0:
            self.logger.info(
                f"Inferred products for {inferred_count} reactions "
                f"({already_has_products} already had products)"
            )

        return reactions

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Generate error response.

        Args:
            message: Error message

        Returns:
            Error response dictionary
        """
        return {"status": STATUS_ERROR, "error": message}
