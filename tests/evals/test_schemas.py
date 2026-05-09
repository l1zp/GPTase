"""Unit tests for gptase.evals.schemas.

These pydantic models are an evals-only contract: only
``gptase/evals/assertions.py`` consumes them, and they exist to catch
*shape* errors in agent JSON outputs rather than to enforce
completeness (completeness lives in ``golden.yaml::key_facts``).

Six cases covering the contracts that matter:

* All registered schemas instantiate from empty dict (every field is
  Optional — partial outputs must validate).
* SCHEMA_MAP exposes the documented agent set (catches accidental
  removal during refactors).
* ``KineticsEntry`` deliberately accepts BOTH ``kcat_over_Km`` and
  ``kcat_over_KM`` — historical case drift across agent prompts.
* Nested entries (kinetics dict, mutation list, section/table/image
  lists) round-trip correctly.
* Despite ``Optional[float]``, providing a non-coercible value still
  raises ValidationError — Optional is about presence, not types.
"""
from pydantic import BaseModel
from pydantic import ValidationError
import pytest

from gptase.evals.schemas import DocumentStructureOutput
from gptase.evals.schemas import EnzymeKineticsOutput
from gptase.evals.schemas import KineticsEntry
from gptase.evals.schemas import ReactionEntry
from gptase.evals.schemas import SCHEMA_MAP


class TestSchemaInstantiation:
    """Every registered schema accepts ``{}`` and is a BaseModel subclass."""

    def test_all_schemas_in_schema_map_accept_empty_dict(self):
        for name, model_cls in SCHEMA_MAP.items():
            # Subclass check first — guards against someone putting a
            # non-pydantic class in the registry.
            assert issubclass(model_cls, BaseModel), name
            instance = model_cls.model_validate({})
            # Round-trip cleanly.
            assert isinstance(instance.model_dump(), dict)

    def test_schema_map_keys_match_documented_agents(self):
        # Pin the public registry surface — adding/removing here is a
        # downstream-visible change and should be intentional.
        assert set(SCHEMA_MAP.keys()) == {
            "document_structure",
            "enzyme_kinetics",
            "enzyme_variant_normalizer",
            "vision_analysis",
            "enzyme_summary",
            "deep_research",
        }


class TestSchemaShape:
    """Nested + drift-tolerant fields — the schema's actual job."""

    def test_kinetics_entry_accepts_both_capitalization_variants(self):
        # Historical case drift: different agents emit kcat_over_Km
        # vs. kcat_over_KM. The schema deliberately accepts both so
        # the evals layer can validate either prompt's output.
        entry = KineticsEntry(
            kcat_over_Km=1.5,
            kcat_over_KM=1.5,
            kcat_over_Km_unit="M-1 s-1",
            kcat_over_KM_unit="M-1 s-1",
        )

        dumped = entry.model_dump(exclude_none=True)
        assert dumped["kcat_over_Km"] == 1.5
        assert dumped["kcat_over_KM"] == 1.5

    def test_reaction_entry_nests_kinetics_and_mutations(self):
        entry = ReactionEntry.model_validate({
            "enzyme_name":
            "KE07",
            "variant_name":
            "KE07-G62V",
            "substrates": ["5-NB"],
            "products": ["2-CN-4-NP"],
            "kinetics": {
                "kcat": 0.2,
                "Km": 0.4
            },  # Dict[str, Any] — passes through
            "mutation_annotations": [{
                "from_residue": "G",
                "position": 62,
                "to_residue": "V",
                "mutation_code": "G62V",
            }],
        })

        assert entry.enzyme_name == "KE07"
        # mutation_annotations is the typed list (MutationAnnotation),
        # while kinetics is left as a free-form dict.
        assert entry.mutation_annotations[0].mutation_code == "G62V"
        assert entry.kinetics["kcat"] == 0.2

    def test_document_structure_nests_section_table_image_entries(self):
        out = DocumentStructureOutput.model_validate({
            "sections": [{
                "section_name": "Results",
                "is_reaction_related": True
            }],
            "tables": [{
                "table_number": 1,
                "is_reaction_related": True
            }],
            "images": [{
                "image_number": 1,
                "image_path": "fig1.png"
            }],
            "source_file":
            "paper.md",
        })

        assert out.sections[0].section_name == "Results"
        assert out.tables[0].table_number == 1
        assert out.images[0].image_path == "fig1.png"


class TestSchemaTypeRejection:
    """Optional[T] still type-checks values that ARE provided."""

    def test_invalid_type_still_rejected_despite_optional(self):
        # Optional[float] means "may be missing", NOT "may be any type".
        with pytest.raises(ValidationError):
            KineticsEntry(kcat="not a float")

        # And nested mis-typing inside a wrapping schema bubbles up too.
        with pytest.raises(ValidationError):
            EnzymeKineticsOutput.model_validate({"reactions": "not a list"})
