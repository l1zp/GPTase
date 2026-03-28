"""Pydantic output schema models for GPTase agent outputs.

Each model corresponds to one agent's expected JSON output structure.
All fields are Optional so that partial outputs still validate structurally --
the goal is to catch completely wrong shapes, not to enforce completeness
(completeness is measured separately via key_facts in golden.yaml).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# document_structure_analyzer
# ---------------------------------------------------------------------------


class SectionEntry(BaseModel):
    section_name: Optional[str] = None
    is_reaction_related: Optional[bool] = None
    reasoning: Optional[str] = None


class TableEntry(BaseModel):
    table_number: Optional[int] = None
    is_reaction_related: Optional[bool] = None
    reasoning: Optional[str] = None


class ImageEntry(BaseModel):
    image_number: Optional[int] = None
    image_path: Optional[str] = None
    figure_id: Optional[str] = None
    is_reaction_related: Optional[bool] = None
    reasoning: Optional[str] = None


class DocumentStructureOutput(BaseModel):
    sections: Optional[List[SectionEntry]] = None
    tables: Optional[List[TableEntry]] = None
    images: Optional[List[ImageEntry]] = None
    source_file: Optional[str] = None


# ---------------------------------------------------------------------------
# enzyme_kinetics_extractor
# ---------------------------------------------------------------------------


class KineticsEntry(BaseModel):
    kcat: Optional[float] = None
    kcat_unit: Optional[str] = None
    Km: Optional[float] = None
    Km_unit: Optional[str] = None
    kcat_over_KM: Optional[float] = None
    kcat_over_KM_unit: Optional[str] = None
    Tm: Optional[float] = None
    Tm_unit: Optional[str] = None


class ReactionEntry(BaseModel):
    enzyme_name: Optional[str] = None
    substrates: Optional[List[Any]] = None
    products: Optional[List[Any]] = None
    kinetics: Optional[Dict[str, Any]] = None
    mutations: Optional[List[Any]] = None
    pdb_ids: Optional[List[Any]] = None
    conditions: Optional[Dict[str, Any]] = None


class EnzymeKineticsOutput(BaseModel):
    reactions: Optional[List[ReactionEntry]] = None


# ---------------------------------------------------------------------------
# vision_image_analyzer
# ---------------------------------------------------------------------------


class AnalysisResultEntry(BaseModel):
    image_number: Optional[int] = None
    figure_id: Optional[str] = None
    content: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class VisionAnalysisOutput(BaseModel):
    analysis_results: Optional[List[AnalysisResultEntry]] = None
    extracted_tables: Optional[List[Any]] = None
    total_images: Optional[int] = None
    total_tokens: Optional[int] = None


# ---------------------------------------------------------------------------
# enzyme_extraction_summary
# ---------------------------------------------------------------------------


class EnzymeSummaryOutput(BaseModel):
    summary_report: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None
    top_performers: Optional[List[Any]] = None
    data_quality_flags: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------


class OrchestratorRoutingCase(BaseModel):
    case_id: Optional[str] = None
    user_request: Optional[str] = None
    selected_agent: Optional[str] = None
    delegation_reason: Optional[str] = None
    delegated_task: Optional[str] = None
    handoff_agents: Optional[List[str]] = None
    output_distribution: Optional[str] = None
    clarification_needed: Optional[bool] = None
    self_execute: Optional[bool] = None


class OrchestratorRoutingOutput(BaseModel):
    summary: Optional[str] = None
    cases: Optional[List[OrchestratorRoutingCase]] = None


# ---------------------------------------------------------------------------
# Registry: schema_name -> Pydantic model class
# ---------------------------------------------------------------------------

SCHEMA_MAP: Dict[str, type] = {
    "document_structure": DocumentStructureOutput,
    "enzyme_kinetics": EnzymeKineticsOutput,
    "vision_analysis": VisionAnalysisOutput,
    "enzyme_summary": EnzymeSummaryOutput,
    "orchestrator_routing": OrchestratorRoutingOutput,
}
