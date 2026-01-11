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
    Km: Optional[float] = None
    Km_unit: Optional[str] = None
    Vmax: Optional[float] = None
    Vmax_unit: Optional[str] = None


class Reaction(BaseModel):
    source_file: Optional[str] = None
    enzyme_name: Optional[str] = None
    substrates: List[str] = []
    products: List[str] = []
    conditions: ReactionConditions = ReactionConditions()
    kinetics: ReactionKinetics = ReactionKinetics()
    yield_percent: Optional[float] = None
    citations: List[str] = []

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
