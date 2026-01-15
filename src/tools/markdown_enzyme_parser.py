"""Pydantic schema for validating LLM-extracted enzyme reaction data."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ReactionConditions(BaseModel):
    """Reaction conditions (temperature, pH, buffer, etc.).

    Attributes:
        temperature: Reaction temperature with unit.
        pH: Reaction pH value.
        buffer: Buffer composition.
        time: Reaction duration.
        notes: Additional condition notes.
    """

    temperature: Optional[str] = None
    pH: Optional[str] = None
    buffer: Optional[str] = None
    time: Optional[str] = None
    notes: Optional[str] = None


class ReactionKinetics(BaseModel):
    """Enzyme kinetic parameters.

    Attributes:
        Km: Michaelis constant.
        Km_unit: Unit for Km value.
        Vmax: Maximum reaction velocity.
        Vmax_unit: Unit for Vmax value.
        kcat: Turnover number (catalytic rate).
        kcat_unit: Unit for kcat value.
        kcat_over_KM: Catalytic efficiency (kcat/Km).
        kcat_over_KM_unit: Unit for catalytic efficiency.
        Tm: Melting temperature (thermal stability).
        Tm_unit: Unit for Tm value.
    """

    Km: Optional[float] = None
    Km_unit: Optional[str] = None
    Vmax: Optional[float] = None
    Vmax_unit: Optional[str] = None

    kcat: Optional[float] = None
    kcat_unit: Optional[str] = None

    kcat_over_KM: Optional[float] = None
    kcat_over_KM_unit: Optional[str] = None

    Tm: Optional[float] = None
    Tm_unit: Optional[str] = None


class Reaction(BaseModel):
    """Enzyme-catalyzed reaction with substrates, products, and parameters.

    Attributes:
        source_file: Source document file path.
        enzyme_name: Name of the enzyme.
        substrates: List of substrate molecules.
        products: List of product molecules.
        conditions: Reaction conditions.
        kinetics: Kinetic parameters.
        yield_percent: Reaction yield as percentage.
        citations: Literature citations.
        pdb_ids: Associated Protein Data Bank identifiers.
    """

    source_file: Optional[str] = None
    enzyme_name: Optional[str] = None
    substrates: List[str] = []
    products: List[str] = []
    conditions: ReactionConditions = ReactionConditions()
    kinetics: ReactionKinetics = ReactionKinetics()
    yield_percent: Optional[float] = None
    citations: List[str] = []
    pdb_ids: List[str] = []

    model_config = ConfigDict(extra="allow")


class PipelineStep(BaseModel):
    """A step in the extraction pipeline.

    Attributes:
        name: Step identifier.
        description: Human-readable description.
        status: Step status (e.g., "completed", "failed").
    """

    name: str
    description: str
    status: str


class ExtractionPipeline(BaseModel):
    """Pipeline execution metadata.

    Attributes:
        steps: List of pipeline steps executed.
        validations: Validation messages.
        errors: Error messages encountered.
    """

    steps: List[PipelineStep] = []
    validations: List[str] = []
    errors: List[str] = []


class ExtractionResult(BaseModel):
    """Complete extraction result with reactions and pipeline metadata.

    Attributes:
        reactions: List of extracted enzyme reactions.
        pipeline: Pipeline execution metadata.
    """

    reactions: List[Reaction] = []
    pipeline: ExtractionPipeline = ExtractionPipeline()

    model_config = ConfigDict(extra="allow")
