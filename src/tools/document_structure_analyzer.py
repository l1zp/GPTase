"""Document structure analyzer for locating tables and key sections.

This analyzer provides intelligent document structure analysis using LLM-based判断
to identify Markdown tables and key sections containing enzyme reaction data.
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
from src.tools.prompts import IMAGE_ANALYSIS_PROMPT
from src.tools.prompts import PARAGRAPH_ANALYSIS_PROMPT
from src.tools.prompts import REACTION_CHECK_PROMPT
from src.tools.prompts import TABLE_ANALYSIS_PROMPT
from src.tools.tracking_mixin import TrackingMixin

logger = logging.getLogger(__name__)

# Constants
_DEFAULT_TIMEOUT = Timeouts.DOCUMENT_ANALYSIS
_MIN_PIPE_COUNT = DocumentLimits.MIN_PIPE_COUNT
_MARKDOWN_PREVIEW_ROWS = DocumentLimits.MARKDOWN_PREVIEW_ROWS
_HTML_PREVIEW_ROWS = DocumentLimits.HTML_PREVIEW_ROWS
_KEY_PARAGRAPHS_LIMIT = DocumentLimits.KEY_PARAGRAPHS_LIMIT

# JSON parsing pattern for LLM responses
_JSON_PATTERN = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'

# HTML table parsing patterns
_HTML_TABLE_PATTERN = r'<table>(.*?)</table>'
_HTML_ROW_PATTERN = r'<tr>(.*?)</tr>'
_HTML_CELL_PATTERN = r'<td[^>]*>(.*?)</td>'

# Image parsing patterns
_IMAGE_PATTERN = r'!\[\]\(images/[^)]+\)'


class DocumentStructureAnalyzer(BaseTool, TrackingMixin):
    """Analyze document structure and locate tables and key sections.

    This tool uses LLM-based reasoning to intelligently identify:
    - Markdown tables containing enzyme reaction data
    - Key paragraphs with relevant experimental information

    Args:
        model_manager: Model instance for LLM operations (required).
        use_llm_enhancement: Whether to enhance tables with additional LLM analysis.
        agent_id: Optional agent ID for session tracking.
        session_id: Optional session ID for session tracking.
        step_id: Optional step ID for workflow step tracking.
    """

    def __init__(
        self,
        model_manager=None,
        use_llm_enhancement=False,
        agent_id=None,
        session_id=None,
        step_id=None,
    ):
        BaseTool.__init__(
            self,
            name="document_structure_analyzer",
            description="Analyze document structure to identify tables and key sections",
            timeout=_DEFAULT_TIMEOUT,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager
        self.use_llm_enhancement = use_llm_enhancement and (model_manager is not None)

    async def execute(self, text: str, source_file: str = None) -> ToolResult:
        """Analyze document structure and locate relevant sections.

        Args:
            text: Full document text to analyze.
            source_file: Optional source file path for logging.

        Returns:
            ToolResult with analysis data including tables, sections, key paragraphs, and images.
        """
        try:
            # Phase 1: Identify document structure
            sections = self._identify_sections(text)

            # Phase 2: Extract tables with LLM-based relevance判断
            tables = await self._extract_tables(text)
            logger.info("Found %d total tables (%d reaction-related)", len(tables),
                        sum(1 for t in tables if t.get('is_reaction_related')))

            # Phase 3: Optional LLM enhancement
            if self.use_llm_enhancement and tables:
                tables = await self._enhance_tables_with_llm(tables, text, source_file)

            # Phase 4: Identify key paragraphs with LLM
            key_paragraphs = await self._identify_key_paragraphs(text, sections)

            # Phase 5: Extract and analyze images with captions
            images = await self._extract_and_analyze_images(text, sections)

            logger.info(
                "Document analysis complete: %d tables, %d key paragraphs, %d images (LLM enhanced: %s)",
                len(tables), len(key_paragraphs), len(images), self.use_llm_enhancement)

            return ToolResult.success({
                "source_file": source_file or "unknown",
                "sections": sections,
                "tables": tables,
                "key_paragraphs": key_paragraphs,
                "images": images,
                "total_tables": len(tables),
                "total_key_paragraphs": len(key_paragraphs),
                "total_images": len(images),
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

                # Save previous section if exists
                if current_section:
                    current_section['end_line'] = i - 1
                    current_section['content'] = '\n'.join(lines[section_start:i])
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

    async def _extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract tables from document (both markdown and HTML).

        Args:
            text: Full document text.

        Returns:
            List of table dictionaries with structure and content.
        """
        tables = []
        tables.extend(await self._extract_markdown_tables(text))
        tables.extend(await self._extract_html_tables(text))
        return tables

    async def _extract_markdown_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract markdown tables from text using LLM for relevance判断.

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

            # Check for markdown table pattern
            if '|' in line and line.count('|') >= _MIN_PIPE_COUNT:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if '|---' in next_line or '---|' in next_line or '| :---' in next_line:
                        # Found a table - parse it
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

                        # Check if reaction-related using LLM
                        table_text = ' '.join([' '.join(row) for row in table_rows])
                        is_related = await self._is_reaction_related(table_text)

                        logger.debug("Table %d: %d rows, is_reaction_related=%s",
                                     len(tables) + 1, len(table_rows), is_related)

                        tables.append({
                            'table_number': len(tables) + 1,
                            'start_line': table_start,
                            'end_line': j - 1,
                            'type': 'markdown',
                            'headers': headers,
                            'row_count': len(table_rows),
                            'rows': table_rows[:_MARKDOWN_PREVIEW_ROWS],
                            'full_content': '\n'.join(lines[table_start:j]),
                            'is_reaction_related': is_related,
                        })
                        i = j - 1  # Skip past this table
            i += 1

        return tables

    async def _extract_html_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract HTML tables from text using LLM for relevance判断.

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

            # Check if reaction-related using LLM
            table_text = ' '.join([' '.join(row)
                                   for row in table_rows]) + ' ' + ' '.join(headers)
            is_related = await self._is_reaction_related(table_text)

            logger.debug("HTML table %d: %d rows, is_reaction_related=%s",
                         len(tables) + 1, len(table_rows), is_related)

            tables.append({
                'table_number': len(tables) + 1,
                'start_line': text[:start_pos].count('\n'),
                'end_line': text[:end_pos].count('\n'),
                'type': 'html',
                'headers': headers,
                'row_count': len(table_rows),
                'rows': table_rows[:_HTML_PREVIEW_ROWS],
                'full_content': table_content,
                'is_reaction_related': is_related,
            })

        return tables

    async def _identify_key_paragraphs(
            self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify paragraphs containing reaction-related information using LLM.

        Uses batch LLM processing to efficiently analyze all paragraphs at once.

        Args:
            text: Full document text.
            sections: List of identified sections.

        Returns:
            List of key paragraph dictionaries with content and metadata.
        """
        if not self.model_manager:
            raise ValueError(
                "model_manager is required for LLM-based paragraph identification")

        # Collect all paragraphs
        all_paragraphs = []
        for section in sections:
            section_lines = section.get('content', '').split('\n')
            paragraphs = self._extract_paragraphs_from_section(section_lines)

            for para_data in paragraphs:
                all_paragraphs.append({
                    'section':
                    section['title'],
                    'section_level':
                    section['level'],
                    'start_line':
                    section['start_line'] + para_data["start_idx"],
                    'line_count':
                    para_data["line_count"],
                    'content':
                    para_data["text"],
                })

        # Batch analyze with LLM (limit to 20 paragraphs for efficiency)
        if not all_paragraphs:
            return []

        try:
            # Always include Methods/Activity assay sections (heuristically added)
            methods_indices = []
            for i, para in enumerate(all_paragraphs):
                section_lower = para['section'].lower()
                if any(
                        keyword in section_lower for keyword in
                    ['methods', 'activity assay', 'experimental', 'kinetic parameters'
                     ]):
                    methods_indices.append(i)

            # Analyze ALL paragraphs to ensure comprehensive coverage
            key_indices = await self._llm_analyze_paragraphs(all_paragraphs)

            # Combine LLM-selected paragraphs with Methods sections (deduplicate)
            all_selected_indices = list(set(key_indices + methods_indices))

            key_paragraphs = [
                all_paragraphs[idx] for idx in all_selected_indices
                if idx < len(all_paragraphs)
            ]
            return key_paragraphs

        except Exception as e:
            logger.error("LLM paragraph identification failed: %s", e)
            raise

    def _extract_paragraphs_from_section(
            self, section_lines: List[str]) -> List[Dict[str, Any]]:
        """Extract individual paragraphs from section lines.

        A paragraph is a sequence of non-empty, non-header lines.

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

            # Check for section boundary or empty line
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

            # Start or continue paragraph
            if not in_paragraph:
                in_paragraph = True
                paragraph_start = i
                paragraph_lines = [stripped]
            else:
                paragraph_lines.append(stripped)

        # Handle last paragraph if exists
        if in_paragraph and paragraph_lines:
            paragraphs.append({
                "text": ' '.join(paragraph_lines),
                "start_idx": paragraph_start,
                "line_count": len(paragraph_lines),
            })

        return paragraphs

    async def _is_reaction_related(self, text: str) -> bool:
        """Check if text is reaction-related using LLM analysis.

        Uses LLM with confidence scoring to intelligently determine if text
        contains enzyme reaction data. Only returns True if confidence > 0.6.

        Args:
            text: Text to check (full text analyzed for accuracy).

        Returns:
            True if text contains reaction-related content with high confidence.

        Raises:
            ValueError: If model_manager is not available.
        """
        if not self.model_manager:
            raise ValueError("model_manager is required for LLM-based判断")

        try:

            prompt = REACTION_CHECK_PROMPT.format(text=text)

            messages = [{
                "role": "system",
                "content": "You are an expert scientific document analyzer."
            }, {
                "role": "user",
                "content": prompt
            }]

            response = await self.model_manager.generate(
                messages,
                **self.get_tracking_params(),
            )

            # Parse and evaluate response
            result = self._parse_json_response(response.content or "")
            if result:
                is_related = result.get("is_reaction_related", False)
                confidence = result.get("confidence", 0.0)
                reasoning = result.get("reasoning", "")

                logger.debug("LLM判断: is_related=%s, confidence=%.2f, reasoning=%s",
                             is_related, confidence, reasoning[:100])

                return is_related and confidence > 0.6

            logger.warning("LLM returned empty result, treating as not related")
            return False

        except Exception as e:
            logger.error("LLM reaction check failed: %s", e)
            raise

    async def _llm_analyze_paragraphs(self, paragraphs: List[Dict[str,
                                                                  Any]]) -> List[int]:
        """Use LLM to identify which paragraphs contain reaction-related data.

        Args:
            paragraphs: List of paragraph dictionaries.

        Returns:
            List of indices of key paragraphs.

        Raises:
            Exception: If LLM call or parsing fails.
        """

        # Format paragraphs for batch processing (full content for accuracy)
        paragraphs_text = "\n\n---\n\n".join([
            f"Paragraph {i+1} (Section: {para['section']}):\n{para['content']}"
            for i, para in enumerate(paragraphs)
        ])

        prompt = PARAGRAPH_ANALYSIS_PROMPT.format(paragraphs_text=paragraphs_text)

        messages = [{
            "role": "system",
            "content": "You are an expert scientific document analyzer."
        }, {
            "role": "user",
            "content": prompt
        }]

        response = await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),
        )
        result = self._parse_json_response(response.content or "")

        if result:
            return result.get("key_paragraph_indices", [])

        return []

    async def _enhance_tables_with_llm(self,
                                       tables: List[Dict[str, Any]],
                                       full_text: str,
                                       source_file: str = None) -> List[Dict[str, Any]]:
        """Use LLM to enhance table understanding and relevance detection.

        For each table, performs deep analysis to extract:
        - Data types present (kcat, KM, Tm, etc.)
        - Number of enzyme variants
        - Confidence score for relevance

        Args:
            tables: List of table dictionaries to enhance.
            full_text: Full document text (for context).
            source_file: Optional source file identifier.

        Returns:
            List of enhanced table dictionaries.
        """

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

                response = await self.model_manager.generate(
                    messages,
                    **self.get_tracking_params(),
                )
                analysis = self._parse_llm_table_analysis(response.content or "")

                table["llm_analysis"] = analysis
                table["description"] = analysis.get("description",
                                                    table.get("headers", []))
                table["is_reaction_related"] = analysis.get(
                    "is_reaction_related", table["is_reaction_related"])
                table["confidence"] = analysis.get("confidence", 0.5)

                # Override if LLM is very confident
                if (analysis.get("is_reaction_related")
                        and analysis.get("confidence", 0) > 0.7):
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
        return TABLE_ANALYSIS_PROMPT.format(table_summary=table_summary,
                                            source_file=source_file
                                            or "unknown document")

    def _parse_llm_table_analysis(self, llm_response: str) -> Dict[str, Any]:
        """Parse LLM response into structured analysis.

        Args:
            llm_response: Raw LLM response string.

        Returns:
            Parsed analysis dictionary.
        """
        result = self._parse_json_response(llm_response)

        if result:
            return {
                "is_reaction_related": result.get("is_reaction_related", False),
                "description": result.get("description", ""),
                "confidence": float(result.get("confidence", 0.5)),
                "data_types": result.get("data_types", []),
                "enzyme_count": result.get("enzyme_count"),
                "raw_response": llm_response
            }

        # Fallback for parsing failures
        return {
            "is_reaction_related": False,
            "description": llm_response[:200],
            "confidence": 0.0,
            "data_types": [],
            "enzyme_count": None,
            "raw_response": llm_response
        }

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response content.

        A utility method for extracting and parsing JSON from LLM responses.

        Args:
            content: Raw content from LLM response.

        Returns:
            Parsed JSON dictionary, or empty dict if parsing fails.
        """
        # Try finding JSON block first
        json_match = re.search(_JSON_PATTERN, content, re.DOTALL)
        json_str = json_match.group(0) if json_match else content

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try some basic cleanup
            try:
                # Remove markdown code blocks if present
                clean_str = re.sub(r'```json\s*', '', json_str)
                clean_str = re.sub(r'```', '', clean_str)
                clean_str = clean_str.strip()
                return json.loads(clean_str)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in LLM response")
        return {}

    async def _extract_and_analyze_images(
            self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract images and analyze their captions using LLM.

        Args:
            text: Full document text.
            sections: List of identified sections (for context).

        Returns:
            List of image dictionaries with metadata and analyzed content.
        """
        if not self.model_manager:
            logger.warning("No model_manager provided, skipping image analysis")
            return []

        try:
            # Extract image references with their captions
            images = self._extract_images_with_captions(text)

            if not images:
                logger.info("No images found in document")
                return []

            # Analyze captions with LLM
            analyzed_images = await self._analyze_image_captions_with_llm(images)

            logger.info("Analyzed %d images with captions", len(analyzed_images))
            return analyzed_images

        except Exception as e:
            logger.error("Image extraction and analysis failed: %s", e)
            return []

    def _extract_images_with_captions(self, text: str) -> List[Dict[str, Any]]:
        """Extract image references and their captions from text.

        Handles consecutive images (e.g., Fig. 3a, 3b, 3c) that share a single caption.

        Args:
            text: Full document text.

        Returns:
            List of image dictionaries with file paths and caption text.
        """
        images = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if line contains an image reference
            image_match = re.search(_IMAGE_PATTERN, line)
            if image_match:
                # Start of an image group - collect nearby images
                image_group = []
                group_end = i

                # Look ahead up to 10 lines to collect all images in the group
                for j in range(i, min(i + 10, len(lines))):
                    if re.search(_IMAGE_PATTERN, lines[j]):
                        current_line = lines[j]
                        img_match = re.search(_IMAGE_PATTERN, current_line)
                        image_path = img_match.group(0)

                        # Check if caption starts on the same line (after the image)
                        same_line_caption = current_line[img_match.end():].strip()

                        image_group.append({
                            'line_number': j,
                            'image_path': image_path,
                            'same_line_caption': same_line_caption,
                        })
                        group_end = j + 1
                    elif j > i + 3:
                        # If we haven't found an image in 3 lines, stop looking
                        break

                # Now extract caption for the entire group
                # Start with any same-line caption from the last image
                caption_lines = []
                if image_group and image_group[-1].get('same_line_caption'):
                    caption_lines.append(image_group[-1]['same_line_caption'])

                # Continue collecting caption from following lines
                for j in range(group_end, min(group_end + 10, len(lines))):
                    next_line = lines[j].strip()

                    # Stop at empty line, new section, or another image
                    if not next_line or next_line.startswith('#'):
                        break
                    if re.search(_IMAGE_PATTERN, next_line):
                        break

                    # Collect caption text
                    caption_lines.append(next_line)

                # Join caption lines
                caption = ' '.join(caption_lines).strip() if caption_lines else ""

                # Extract figure number if present (e.g., "Fig. 1", "Figure 2")
                figure_match = re.search(r'Fig\.?\s*(\d+)[\s\|]|Figure\s*(\d+)',
                                         caption, re.IGNORECASE)
                figure_number = None
                if figure_match:
                    figure_number = figure_match.group(1) or figure_match.group(2)

                # Add all images in the group with the shared caption
                for img_data in image_group:
                    images.append({
                        'image_number': len(images) + 1,
                        'line_number': img_data['line_number'],
                        'image_path': img_data['image_path'],
                        'caption': caption,
                        'figure_number': figure_number,
                    })

                # Move to after the image group
                i = group_end
            else:
                i += 1

        return images

    async def _analyze_image_captions_with_llm(
            self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use LLM to analyze image captions and extract key information.

        Args:
            images: List of image dictionaries with captions.

        Returns:
            List of enhanced image dictionaries with LLM analysis.
        """

        analyzed_images = []

        for image in images:
            caption = image.get('caption', '')
            if not caption:
                # No caption to analyze
                image['analysis'] = {
                    'topics': [],
                    'description': 'No caption available',
                    'is_relevant': False,
                }
                analyzed_images.append(image)
                continue

            try:
                prompt = IMAGE_ANALYSIS_PROMPT.format(figure_number=image.get(
                    'figure_number', 'N/A'),
                                                      caption=caption)

                messages = [{
                    "role":
                    "system",
                    "content":
                    "You are an expert scientific document analyzer specializing in biochemistry and enzyme design."
                }, {
                    "role": "user",
                    "content": prompt
                }]

                response = await self.model_manager.generate(
                    messages,
                    **self.get_tracking_params(),
                )

                analysis = self._parse_json_response(response.content or "")

                if analysis:
                    image['analysis'] = {
                        'topics': analysis.get('topics', []),
                        'description': analysis.get('description', ''),
                        'is_relevant': analysis.get('is_relevant', False),
                        'enzyme_variants': analysis.get('enzyme_variants', []),
                        'data_types': analysis.get('data_types', []),
                        'key_findings': analysis.get('key_findings', []),
                    }
                else:
                    # Fallback if parsing fails
                    image['analysis'] = {
                        'topics': [],
                        'description': caption[:200],
                        'is_relevant': False,
                        'enzyme_variants': [],
                        'data_types': [],
                        'key_findings': [],
                    }

            except Exception as e:
                logger.warning("LLM analysis failed for image %s: %s",
                               image.get('image_number'), e)
                image['analysis'] = {
                    'topics': [],
                    'description': f"Analysis failed: {str(e)}",
                    'is_relevant': False,
                    'enzyme_variants': [],
                    'data_types': [],
                    'key_findings': [],
                }

            analyzed_images.append(image)

        return analyzed_images

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
    comprehensive extraction of all enzyme variants. Also includes
    relevant image captions for additional context.

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

    # Add all key paragraphs selected by LLM (no artificial limit)
    for para in analysis.get('key_paragraphs', []):
        relevant_parts.append(f"Section: {para['section']}")
        relevant_parts.append(para['content'])
        relevant_parts.append("")

    # Add relevant image captions
    for image in analysis.get('images', []):
        analysis_data = image.get('analysis', {})
        if analysis_data.get('is_relevant', False):
            relevant_parts.append(
                f"Figure {image.get('figure_number', image.get('image_number'))}:")
            relevant_parts.append(image.get('caption', ''))
            if analysis_data.get('description'):
                relevant_parts.append(f"Summary: {analysis_data['description']}")
            relevant_parts.append("")

    return '\n'.join(relevant_parts)
