"""
Pydantic schema for validating LLM-extracted enzyme reaction data.
"""

from typing import List, Optional

from pydantic import BaseModel


class ReactionConditions(BaseModel):
    temperature: Optional[str] = None
    pH: Optional[str] = None
    buffer: Optional[str] = None
    time: Optional[str] = None
    notes: Optional[str] = None


class ReactionKinetics(BaseModel):
    # Michaelis-Menten parameters
    Km: Optional[float] = None
    Km_unit: Optional[str] = None
    Vmax: Optional[float] = None
    Vmax_unit: Optional[str] = None

    # Turnover number (catalytic rate)
    kcat: Optional[float] = None
    kcat_unit: Optional[str] = None

    # Catalytic efficiency (kcat/KM)
    kcat_over_KM: Optional[float] = None
    kcat_over_KM_unit: Optional[str] = None

    # Melting temperature (thermal stability)
    Tm: Optional[float] = None
    Tm_unit: Optional[str] = None


class Reaction(BaseModel):
    source_file: Optional[str] = None
    enzyme_name: Optional[str] = None
    substrates: List[str] = []
    products: List[str] = []
    conditions: ReactionConditions = ReactionConditions()
    kinetics: ReactionKinetics = ReactionKinetics()
    yield_percent: Optional[float] = None
    citations: List[str] = []
    pdb_ids: List[str] = []  # Protein Data Bank IDs

    class Config:
        extra = "allow"


class PipelineStep(BaseModel):
    name: str
    description: str
    status: str


class ExtractionPipeline(BaseModel):
    steps: List[PipelineStep] = []
    validations: List[str] = []
    errors: List[str] = []


class ExtractionResult(BaseModel):
    reactions: List[Reaction] = []
    pipeline: ExtractionPipeline = ExtractionPipeline()

    class Config:
        extra = "allow"
