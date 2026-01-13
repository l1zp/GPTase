"""
Document structure analyzer for locating tables and key sections.
"""

import re
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


class DocumentStructureAnalyzer(BaseTool):
    """Analyze document structure and locate tables and key sections.

    Can optionally use LLM to enhance table recognition and understanding.
    """

    def __init__(self, model_manager=None, use_llm_enhancement=False):
        super().__init__(
            name="document_structure_analyzer",
            description="Analyze document structure to identify tables and key sections",
            timeout=30,
        )
        self.model_manager = model_manager
        self.use_llm_enhancement = use_llm_enhancement and (model_manager is not None)

    async def execute(self,
                      text: str,
                      source_file: str = None) -> ToolResult:
        """Analyze document structure and locate relevant sections."""
        try:
            sections = self._identify_sections(text)
            tables = self._extract_tables(text)

            # Use LLM to enhance table understanding if enabled
            if self.use_llm_enhancement and tables:
                tables = await self._enhance_tables_with_llm(tables, text, source_file)

            key_paragraphs = self._identify_key_paragraphs(text, sections)

            # Store analysis results
            analysis = {
                "source_file": source_file or "unknown",
                "sections": sections,
                "tables": tables,
                "key_paragraphs": key_paragraphs,
                "total_tables": len(tables),
                "total_key_paragraphs": len(key_paragraphs),
                "llm_enhanced": self.use_llm_enhancement,
            }

            logger.info(f"Document analysis complete: {len(tables)} tables, "
                       f"{len(key_paragraphs)} key paragraphs identified "
                       f"(LLM enhanced: {self.use_llm_enhancement})")

            return ToolResult.success(analysis)

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return ToolResult.error(str(e))

    def _identify_sections(self, text: str) -> List[Dict[str, Any]]:
        """Identify document sections based on headers."""
        sections = []
        lines = text.split('\n')

        current_section = None
        section_start = 0

        for i, line in enumerate(lines):
            # Check for markdown headers (# ## ###)
            if line.strip().startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.strip('#').strip()

                # Save previous section
                if current_section:
                    current_section['end_line'] = i - 1
                    current_section['content'] = '\n'.join(
                        lines[section_start:i]
                    )
                    sections.append(current_section)

                # Start new section
                current_section = {
                    'line_number': i,
                    'level': level,
                    'title': title,
                    'start_line': i,
                }
                section_start = i

        # Save last section
        if current_section:
            current_section['end_line'] = len(lines) - 1
            current_section['content'] = '\n'.join(lines[section_start:])
            sections.append(current_section)

        return sections

    def _extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract markdown and HTML tables from document."""
        tables = []
        lines = text.split('\n')

        # First, extract markdown tables
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Detect potential table (contains |)
            if '|' in line and line.count('|') >= 2:
                # Check if next line is separator (contains |---|)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if '|---' in next_line or '---|' in next_line or '| :---' in next_line:
                        # Found table start
                        table_start = i
                        headers = [cell.strip() for cell in line.split('|')[1:-1]]

                        # Find table end
                        table_rows = []
                        j = i + 2  # Skip separator line
                        while j < len(lines):
                            row_line = lines[j].strip()
                            if '|' in row_line and row_line.count('|') >= 2:
                                cells = [cell.strip() for cell in row_line.split('|')[1:-1]]
                                table_rows.append(cells)
                                j += 1
                            else:
                                break

                        # Store table info
                        table_info = {
                            'table_number': len(tables) + 1,
                            'start_line': table_start,
                            'end_line': j - 1,
                            'type': 'markdown',
                            'headers': headers,
                            'row_count': len(table_rows),
                            'rows': table_rows[:5],  # Store first 5 rows as preview
                            'full_content': '\n'.join(lines[table_start:j]),
                        }

                        # Detect if table contains reaction-related keywords
                        table_text = ' '.join([' '.join(row) for row in table_rows])
                        table_info['is_reaction_related'] = self._is_reaction_related(table_text)

                        tables.append(table_info)
                        i = j - 1

            i += 1

        # Second, extract HTML tables
        import re
        html_table_pattern = r'<table>(.*?)</table>'
        html_matches = re.finditer(html_table_pattern, text, re.DOTALL)

        for match in html_matches:
            table_content = match.group(0)

            # Find line numbers for HTML table
            start_pos = match.start()
            end_pos = match.end()
            start_line = text[:start_pos].count('\n')
            end_line = text[:end_pos].count('\n')

            # Extract table structure
            rows = re.findall(r'<tr>(.*?)</tr>', table_content, re.DOTALL)
            if not rows:
                continue

            # Parse headers (first row)
            headers = []
            first_row_cells = re.findall(r'<td[^>]*>(.*?)</td>', rows[0], re.DOTALL)
            if first_row_cells:
                # Clean HTML tags and whitespace
                headers = [re.sub(r'<[^>]+>', '', cell).strip() for cell in first_row_cells]

            # Parse data rows (skip first row if it's header, or keep all)
            table_rows = []
            for row in rows[1:]:  # Skip header row
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if cells:
                    cleaned_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
                    table_rows.append(cleaned_cells)

            # Store table info
            table_info = {
                'table_number': len(tables) + 1,
                'start_line': start_line,
                'end_line': end_line,
                'type': 'html',
                'headers': headers,
                'row_count': len(table_rows),
                'rows': table_rows[:10],  # Store first 10 rows as preview
                'full_content': table_content,
            }

            # Detect if table contains reaction-related keywords
            table_text = ' '.join([' '.join(row) for row in table_rows])
            table_text += ' ' + ' '.join(headers)
            table_info['is_reaction_related'] = self._is_reaction_related(table_text)

            tables.append(table_info)

        return tables

    def _identify_key_paragraphs(self,
                                  text: str,
                                  sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify paragraphs containing reaction-related information."""
        keywords = [
            # Kinetic parameters
            'kcat', 'k_cat', 'km', 'k_m', 'vmax', 'v_max',
            'catalytic efficiency', 'turnover', 'michaelis',
            # Units
            'm-1', 's-1', 'μmol', 'mmol', 'μm',
            # Reaction info
            'substrate', 'product', 'enzyme', 'catalyst',
            'temperature', 'ph', 'buffer', 'conditions',
            # Values
            'efficiency', 'rate', 'activity', 'kinetics',
            'mutant', 'variant', 'wild-type',
        ]

        key_paragraphs = []
        lines = text.split('\n')

        for section in sections:
            section_lines = section.get('content', '').split('\n')
            in_paragraph = False
            paragraph_start = 0
            paragraph_lines = []

            for i, line in enumerate(section_lines):
                stripped = line.strip()

                # Skip headers and empty lines
                if stripped.startswith('#') or not stripped:
                    if in_paragraph and paragraph_lines:
                        # End of paragraph, check if it's relevant
                        paragraph_text = ' '.join(paragraph_lines)
                        if self._contains_keywords(paragraph_text, keywords):
                            key_paragraphs.append({
                                'section': section['title'],
                                'section_level': section['level'],
                                'start_line': section['start_line'] + paragraph_start,
                                'line_count': len(paragraph_lines),
                                'content': paragraph_text,
                                'keywords_found': self._extract_found_keywords(
                                    paragraph_text, keywords
                                ),
                            })
                    in_paragraph = False
                    paragraph_lines = []
                    continue

                # Build paragraph
                if not in_paragraph:
                    in_paragraph = True
                    paragraph_start = i
                    paragraph_lines = [stripped]
                else:
                    paragraph_lines.append(stripped)

            # Check last paragraph in section
            if in_paragraph and paragraph_lines:
                paragraph_text = ' '.join(paragraph_lines)
                if self._contains_keywords(paragraph_text, keywords):
                    key_paragraphs.append({
                        'section': section['title'],
                        'section_level': section['level'],
                        'start_line': section['start_line'] + paragraph_start,
                        'line_count': len(paragraph_lines),
                        'content': paragraph_text,
                        'keywords_found': self._extract_found_keywords(
                            paragraph_text, keywords
                        ),
                    })

        return key_paragraphs

    def _is_reaction_related(self, text: str) -> bool:
        """Check if text is reaction-related."""
        keywords = ['kcat', 'km', 'substrate', 'product', 'enzyme',
                   'efficiency', 'kinetics', 'catalytic', 'reaction']
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords."""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _extract_found_keywords(self,
                                 text: str,
                                 keywords: List[str]) -> List[str]:
        """Extract which keywords were found in text."""
        text_lower = text.lower()
        found = []
        for kw in keywords:
            if kw.lower() in text_lower:
                found.append(kw)
        return found

    async def _enhance_tables_with_llm(self, tables: List[Dict[str, Any]], full_text: str, source_file: str = None) -> List[Dict[str, Any]]:
        """Use LLM to enhance table understanding and relevance detection."""
        enhanced_tables = []

        for table in tables:
            # Prepare table summary for LLM
            table_summary = self._create_table_summary(table)

            # Build LLM prompt
            prompt = self._build_table_analysis_prompt(table_summary, source_file)

            try:
                # Call LLM
                from src.models.types import ModelRole
                messages = [
                    {
                        "role": "system",
                        "content": "You are an expert scientific document analyzer. Analyze tables and determine their relevance to enzyme reaction data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

                response = await self.model_manager.generate(messages, role=ModelRole.GENERAL)
                analysis = self._parse_llm_table_analysis(response.content or "")

                # Enhance table info with LLM insights
                table["llm_analysis"] = analysis
                table["description"] = analysis.get("description", table.get("headers", []))
                table["is_reaction_related"] = analysis.get("is_reaction_related", table["is_reaction_related"])
                table["confidence"] = analysis.get("confidence", 0.5)

                # If LLM detects it's reaction-related with high confidence, override keyword detection
                if analysis.get("is_reaction_related") and analysis.get("confidence", 0) > 0.7:
                    table["is_reaction_related"] = True

            except Exception as e:
                logger.warning(f"LLM enhancement failed for table {table['table_number']}: {e}")
                # Keep original table info if LLM fails
                table["llm_analysis"] = {"error": str(e)}
                table["description"] = table.get("headers", [])
                table["confidence"] = 0.5

            enhanced_tables.append(table)

        return enhanced_tables

    def _create_table_summary(self, table: Dict[str, Any]) -> str:
        """Create a concise summary of the table for LLM analysis."""
        headers = table.get("headers", [])
        rows = table.get("rows", [])[:5]  # First 5 rows for summary

        summary_parts = [
            f"Table {table['table_number']}:",
            f"Type: {table['type']}",
            f"Headers: {', '.join(headers)}",
            f"Total rows: {table['row_count']}",
            "\nSample rows:"
        ]

        for i, row in enumerate(rows[:3], 1):
            if row:
                row_text = " | ".join(str(cell)[:30] for cell in row)
                summary_parts.append(f"  Row {i}: {row_text}")

        return "\n".join(summary_parts)

    def _build_table_analysis_prompt(self, table_summary: str, source_file: str = None) -> str:
        """Build prompt for LLM table analysis."""
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
        """Parse LLM response into structured analysis."""
        import json
        import re

        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
                return {
                    "is_reaction_related": analysis.get("is_reaction_related", False),
                    "description": analysis.get("description", ""),
                    "confidence": float(analysis.get("confidence", 0.5)),
                    "data_types": analysis.get("data_types", []),
                    "enzyme_count": analysis.get("enzyme_count", None),
                    "raw_response": llm_response
                }
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        # Fallback: try to extract basic info from text
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


def save_document_analysis(analysis: Dict[str, Any],
                          output_dir: Path) -> Path:
    """Save document analysis to JSON file."""
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    source_name = Path(analysis.get('source_file', 'unknown')).stem
    output_file = output_dir / f"{source_name}_structure_analysis.json"

    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)

    logger.info(f"Document analysis saved to: {output_file}")
    return output_file


def get_relevant_content_for_extraction(analysis: Dict[str, Any]) -> str:
    """Extract and combine relevant content for LLM extraction.

    Includes all reaction-related tables without row limits to ensure
    comprehensive extraction of all enzyme variants.
    """
    relevant_parts = []
    import re

    # Add reaction-related tables (ALL rows, no limit)
    for table in analysis.get('tables', []):
        if table.get('is_reaction_related', False):
            relevant_parts.append(f"Table {table['table_number']}:")

            # Use full table content without limiting rows
            table_content = table.get('full_content', '')
            relevant_parts.append(table_content)
            relevant_parts.append("")

    # Add key paragraphs (limited to first 20 to reduce tokens)
    key_paras = analysis.get('key_paragraphs', [])[:20]
    for para in key_paras:
        relevant_parts.append(f"Section: {para['section']}")
        relevant_parts.append(para['content'])
        relevant_parts.append("")

    return '\n'.join(relevant_parts)
