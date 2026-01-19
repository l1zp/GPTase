"""
Document structure analyzer for locating tables and key sections.
"""

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List

from src.core.constants import DocumentLimits
from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# Constants - use centralized timeout and document limits
_DEFAULT_TIMEOUT = Timeouts.DOCUMENT_ANALYSIS
_MIN_PIPE_COUNT = DocumentLimits.MIN_PIPE_COUNT
_HTML_TABLE_PATTERN = r'<table>(.*?)</table>'
_HTML_ROW_PATTERN = r'<tr>(.*?)</tr>'
_HTML_CELL_PATTERN = r'<td[^>]*>(.*?)</td>'

# Kinetic keywords for identifying relevant content
_KINETIC_KEYWORDS = [
    # Kinetic parameters
    "kcat",
    "k_cat",
    "km",
    "k_m",
    "vmax",
    "v_max",
    "catalytic efficiency",
    "turnover",
    "michaelis",
    # Units
    "m-1",
    "s-1",
    "μmol",
    "mmol",
    "μm",
    # Reaction info
    "substrate",
    "product",
    "enzyme",
    "catalyst",
    "temperature",
    "ph",
    "buffer",
    "conditions",
    # Values
    "efficiency",
    "rate",
    "activity",
    "kinetics",
    "mutant",
    "variant",
    "wild-type",
]

# Keywords for quick reaction-related check
_REACTION_KEYWORDS_SHORT = [
    "kcat",
    "km",
    "substrate",
    "product",
    "enzyme",
    "efficiency",
    "kinetics",
    "catalytic",
    "reaction",
]

# Row preview limits - use centralized document limits
_MARKDOWN_PREVIEW_ROWS = DocumentLimits.MARKDOWN_PREVIEW_ROWS
_HTML_PREVIEW_ROWS = DocumentLimits.HTML_PREVIEW_ROWS
_KEY_PARAGRAPHS_LIMIT = DocumentLimits.KEY_PARAGRAPHS_LIMIT


class DocumentStructureAnalyzer(BaseTool):
    """Analyze document structure and locate tables and key sections.

    Can optionally use LLM to enhance table recognition and understanding.
    """

    def __init__(self, model_manager=None, use_llm_enhancement=False):
        super().__init__(
            name="document_structure_analyzer",
            description="Analyze document structure to identify tables and key sections",
            timeout=_DEFAULT_TIMEOUT,
        )
        self.model_manager = model_manager
        self.use_llm_enhancement = use_llm_enhancement and (model_manager is not None)

    async def execute(self, text: str, source_file: str = None) -> ToolResult:
        """Analyze document structure and locate relevant sections.

        Args:
            text: Full document text to analyze.
            source_file: Optional source file path for logging.

        Returns:
            ToolResult with analysis data including tables, sections, and key paragraphs.
        """
        try:
            sections = self._identify_sections(text)
            tables = self._extract_tables(text)

            if self.use_llm_enhancement and tables:
                tables = await self._enhance_tables_with_llm(tables, text, source_file)

            key_paragraphs = self._identify_key_paragraphs(text, sections)

            logger.info(
                "Document analysis complete: %d tables, %d key paragraphs (LLM enhanced: %s)",
                len(tables), len(key_paragraphs), self.use_llm_enhancement)

            return ToolResult.success({
                "source_file": source_file or "unknown",
                "sections": sections,
                "tables": tables,
                "key_paragraphs": key_paragraphs,
                "total_tables": len(tables),
                "total_key_paragraphs": len(key_paragraphs),
                "llm_enhanced": self.use_llm_enhancement,
            })

        except Exception as e:
            logger.error("Document analysis failed: %s", e)
            return ToolResult.error(str(e))

    def _identify_sections(self, text: str) -> List[Dict[str, Any]]:
        """Identify document sections based on markdown headers.

        Args:
            text: Full document text.

        Returns:
            List of section dictionaries with line numbers and content.
        """
        sections = []
        lines = text.split('\n')

        current_section = None
        section_start = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.strip('#').strip()

                if current_section:
                    current_section['end_line'] = i - 1
                    current_section['content'] = '\n'.join(lines[section_start:i])
                    sections.append(current_section)

                current_section = {
                    'line_number': i,
                    'level': level,
                    'title': title,
                    'start_line': i,
                }
                section_start = i

        if current_section:
            current_section['end_line'] = len(lines) - 1
            current_section['content'] = '\n'.join(lines[section_start:])
            sections.append(current_section)

        return sections

    def _extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract markdown and HTML tables from document.

        Args:
            text: Full document text.

        Returns:
            List of table dictionaries with structure and content.
        """
        tables = []
        tables.extend(self._extract_markdown_tables(text))
        tables.extend(self._extract_html_tables(text))
        return tables

    def _extract_markdown_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract markdown tables from text.

        Args:
            text: Full document text.

        Returns:
            List of markdown table dictionaries.
        """
        tables = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if '|' in line and line.count('|') >= _MIN_PIPE_COUNT:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if '|---' in next_line or '---|' in next_line or '| :---' in next_line:
                        table_start = i
                        headers = [cell.strip() for cell in line.split('|')[1:-1]]

                        # Parse table rows
                        table_rows = []
                        j = i + 2
                        while j < len(lines):
                            row_line = lines[j].strip()
                            if '|' in row_line and row_line.count(
                                    '|') >= _MIN_PIPE_COUNT:
                                cells = [
                                    cell.strip() for cell in row_line.split('|')[1:-1]
                                ]
                                table_rows.append(cells)
                                j += 1
                            else:
                                break

                        table_text = ' '.join([' '.join(row) for row in table_rows])

                        tables.append({
                            'table_number':
                            len(tables) + 1,
                            'start_line':
                            table_start,
                            'end_line':
                            j - 1,
                            'type':
                            'markdown',
                            'headers':
                            headers,
                            'row_count':
                            len(table_rows),
                            'rows':
                            table_rows[:_MARKDOWN_PREVIEW_ROWS],
                            'full_content':
                            '\n'.join(lines[table_start:j]),
                            'is_reaction_related':
                            self._is_reaction_related(table_text),
                        })
                        i = j - 1
            i += 1

        return tables

    def _extract_html_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract HTML tables from text.

        Args:
            text: Full document text.

        Returns:
            List of HTML table dictionaries.
        """
        tables = []
        html_matches = re.finditer(_HTML_TABLE_PATTERN, text, re.DOTALL)

        for match in html_matches:
            table_content = match.group(0)
            start_pos = match.start()
            end_pos = match.end()

            rows = re.findall(_HTML_ROW_PATTERN, table_content, re.DOTALL)
            if not rows:
                continue

            # Parse headers from first row
            first_row_cells = re.findall(_HTML_CELL_PATTERN, rows[0], re.DOTALL)
            headers = [re.sub(r'<[^>]+>', '', cell).strip() for cell in first_row_cells]

            # Parse data rows
            table_rows = []
            for row in rows[1:]:
                cells = re.findall(_HTML_CELL_PATTERN, row, re.DOTALL)
                if cells:
                    cleaned_cells = [
                        re.sub(r'<[^>]+>', '', cell).strip() for cell in cells
                    ]
                    table_rows.append(cleaned_cells)

            table_text = ' '.join([' '.join(row)
                                   for row in table_rows]) + ' ' + ' '.join(headers)

            tables.append({
                'table_number': len(tables) + 1,
                'start_line': text[:start_pos].count('\n'),
                'end_line': text[:end_pos].count('\n'),
                'type': 'html',
                'headers': headers,
                'row_count': len(table_rows),
                'rows': table_rows[:_HTML_PREVIEW_ROWS],
                'full_content': table_content,
                'is_reaction_related': self._is_reaction_related(table_text),
            })

        return tables

    def _identify_key_paragraphs(
            self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify paragraphs containing reaction-related information.

        Args:
            text: Full document text.
            sections: List of identified sections.

        Returns:
            List of key paragraph dictionaries with content and metadata.
        """
        key_paragraphs = []

        for section in sections:
            section_lines = section.get('content', '').split('\n')
            paragraphs = self._extract_paragraphs_from_section(section_lines)

            for paragraph_data in paragraphs:
                paragraph_text = paragraph_data["text"]
                if self._contains_keywords(paragraph_text, _KINETIC_KEYWORDS):
                    key_paragraphs.append({
                        'section':
                        section['title'],
                        'section_level':
                        section['level'],
                        'start_line':
                        section['start_line'] + paragraph_data["start_idx"],
                        'line_count':
                        paragraph_data["line_count"],
                        'content':
                        paragraph_text,
                        'keywords_found':
                        self._extract_found_keywords(paragraph_text, _KINETIC_KEYWORDS),
                    })

        return key_paragraphs

    def _extract_paragraphs_from_section(
            self, section_lines: List[str]) -> List[Dict[str, Any]]:
        """Extract individual paragraphs from section lines.

        Args:
            section_lines: List of lines in a section.

        Returns:
            List of paragraph data dictionaries.
        """
        paragraphs = []
        in_paragraph = False
        paragraph_start = 0
        paragraph_lines = []

        for i, line in enumerate(section_lines):
            stripped = line.strip()

            if stripped.startswith('#') or not stripped:
                if in_paragraph and paragraph_lines:
                    paragraphs.append({
                        "text": ' '.join(paragraph_lines),
                        "start_idx": paragraph_start,
                        "line_count": len(paragraph_lines),
                    })
                in_paragraph = False
                paragraph_lines = []
                continue

            if not in_paragraph:
                in_paragraph = True
                paragraph_start = i
                paragraph_lines = [stripped]
            else:
                paragraph_lines.append(stripped)

        if in_paragraph and paragraph_lines:
            paragraphs.append({
                "text": ' '.join(paragraph_lines),
                "start_idx": paragraph_start,
                "line_count": len(paragraph_lines),
            })

        return paragraphs

    def _is_reaction_related(self, text: str) -> bool:
        """Check if text is reaction-related using short keyword list.

        Args:
            text: Text to check.

        Returns:
            True if text contains reaction-related keywords.
        """
        text_lower = text.lower()
        return any(kw in text_lower for kw in _REACTION_KEYWORDS_SHORT)

    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords.

        Args:
            text: Text to check.
            keywords: List of keywords to search for.

        Returns:
            True if any keyword is found.
        """
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _extract_found_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Extract which keywords were found in text.

        Args:
            text: Text to search.
            keywords: List of keywords to look for.

        Returns:
            List of found keywords.
        """
        text_lower = text.lower()
        return [kw for kw in keywords if kw.lower() in text_lower]

    async def _enhance_tables_with_llm(self,
                                       tables: List[Dict[str, Any]],
                                       full_text: str,
                                       source_file: str = None) -> List[Dict[str, Any]]:
        """Use LLM to enhance table understanding and relevance detection.

        Args:
            tables: List of table dictionaries to enhance.
            full_text: Full document text (for context).
            source_file: Optional source file identifier.

        Returns:
            List of enhanced table dictionaries.
        """
        from src.models.types import ModelRole

        enhanced_tables = []

        for table in tables:
            table_summary = self._create_table_summary(table)
            prompt = self._build_table_analysis_prompt(table_summary, source_file)

            try:
                messages = [{
                    "role":
                    "system",
                    "content":
                    "You are an expert scientific document analyzer. "
                    "Analyze tables and determine their relevance to enzyme reaction data."
                }, {
                    "role": "user",
                    "content": prompt
                }]

                response = await self.model_manager.generate(messages,
                                                             role=ModelRole.GENERAL)
                analysis = self._parse_llm_table_analysis(response.content or "")

                table["llm_analysis"] = analysis
                table["description"] = analysis.get("description",
                                                    table.get("headers", []))
                table["is_reaction_related"] = analysis.get(
                    "is_reaction_related", table["is_reaction_related"])
                table["confidence"] = analysis.get("confidence", 0.5)

                # Override keyword detection if LLM is confident
                if analysis.get("is_reaction_related") and analysis.get(
                        "confidence", 0) > 0.7:
                    table["is_reaction_related"] = True

            except Exception as e:
                logger.warning("LLM enhancement failed for table %s: %s",
                               table['table_number'], e)
                table["llm_analysis"] = {"error": str(e)}
                table["description"] = table.get("headers", [])
                table["confidence"] = 0.5

            enhanced_tables.append(table)

        return enhanced_tables

    def _create_table_summary(self, table: Dict[str, Any]) -> str:
        """Create a concise summary of the table for LLM analysis.

        Args:
            table: Table dictionary.

        Returns:
            Formatted table summary string.
        """
        headers = table.get("headers", [])
        rows = table.get("rows", [])[:3]

        summary_parts = [
            f"Table {table['table_number']}:", f"Type: {table['type']}",
            f"Headers: {', '.join(headers)}", f"Total rows: {table['row_count']}",
            "\nSample rows:"
        ]

        for i, row in enumerate(rows, 1):
            if row:
                row_text = " | ".join(str(cell)[:30] for cell in row)
                summary_parts.append(f"  Row {i}: {row_text}")

        return "\n".join(summary_parts)

    def _build_table_analysis_prompt(self,
                                     table_summary: str,
                                     source_file: str = None) -> str:
        """Build prompt for LLM table analysis.

        Args:
            table_summary: Table summary string.
            source_file: Optional source file identifier.

        Returns:
            Formatted prompt string.
        """
        return f"""Analyze this table and determine if it contains enzyme reaction data.

{table_summary}

Context: {source_file or "unknown document"}

Please analyze and return a JSON object with:
{{
    "is_reaction_related": true/false,
    "description": "Brief description of what this table contains",
    "confidence": 0.0-1.0,
    "data_types": ["list of data types found, e.g., 'kcat', 'KM', 'Tm', etc."],
    "enzyme_count": "approximate number of enzyme variants if applicable"
}}

Focus on tables containing:
- Kinetic parameters (kcat, KM, Vmax, kcat/KM)
- Enzyme variants or mutants
- Temperature (Tm), pH, buffer conditions
- Catalytic efficiency or activity data

Return ONLY valid JSON, no markdown."""

    def _parse_llm_table_analysis(self, llm_response: str) -> Dict[str, Any]:
        """Parse LLM response into structured analysis.

        Args:
            llm_response: Raw LLM response string.

        Returns:
            Parsed analysis dictionary.
        """
        try:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response,
                                   re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
                return {
                    "is_reaction_related": analysis.get("is_reaction_related", False),
                    "description": analysis.get("description", ""),
                    "confidence": float(analysis.get("confidence", 0.5)),
                    "data_types": analysis.get("data_types", []),
                    "enzyme_count": analysis.get("enzyme_count"),
                    "raw_response": llm_response
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse LLM response: %s", e)

        # Fallback to basic analysis
        return {
            "is_reaction_related": self._is_reaction_related(llm_response),
            "description": llm_response[:200],
            "confidence": 0.5,
            "data_types": [],
            "enzyme_count": None,
            "raw_response": llm_response
        }

    def get_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Document text to analyze"
                },
                "source_file": {
                    "type": "string",
                    "description": "Source file path (optional)"
                }
            },
            "required": ["text"]
        }


def save_document_analysis(analysis: Dict[str, Any], output_dir: Path) -> Path:
    """Save document analysis to JSON file.

    Args:
        analysis: Analysis data dictionary.
        output_dir: Directory to save the analysis file.

    Returns:
        Path to the saved analysis file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    source_name = Path(analysis.get('source_file', 'unknown')).stem
    output_file = output_dir / f"{source_name}_structure_analysis.json"

    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)

    logger.info("Document analysis saved to: %s", output_file)
    return output_file


def get_relevant_content_for_extraction(analysis: Dict[str, Any]) -> str:
    """Extract and combine relevant content for LLM extraction.

    Includes all reaction-related tables without row limits to ensure
    comprehensive extraction of all enzyme variants.

    Args:
        analysis: Document analysis dictionary.

    Returns:
        Combined relevant content as a string.
    """
    relevant_parts = []

    # Add all reaction-related tables with full content
    for table in analysis.get('tables', []):
        if table.get('is_reaction_related', False):
            relevant_parts.append(f"Table {table['table_number']}:")
            relevant_parts.append(table.get('full_content', ''))
            relevant_parts.append("")

    # Add key paragraphs (limited to reduce tokens)
    for para in analysis.get('key_paragraphs', [])[:_KEY_PARAGRAPHS_LIMIT]:
        relevant_parts.append(f"Section: {para['section']}")
        relevant_parts.append(para['content'])
        relevant_parts.append("")

    return '\n'.join(relevant_parts)
