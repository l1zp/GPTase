"""LLM-driven Enzyme Reaction Extractor.

Uses a Large Language Model via Model to parse literature-style content
and return structured JSON conforming to the ExtractionResult schema defined in
`markdown_enzyme_parser.py`. Includes optimized prompts for context-rich parsing.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from pydantic import ValidationError

from src.agents.base import BaseAgent
from src.agents.specialized.enzyme_extraction_utils import create_error_response
from src.agents.specialized.enzyme_extraction_utils import extract_pdb_ids_from_text
from src.agents.specialized.enzyme_extraction_utils import merge_pdb_ids
from src.agents.specialized.enzyme_extraction_utils import sanitize_reaction_list_fields
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.models.model import Model
from src.models.types import ModelRole
from src.tools.document_structure_analyzer import DocumentStructureAnalyzer
from src.tools.document_structure_analyzer import get_relevant_content_for_extraction
from src.tools.document_structure_analyzer import save_document_analysis
from src.tools.markdown_enzyme_parser import ExtractionResult

logger = logging.getLogger(__name__)

# Source file identifiers
_INLINE_SOURCE_FILE = "inline_text.md"
_UNKNOWN_SOURCE_FILE = "unknown.md"

# Document source types
_SOURCE_TYPE_TEXT = "text"
_SOURCE_TYPE_FILE = "file"
_SOURCE_TYPE_URL = "url"

SYSTEM_PROMPT = (
    "You are an expert biochemical text parser. Extract enzyme reaction data "
    "from academic-style text and return STRICT JSON that conforms to the following structure. "
    "No markdown, no commentary, no trailing commas. If a field is unknown, use null or an empty list. "
    "Schema (examples of keys and types, not values): "
    '{"reactions": [{"source_file": string|null, "enzyme_name": string|null, "substrates": [string], '
    '"products": [string], "conditions": {"temperature": string|null, "pH": string|null, "buffer": string|null, "time": string|null, "notes": string|null}, '
    '"kinetics": {"Km": number|null, "Km_unit": string|null, "Vmax": number|null, "Vmax_unit": string|null, '
    '"kcat": number|null, "kcat_unit": string|null, "kcat_over_KM": number|null, "kcat_over_KM_unit": string|null, '
    '"Tm": number|null, "Tm_unit": string|null}, "yield_percent": number|null, "citations": [string], '
    '"pdb_ids": [string]}], "pipeline": {"steps": [{"name": string, "description": string, "status": string}], "validations": [string], "errors": [string]}}. '
    "CRITICAL RULES: "
    "1) COMPREHENSIVE EXTRACTION: Extract EVERY enzyme variant from tables, not just 'important' ones. "
    "If a table has N rows, you MUST extract all N variants. Each row is a separate reaction entry. "
    "DO NOT stop after extracting only the first few variants - you must extract ALL of them. "
    "2) Never hallucinate numbers; only extract if explicitly present. "
    "3) Keep units alongside numeric values in the *_unit fields. "
    "4) Prefer precise biochemical names (IUPAC/common) over generic phrases. "
    "5) When multiple reactions are present, split them into separate entries. "
    "6) Extract ALL kinetics parameters from table columns: "
    "   - kcat (turnover number, typically s^-1) → kinetics.kcat and kinetics.kcat_unit "
    "   - KM (Michaelis constant, typically mM) → kinetics.Km and kinetics.Km_unit "
    "   - kcat/KM (catalytic efficiency, typically M^-1s^-1) → kinetics.kcat_over_KM and kinetics.kcat_over_KM_unit "
    "   - Tm (melting temperature, typically °C) → kinetics.Tm and kinetics.Tm_unit "
    "   For 'n.c.' (not calculable), 'n.d.' (not detected), 'n.m.' (not measured), use null for the value "
    "   For values with ± (uncertainty), extract the mean value (e.g., '0.07 ± 0.02' → 0.07) "
    '7) PDB IDs are four-character codes (first is a digit) like 1ABC; include any PDB IDs you find in the "pdb_ids" list for the corresponding reaction. '
)


def build_user_prompt(text: str, source_file: str) -> str:
    """Build the user prompt for LLM enzyme extraction.

    Args:
        text: The document text to extract reactions from.
        source_file: Name or path of the source file for context.

    Returns:
        The formatted user prompt string.
    """
    return (
        "Task: Extract enzyme reaction information from the following content.\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "- Extract EVERY enzyme variant listed in tables, not just the 'main' or 'important' ones\n"
        "- If a table contains N rows of enzyme variants, you MUST extract ALL N variants\n"
        "- Each row in a kinetics table represents a separate reaction entry\n"
        "- Count the number of enzyme names in the table - if you count N, you must output N reaction entries\n"
        "- Do NOT stop early or skip variants - extract ALL of them\n"
        "- Even variants with 'n.c.' (not calculable) or 'n.d.' (not detected) should be extracted with null values\n\n"
        "Required fields for EACH reaction:\n"
        "- Enzyme name: exact variant name from table (e.g., Des27, Des27.1, Des27.7 F113L, etc.)\n"
        "- Substrates and products (lists, use empty list [] if not mentioned)\n"
        "- Conditions: temperature, pH, buffer, time, notes (strings, use null if not available)\n"
        "- Kinetics: extract ALL available parameters from table columns:\n"
        "  * kcat → kinetics.kcat + kinetics.kcat_unit (typically 's^-1' or 's⁻¹')\n"
        "  * KM → kinetics.Km + kinetics.Km_unit (typically 'mM')\n"
        "  * kcat/KM → kinetics.kcat_over_KM + kinetics.kcat_over_KM_unit (typically 'M^-1s^-1' or 'M⁻¹s⁻¹')\n"
        "  * Tm → kinetics.Tm + kinetics.Tm_unit (typically '°C' or 'C')\n"
        "  * Vmax → kinetics.Vmax + kinetics.Vmax_unit (if present)\n"
        "  For 'n.c.' (not calculable), 'n.d.' (not detected), 'n.m.' (not measured), use null\n"
        "  For values with ± (uncertainty), extract the mean value (e.g., '0.07 ± 0.02' → 0.07)\n"
        "- Yield percent if explicitly stated\n"
        "- Citations (DOI, PubMed, journal references)\n"
        "- PDB IDs found in the text (four-character codes starting with digit)\n\n"
        "COUNTING CHECKLIST:\n"
        "Before finalizing your JSON response:\n"
        "1. Count how many enzyme variants are in the table\n"
        "2. Count how many reaction entries you created\n"
        "3. These numbers MUST match exactly\n"
        "4. If they don't match, go back and extract the missing variants\n\n"
        f"Context: source file = {source_file}\n"
        "Output: STRICT JSON only, conforming to the described schema.\n\n"
        "Content:\n" + text)


async def extract_with_llm(
    text: str,
    source_file: str = _UNKNOWN_SOURCE_FILE,
    manager: Model | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    step_id: str | None = None,
) -> Dict[str, Any]:
    """Extract enzyme reaction data from text using an LLM.

    Args:
        text: The text content to extract reactions from.
        source_file: Name or path of the source file for logging.
        manager: The Model instance to use for LLM generation.
        agent_id: Optional agent ID for session tracking.
        session_id: Optional session ID for session tracking.
        step_id: Optional step ID for linking to extraction steps.

    Returns:
        Dictionary with extracted reactions and pipeline metadata.
    """
    if manager is None:
        return create_error_response("LLM extraction aborted: missing Model",
                                     ["Model is required"])

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": build_user_prompt(text, source_file)
        },
    ]

    try:
        resp = await manager.generate(
            messages,
            role=ModelRole.GENERAL,
            agent_id=agent_id,
            session_id=session_id,
            step_id=step_id,
        )
        data = json.loads(resp.content or "{}")

        sanitize_reaction_list_fields(data)

        pdb_ids = extract_pdb_ids_from_text(text)
        merge_pdb_ids(data, pdb_ids)

        # Validate against schema
        ExtractionResult(**data)
        return data

    except (json.JSONDecodeError, ValidationError) as e:
        logger.error("Failed to parse/validate JSON output: %s", e)
        return create_error_response("Failed to parse/validate JSON output", [str(e)])
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return create_error_response("LLM call failed", [str(e)])


class LLMEnzymeExtractorAgent(BaseAgent):
    """Agent for extracting enzyme reaction data using LLM analysis.

    This agent uses a two-phase pipeline:
    1. Document structure analysis to identify relevant sections
    2. Targeted LLM extraction from the relevant content only
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager: Model,
    ):
        """Initialize the LLMEnzymeExtractorAgent.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: Manager for agent memory and message passing.
            tool_registry: Registry of available tools.
            model_manager: Model instance for LLM operations.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["llm_enzyme_extraction"],
        )
        self.model_manager = model_manager

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process an enzyme extraction task.

        Args:
            task: Dictionary containing document information with optional
                  source_type, content, path, or url fields.

        Returns:
            Dictionary with status and extraction data, or error information.
        """
        from src.conversations.models import ExtractionSessionStatus, ExtractionStepStatus
        from src.conversations.storage import ConversationStorage

        # Initialize storage if tracking is enabled
        storage = None
        session_id = "tracking_disabled"
        if self.model_manager.enable_tracking and self.model_manager.tracking_storage:
            storage = self.model_manager.tracking_storage

        # Load document
        load_result = await self._load_document(task)
        if load_result["status"] == "error":
            return load_result

        # Start extraction session
        if storage:
            session_id = await storage.start_extraction_session(
                document_path=load_result["source_file"],
                extraction_type="kinetics",
                agent_id=self.agent_id,
                metadata={"task": task},
            )

        try:
            # Phase 1: Document structure analysis
            if storage:
                await storage.update_session_phase(session_id, "structure_analysis")

                table_step_id = await storage.start_session_step(
                    session_id=session_id,
                    step_name="table_extraction",
                    step_phase="phase1_structure",
                    step_order=1,
                    metadata={"description": "Extract and classify tables from document"},
                )

            analysis_result = await self._analyze_document_structure(
                load_result["text"],
                load_result["source_file"],
                session_id=session_id,
                agent_id=self.agent_id,
                step_id=table_step_id if storage else None,
            )

            if storage:
                await storage.complete_session_step(table_step_id)

            if analysis_result["status"] == "error":
                if storage:
                    await storage.complete_extraction_session(
                        session_id, ExtractionSessionStatus.FAILED
                    )
                return analysis_result

            # Phase 2: Main extraction
            if storage:
                await storage.update_session_phase(session_id, "extraction")

                extraction_step_id = await storage.start_session_step(
                    session_id=session_id,
                    step_name="main_extraction",
                    step_phase="phase2_extraction",
                    step_order=2,
                    metadata={"description": "Extract structured kinetics data"},
                )

            extraction_data = await extract_with_llm(
                text=analysis_result["relevant_content"],
                source_file=load_result["source_file"],
                manager=self.model_manager,
                agent_id=self.agent_id,
                session_id=session_id,
                step_id=extraction_step_id if storage else None,
            )

            if storage:
                await storage.complete_session_step(extraction_step_id)

            extraction_data["pipeline"]["document_analysis"] = (
                self._build_document_analysis_metadata(
                    analysis_result["analysis"],
                    load_result["source_file"]
                )
            )

            # Save extraction results
            if storage:
                await storage.save_extraction_result(
                    session_id=session_id,
                    result_type="reactions",
                    content=json.dumps(extraction_data),
                )

            # Complete session
            if storage:
                await storage.complete_extraction_session(
                    session_id, ExtractionSessionStatus.COMPLETED
                )

            result = {"status": STATUS_SUCCESS, "data": {"extraction": extraction_data}}
            if storage:
                result["data"]["session_id"] = session_id
            return result

        except Exception as e:
            if storage:
                await storage.complete_extraction_session(
                    session_id, ExtractionSessionStatus.FAILED
                )
            raise

    async def _load_document(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Load document content based on source type.

        Args:
            task: Task dictionary containing document information.

        Returns:
            Dictionary with status and either text/source_file or error.
        """
        doc = task.get("document") or {}
        source_type = (doc.get("source_type") or _SOURCE_TYPE_TEXT).lower()

        if source_type == _SOURCE_TYPE_TEXT:
            return self._load_from_text(doc)
        elif source_type == _SOURCE_TYPE_FILE:
            return await self._load_from_file(doc)
        elif source_type == _SOURCE_TYPE_URL:
            return await self._load_from_url(doc)

        return {
            "status": STATUS_ERROR,
            "error": f"Unsupported source_type: {source_type}"
        }

    def _load_from_text(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Load document from inline text content.

        Args:
            doc: Document dictionary containing content.

        Returns:
            Dictionary with status and text/source_file or error.
        """
        content = doc.get("content")
        if not content:
            return {"status": STATUS_ERROR, "error": "Missing text content"}
        return {
            "status": STATUS_SUCCESS,
            "text": str(content),
            "source_file": _INLINE_SOURCE_FILE,
        }

    async def _load_from_file(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Load document from file path.

        Args:
            doc: Document dictionary containing path.

        Returns:
            Dictionary with status and text/source_file or error.
        """
        path = doc.get("path")
        if not path:
            return {"status": STATUS_ERROR, "error": "Missing file path"}
        return await self._load_via_tool("file", {
            "source_type": "file",
            "path": str(path)
        }, str(path))

    async def _load_from_url(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Load document from URL.

        Args:
            doc: Document dictionary containing url.

        Returns:
            Dictionary with status and text/source_file or error.
        """
        url = doc.get("url")
        if not url:
            return {"status": STATUS_ERROR, "error": "Missing URL"}
        return await self._load_via_tool("url", {
            "source_type": "url",
            "url": str(url)
        }, str(url))

    async def _load_via_tool(self, tool_name: str, params: Dict[str, Any],
                             source_file: str) -> Dict[str, Any]:
        """Load document using the document_loader tool.

        Args:
            tool_name: Name of the tool operation ('file' or 'url').
            params: Parameters to pass to the tool.
            source_file: Identifier for the source file.

        Returns:
            Dictionary with status and either text/source_file or error.
        """
        loaded = await self.tools.execute_tool("document_loader", params)
        if loaded.status.value != STATUS_SUCCESS:
            return {"status": STATUS_ERROR, "error": loaded.error or "load_failed"}
        return {
            "status": STATUS_SUCCESS,
            "text": loaded.data.get("text", ""),
            "source_file": source_file,
        }

    async def _analyze_document_structure(
        self,
        text: str,
        source_file: str,
        session_id: str | None = None,
        agent_id: str | None = None,
        step_id: str | None = None,
    ) -> Dict[str, Any]:
        """Analyze document structure to identify relevant content.

        Args:
            text: Full document text to analyze.
            source_file: Path or identifier of the source file.
            session_id: Optional session ID for tracking.
            agent_id: Optional agent ID for tracking.
            step_id: Optional step ID for tracking.

        Returns:
            Dictionary with status and analysis/relevant_content or error.
        """
        analyzer = DocumentStructureAnalyzer(
            model_manager=self.model_manager,
            use_llm_enhancement=True,
            agent_id=agent_id,
            session_id=session_id,
            step_id=step_id,
        )
        structure_result = await analyzer.execute(text=text, source_file=source_file)

        if structure_result.status.value != STATUS_SUCCESS:
            return {
                "status": STATUS_ERROR,
                "error":
                f"Document structure analysis failed: {structure_result.error}",
            }

        analysis = structure_result.data
        output_dir = Path(source_file).parent.parent / "data" / "analysis"
        save_document_analysis(analysis, output_dir)

        relevant_content = get_relevant_content_for_extraction(analysis)

        # Fallback to full text if no relevant content found
        if not relevant_content.strip():
            relevant_content = text
            analysis["fallback_to_full_text"] = True

        return {
            "status": STATUS_SUCCESS,
            "analysis": analysis,
            "relevant_content": relevant_content,
        }

    def _build_document_analysis_metadata(self, analysis: Dict[str, Any],
                                          source_file: str) -> Dict[str, Any]:
        """Build metadata summary about the document analysis.

        Args:
            analysis: Document analysis data.
            source_file: Path or identifier of the source file.

        Returns:
            Dictionary with document analysis metadata.
        """
        output_dir = Path(source_file).parent.parent / "data" / "analysis"
        tables = analysis.get("tables", [])

        return {
            "total_tables":
            analysis.get("total_tables", 0),
            "reaction_related_tables":
            sum(1 for table in tables if table.get("is_reaction_related", False)),
            "key_paragraphs":
            analysis.get("total_key_paragraphs", 0),
            "used_fallback":
            analysis.get("fallback_to_full_text", False),
            "analysis_file":
            str(output_dir / f"{Path(source_file).stem}_structure_analysis.json"),
        }
