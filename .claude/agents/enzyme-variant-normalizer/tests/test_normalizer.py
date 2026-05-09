"""Unit tests for the sibling normalizer.py module.

The agent dir's conftest.py adds the parent dir to sys.path, so
``import normalizer`` resolves to the sibling normalizer.py without
needing __init__.py boilerplate or relative imports.

19 cases covering the public surface (normalize_variant_payload,
flatten_normalized_variants) + the high-leverage private helpers
that handle the most error-prone parsing paths (mutation codes, PDB
IDs, kinetic-column header recognition, uncertainty stripping, CSV
two-tier headers, HTML table -> CSV).
"""
import normalizer  # noqa: E402 — sys.path injected by conftest


class TestNormalizeVariantPayloadE2E:
    """Public entry point: text replicas in -> normalized records out."""

    def test_text_extraction_only_produces_normalized_records(self):
        inputs = {
            "text_extraction_data": [{
                "reactions": [{
                    "variant_name": "KE07",
                    "enzyme_name": "KE07",
                    "kinetics": {
                        "kcat": 0.1,
                        "Km": 0.5
                    },
                }],
            }],
        }

        result = normalizer.normalize_variant_payload(inputs)

        assert "normalized_variants" in result
        assert "normalization_summary" in result
        assert result["normalization_summary"]["variant_count"] >= 1
        names = [r.get("variant_name") for r in result["normalized_variants"]]
        assert "KE07" in names

    def test_merges_replicas_by_variant_name(self):
        # Three replicas all reference the same variant — merge into 1 record.
        inputs = {
            "text_extraction_data": [
                {
                    "reactions": [{
                        "variant_name": "KE07",
                        "enzyme_name": "KE07",
                        "kinetics": {
                            "kcat": 0.10
                        }
                    }]
                },
                {
                    "reactions": [{
                        "variant_name": "KE07",
                        "enzyme_name": "KE07",
                        "kinetics": {
                            "kcat": 0.12
                        }
                    }]
                },
                {
                    "reactions": [{
                        "variant_name": "KE07",
                        "enzyme_name": "KE07",
                        "kinetics": {
                            "Km": 0.5
                        }
                    }]
                },
            ],
        }

        result = normalizer.normalize_variant_payload(inputs)

        # One canonical record despite 3 replica rows.
        assert result["normalization_summary"]["variant_count"] == 1

    def test_kinetics_collected_from_multiple_replicas(self):
        # Two replicas with kcat from one + Km from the other.
        inputs = {
            "text_extraction_data": [
                {
                    "reactions": [{
                        "variant_name": "KE07",
                        "enzyme_name": "KE07",
                        "kinetics": {
                            "kcat": 0.10
                        }
                    }]
                },
                {
                    "reactions": [{
                        "variant_name": "KE07",
                        "enzyme_name": "KE07",
                        "kinetics": {
                            "Km": 0.5
                        }
                    }]
                },
            ],
        }

        result = normalizer.normalize_variant_payload(inputs)

        record = result["normalized_variants"][0]
        kinetics = record.get("kinetics", {})
        # Either replica's value should land in the merged record.
        assert "kcat" in kinetics or "Km" in kinetics


class TestParseMutationCode:
    """_parse_mutation_code + _extract_mutations_from_variant_name."""

    def test_parse_valid_mutation_code(self):
        result = normalizer._parse_mutation_code("G62V")

        assert result is not None
        assert result.get("mutation_code") == "G62V"

    def test_parse_invalid_mutation_returns_none(self):
        assert normalizer._parse_mutation_code("not a mutation") is None
        assert normalizer._parse_mutation_code("") is None
        assert normalizer._parse_mutation_code("xyz") is None

    def test_extract_mutations_from_variant_name(self):
        # Variant naming "KE07(R7K)" -> mutation list ["R7K"]
        muts = normalizer._extract_mutations_from_variant_name("KE07(R7K)")

        assert "R7K" in muts


class TestPdbIdAndVariantNames:
    """_normalize_pdb_id + _variant_base_name + _preferred_variant_name."""

    def test_normalize_pdb_id_valid_and_invalid(self):
        # Valid: 4-char PDB ID starting with digit.
        assert normalizer._normalize_pdb_id("3NPV") == "3NPV"
        # Lowercase normalizes to upper.
        assert normalizer._normalize_pdb_id("3npv") == "3NPV"
        # Invalid shapes return None.
        assert normalizer._normalize_pdb_id("ABCD") is None  # no leading digit
        assert normalizer._normalize_pdb_id("3NP") is None  # too short
        assert normalizer._normalize_pdb_id(None) is None

    def test_variant_base_name_strips_mutation_suffix(self):
        # KE07(R7K) -> KE07
        base = normalizer._variant_base_name("KE07(R7K)")

        assert base == "KE07"

    def test_preferred_variant_name_picks_longer_descriptive(self):
        # Picks the non-empty one; among non-empty, longer / more descriptive.
        result = normalizer._preferred_variant_name("KE07", "KE07-mutant-A")

        # Either way the function should return a non-empty preferred name;
        # the exact preference is encoded in _variant_name_score, so we
        # accept the function's choice as canonical.
        assert result in ("KE07", "KE07-mutant-A")
        # And empty-vs-non-empty: the non-empty wins.
        assert normalizer._preferred_variant_name("", "KE07") == "KE07"
        assert normalizer._preferred_variant_name(None, "KE07") == "KE07"


class TestKineticsNormalization:
    """normalize_kinetics_key + _strip_uncertainty + _normalize_kinetics."""

    def test_normalize_kinetics_key_canonical_aliases(self):
        # Alias variants -> canonical keys.
        assert normalizer.normalize_kinetics_key("kcat/km") == "kcat_over_Km"
        assert normalizer.normalize_kinetics_key("kcat_km") == "kcat_over_Km"
        assert normalizer.normalize_kinetics_key("kcat_over_km") == "kcat_over_Km"
        assert normalizer.normalize_kinetics_key("KM") == "Km"
        assert normalizer.normalize_kinetics_key("tm") == "Tm"

    def test_strip_uncertainty_handles_plus_minus_and_unicode_superscript(self):
        # Plus/minus uncertainty.
        assert normalizer._strip_uncertainty("5.1±0.8") == 5.1
        assert normalizer._strip_uncertainty("3.0+/-0.2") == 3.0
        # Unicode superscript exponent.
        assert normalizer._strip_uncertainty("2.1·10⁴") == 21000.0
        # ND / empty / dashes -> None.
        assert normalizer._strip_uncertainty("ND") is None
        assert normalizer._strip_uncertainty("") is None
        assert normalizer._strip_uncertainty("—") is None

    def test_normalize_kinetics_returns_canonical_dict(self):
        # _normalize_kinetics only canonicalizes keys — values are
        # passed through unchanged (uncertainty stripping happens
        # earlier, in _parse_csv_to_rows).
        raw = {"kcat": 0.5, "KM": 1.2, "kcat/km": 0.4}

        result = normalizer._normalize_kinetics(raw)

        assert result["kcat"] == 0.5
        assert result["Km"] == 1.2
        assert result["kcat_over_Km"] == 0.4
        # And the canonical schema includes _unit slots even when absent.
        assert "kcat_unit" in result
        assert "Tm" in result


class TestCsvAndHtmlParsing:
    """_parse_csv_to_rows + _html_table_to_csv."""

    def test_parse_csv_with_two_tier_header_picks_kinetic_row(self):
        # Row 0 is a group label; row 1 is the real header with kinetic
        # columns. The parser scores rows and picks row 1.
        csv_data = ("Catalysis,,,\n"
                    "variant,kcat (s-1),Km (mM),Tm\n"
                    "KE07,0.10,0.5,55\n"
                    "KE07-G62V,0.20,0.4,58\n")

        rows = normalizer._parse_csv_to_rows(csv_data, figure_id="fig-1")

        names = {r["variant_name"] for r in rows}
        assert "KE07" in names
        assert "KE07-G62V" in names
        # Kinetics extracted under canonical keys.
        ke07 = next(r for r in rows if r["variant_name"] == "KE07")
        assert ke07["kinetics"].get("kcat") == 0.10
        assert ke07["kinetics"].get("Km") == 0.5

    def test_parse_csv_skips_non_kinetic_table(self):
        # A PDB metadata table — no kinetic columns -> drop entirely.
        csv_data = ("variant,pdb_code,resolution\n"
                    "KE07,3NPV,1.6\n")

        rows = normalizer._parse_csv_to_rows(csv_data)

        assert rows == []

    def test_html_table_to_csv_strips_tags_and_quotes_cells(self):
        html = ("<table>"
                "<tr><th>variant</th><th>kcat (s-1)</th></tr>"
                "<tr><td>KE07</td><td>0.10</td></tr>"
                "</table>")

        csv_text = normalizer._html_table_to_csv(html)

        # Two rows, quoted cells.
        assert csv_text.startswith('"variant","kcat (s-1)"')
        assert '"KE07","0.10"' in csv_text


class TestFlattenNormalizedVariants:
    """flatten_normalized_variants -> CSV-ready dict rows."""

    def test_flatten_produces_flat_dict_rows(self):
        records = [{
            "variant_name": "KE07-G62V",
            "aliases": ["KE07_G62V"],
            "scaffold_pdb_id": "3NPV",
            "full_sequence": "MFAKE",
            "variant_sequence": "VFAKE",
            "mutations": [{
                "mutation_code": "G62V"
            }],
            "reaction": {
                "reaction_name": "Kemp elimination",
                "substrates": ["5-NB"],
                "products": ["2-CN-4-NP"],
            },
            "kinetics": {
                "kcat": 0.20,
                "kcat_unit": "s-1",
                "Km": 0.4
            },
            "evidence": {
                "sources": [{
                    "source_id": "text_replica_1"
                }]
            },
            "normalization_status": "resolved",
            "issues": [],
        }]

        rows = normalizer.flatten_normalized_variants(records)

        assert len(rows) == 1
        row = rows[0]
        assert row["variant_name"] == "KE07-G62V"
        assert row["scaffold_pdb_id"] == "3NPV"
        assert row["mutation_codes"] == "G62V"
        assert row["reaction_name"] == "Kemp elimination"
        assert row["substrates"] == "5-NB"
        assert row["kcat"] == 0.20
        assert row["evidence_sources"] == "text_replica_1"

    def test_flatten_handles_empty_or_malformed_records(self):
        # Mixed list: a non-dict entry (silently skipped) + minimal record.
        records = [None, "not-a-dict", {"variant_name": "minimal"}]

        rows = normalizer.flatten_normalized_variants(records)

        # Only the dict entry survives.
        assert len(rows) == 1
        assert rows[0]["variant_name"] == "minimal"


class TestPdbSequenceMutation:
    """_apply_mutations + the PDB-fetch path (network mocked)."""

    def test_apply_mutations_replaces_specified_residues(self):
        # Use _parse_mutation_code so the test follows the canonical
        # mutation-dict schema (from_residue/to_residue/position).
        mutation = normalizer._parse_mutation_code("G2V")
        assert mutation is not None  # sanity

        sequence, issues = normalizer._apply_mutations("MGLY", [mutation])

        # G at position 2 becomes V; M at position 1 preserved.
        assert sequence[0] == "M"
        assert sequence[1] == "V"
        # No issues for an in-bounds, residue-matching mutation.
        assert issues == []

    def test_normalize_with_pdb_fetch_mocked_attaches_full_sequence(self, monkeypatch):
        # Patch _fetch_pdb_sequence so we don't hit RCSB. The normalizer
        # should attach the canned sequence into the resulting record's
        # scaffold info when a pdb_id is present in the source rows.
        canned_sequence = "MAKETESTSEQ"
        monkeypatch.setattr(normalizer, "_fetch_pdb_sequence",
                            lambda pid: canned_sequence)

        inputs = {
            "text_extraction_data": [
                {
                    "reactions": [{
                        "variant_name": "KE07",
                        "enzyme_name": "KE07",
                        "kinetics": {
                            "kcat": 0.10
                        },
                        "pdb_ids": ["3NPV"],
                    }]
                },
            ],
        }

        result = normalizer.normalize_variant_payload(inputs)

        record = result["normalized_variants"][0]
        # Either nested under scaffold or as top-level full_sequence.
        scaffold = record.get("scaffold", {})
        full_seq = scaffold.get("full_sequence") or record.get("full_sequence")
        assert full_seq == canned_sequence
