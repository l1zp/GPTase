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
    kcat_over_Km: Optional[float] = None
    kcat_over_Km_unit: Optional[str] = None
    kcat_over_KM: Optional[float] = None
    kcat_over_KM_unit: Optional[str] = None
    Tm: Optional[float] = None
    Tm_unit: Optional[str] = None


class MutationAnnotation(BaseModel):
    from_residue: Optional[str] = None
    position: Optional[int] = None
    to_residue: Optional[str] = None
    mutation_code: Optional[str] = None


class ReactionEntry(BaseModel):
    enzyme_name: Optional[str] = None
    variant_name: Optional[str] = None
    substrates: Optional[List[Any]] = None
    products: Optional[List[Any]] = None
    kinetics: Optional[Dict[str, Any]] = None
    mutations: Optional[List[Any]] = None
    mutation_annotations: Optional[List[MutationAnnotation]] = None
    pdb_ids: Optional[List[Any]] = None
    scaffold_pdb_id: Optional[str] = None
    full_sequence: Optional[str] = None
    variant_sequence: Optional[str] = None
    normalization_status: Optional[str] = None
    issues: Optional[List[str]] = None
    conditions: Optional[Dict[str, Any]] = None


class EnzymeKineticsOutput(BaseModel):
    reactions: Optional[List[ReactionEntry]] = None


class EnzymeVariantNormalizerOutput(BaseModel):
    normalized_variants: Optional[List[ReactionEntry]] = None
    normalization_summary: Optional[Dict[str, Any]] = None


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
# deep_research
# ---------------------------------------------------------------------------


class DeepResearchOutput(BaseModel):
    """Output schema for the deep-research agent (Markdown report as text)."""

    content: Optional[str] = None


# ---------------------------------------------------------------------------
# Registry: schema_name -> Pydantic model class
# ---------------------------------------------------------------------------

SCHEMA_MAP: Dict[str, type] = {
    "document_structure": DocumentStructureOutput,
    "enzyme_kinetics": EnzymeKineticsOutput,
    "enzyme_variant_normalizer": EnzymeVariantNormalizerOutput,
    "vision_analysis": VisionAnalysisOutput,
    "enzyme_summary": EnzymeSummaryOutput,
    "deep_research": DeepResearchOutput,
}
