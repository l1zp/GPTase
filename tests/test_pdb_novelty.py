"""Tests for PDB novelty classification (boolean flags)."""

import pytest
import json
import tempfile
import os
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.extract_pdb_info import extract_pdb_relationships, create_enzyme_pdb_csv


class TestPDBNoveltyExtraction:
    """Test PDB novelty (is_new) flag extraction from JSON."""

    def test_extract_with_pdb_is_new(self):
        """Test extraction when pdb_is_new field is present."""
        test_data = {
            "reactions": [
                {
                    "enzyme_name": "Enzyme1",
                    "pdb_ids": ["1ABC", "2DEF"],
                    "pdb_is_new": [True, False]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)

            assert len(enzyme_to_pdbs) == 1
            assert enzyme_to_pdbs["Enzyme1"] == {"1ABC", "2DEF"}
            assert enzyme_pdb_is_new["Enzyme1"] == [True, False]
            assert all_pdbs == {"1ABC", "2DEF"}
        finally:
            os.unlink(json_path)

    def test_extract_without_pdb_is_new(self):
        """Test extraction when pdb_is_new field is missing (should default to False)."""
        test_data = {
            "reactions": [
                {
                    "enzyme_name": "Enzyme1",
                    "pdb_ids": ["1ABC", "2DEF"]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)

            # Should default to False for all PDBs
            assert enzyme_pdb_is_new["Enzyme1"] == [False, False]
        finally:
            os.unlink(json_path)

    def test_extract_mismatched_lengths(self):
        """Test extraction when pdb_is_new length doesn't match pdb_ids (should default to False)."""
        test_data = {
            "reactions": [
                {
                    "enzyme_name": "Enzyme1",
                    "pdb_ids": ["1ABC", "2DEF", "3GHI"],
                    "pdb_is_new": [True, False]  # Only 2 flags for 3 PDBs
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)

            # Should default to False for all due to mismatch
            assert enzyme_pdb_is_new["Enzyme1"] == [False, False, False]
        finally:
            os.unlink(json_path)


class TestCreateEnzymePDBCSVWithNovelty:
    """Test CSV generation with pdb_is_new boolean flags."""

    def test_csv_with_mixed_novelty(self):
        """Test CSV generation with mixed new/old PDBs."""
        enzyme_to_pdbs = {
            "Enzyme1": {"1ABC", "2DEF"}
        }
        enzyme_pdb_is_new = {
            "Enzyme1": [True, False]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, output_path)

            # Verify CSV content
            with open(output_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Check header
            assert 'enzyme_name,pdb_id,pdb_is_new' in lines[0]

            # Check data rows (sorted by pdb_id)
            rows = [line.strip() for line in lines[1:]]
            assert 'Enzyme1,1ABC,true' in rows
            assert 'Enzyme1,2DEF,false' in rows

        finally:
            os.unlink(output_path)

    def test_csv_all_new_pdbs(self):
        """Test CSV generation where all PDBs are new."""
        enzyme_to_pdbs = {
            "Enzyme1": {"1ABC", "2DEF"}
        }
        enzyme_pdb_is_new = {
            "Enzyme1": [True, True]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert '1ABC,true' in content
            assert '2DEF,true' in content

        finally:
            os.unlink(output_path)

    def test_csv_all_old_pdbs(self):
        """Test CSV generation where all PDBs are from previous work."""
        enzyme_to_pdbs = {
            "Enzyme1": {"1ABC", "2DEF"}
        }
        enzyme_pdb_is_new = {
            "Enzyme1": [False, False]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert '1ABC,false' in content
            assert '2DEF,false' in content

        finally:
            os.unlink(output_path)


class TestRealWorldScenario:
    """Test with realistic data patterns from scientific papers."""

    def test_paper_with_new_and_template_pdbs(self):
        """Test typical scenario: paper has new structures + template from previous work."""
        test_data = {
            "reactions": [
                {
                    "enzyme_name": "Des27",
                    "pdb_ids": ["9HVB", "9HVH", "1I4A", "1LBF"],
                    "pdb_is_new": [True, True, False, False]  # 2 new, 2 templates
                },
                {
                    "enzyme_name": "Des27.1",
                    "pdb_ids": ["9HVB", "9HVH", "1I4A", "1LBF"],
                    "pdb_is_new": [True, True, False, False]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_path = f.name

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, csv_path)

            # Verify extraction
            assert len(enzyme_to_pdbs) == 2
            assert len(all_pdbs) == 4

            # Verify CSV has correct flags
            with open(csv_path, 'r') as f:
                content = f.read()

            # Count new vs old
            new_count = content.count(',true')
            old_count = content.count(',false')

            assert new_count == 4  # 2 enzymes × 2 new PDBs each
            assert old_count == 4  # 2 enzymes × 2 old PDBs each

        finally:
            os.unlink(json_path)
            os.unlink(csv_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
