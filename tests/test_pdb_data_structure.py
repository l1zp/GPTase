"""Tests for normalized PDB data structure."""

import pytest
import csv
import tempfile
import os
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.extract_pdb_info import extract_pdb_relationships, create_enzyme_pdb_csv, create_pdb_info_csv


class TestExtractPDBRelationships:
    """Test PDB relationship extraction from JSON."""

    def test_extract_relationships_simple(self):
        """Test extraction with simple enzyme-PDB mappings."""
        import json

        # Create temporary JSON file
        test_data = {
            "reactions": [
                {
                    "enzyme_name": "Enzyme1",
                    "pdb_ids": ["1ABC", "2DEF"]
                },
                {
                    "enzyme_name": "Enzyme2",
                    "pdb_ids": ["1ABC", "3GHI"]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)

            assert len(enzyme_to_pdbs) == 2
            assert enzyme_to_pdbs["Enzyme1"] == {"1ABC", "2DEF"}
            assert enzyme_to_pdbs["Enzyme2"] == {"1ABC", "3GHI"}
            assert all_pdbs == {"1ABC", "2DEF", "3GHI"}
            # Check default pdb_is_new values (should all be False)
            assert enzyme_pdb_is_new["Enzyme1"] == [False, False]
            assert enzyme_pdb_is_new["Enzyme2"] == [False, False]
        finally:
            os.unlink(json_path)

    def test_extract_relationships_empty_pdb_ids(self):
        """Test handling of enzymes without PDB IDs."""
        import json

        test_data = {
            "reactions": [
                {
                    "enzyme_name": "Enzyme1",
                    "pdb_ids": ["1ABC"]
                },
                {
                    "enzyme_name": "Enzyme2",
                    "pdb_ids": []
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)

            # Only Enzyme1 should be included
            assert len(enzyme_to_pdbs) == 1
            assert "Enzyme1" in enzyme_to_pdbs
            assert "Enzyme2" not in enzyme_to_pdbs
            assert all_pdbs == {"1ABC"}
            assert enzyme_pdb_is_new["Enzyme1"] == [False]
        finally:
            os.unlink(json_path)


class TestCreateEnzymePDBCSV:
    """Test enzyme_to_pdb.csv generation."""

    def test_create_junction_table(self):
        """Test creation of junction table CSV."""
        enzyme_to_pdbs = {
            "Enzyme1": {"1ABC", "2DEF"},
            "Enzyme2": {"1ABC", "3GHI"}
        }
        enzyme_pdb_is_new = {
            "Enzyme1": [True, False],
            "Enzyme2": [True, False]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, output_path)

            # Verify CSV structure
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Should have 4 rows (2 enzymes × 2 PDBs each, but 1ABC is shared)
            # Actually: Enzyme1-1ABC, Enzyme1-2DEF, Enzyme2-1ABC, Enzyme2-3GHI = 4 rows
            assert len(rows) == 4

            # Check columns - now includes pdb_is_new
            assert set(rows[0].keys()) == {'enzyme_name', 'pdb_id', 'pdb_is_new'}

            # Check content
            enzyme_pdb_pairs = {(r['enzyme_name'], r['pdb_id'], r['pdb_is_new']) for r in rows}
            assert ('Enzyme1', '1ABC', 'true') in enzyme_pdb_pairs
            assert ('Enzyme1', '2DEF', 'false') in enzyme_pdb_pairs
            assert ('Enzyme2', '1ABC', 'true') in enzyme_pdb_pairs
            assert ('Enzyme2', '3GHI', 'false') in enzyme_pdb_pairs

        finally:
            os.unlink(output_path)

    def test_junction_table_sorted(self):
        """Test that junction table is sorted by enzyme_name and pdb_id."""
        enzyme_to_pdbs = {
            "Enzyme2": {"3GHI"},
            "Enzyme1": {"2DEF", "1ABC"}
        }
        enzyme_pdb_is_new = {
            "Enzyme2": [False],
            "Enzyme1": [True, False]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Check sorting: enzyme_name, then pdb_id
            enzyme_pdb_pairs = [(r['enzyme_name'], r['pdb_id']) for r in rows]
            assert enzyme_pdb_pairs == [
                ('Enzyme1', '1ABC'),
                ('Enzyme1', '2DEF'),
                ('Enzyme2', '3GHI')
            ]

        finally:
            os.unlink(output_path)


class TestNormalizedStructure:
    """Test the normalized database structure."""

    def test_no_data_redundancy(self):
        """Test that PDB metadata is not duplicated across enzymes."""
        import json

        # Create test data where multiple enzymes share same PDB
        test_data = {
            "reactions": [
                {"enzyme_name": "E1", "pdb_ids": ["1ABC", "2DEF"]},
                {"enzyme_name": "E2", "pdb_ids": ["1ABC", "2DEF"]},
                {"enzyme_name": "E3", "pdb_ids": ["1ABC", "2DEF"]}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            enzyme_pdb_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            pdb_info_path = f.name

        try:
            # Extract relationships
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)

            # Create junction table
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, enzyme_pdb_path)

            # Create PDB info table
            create_pdb_info_csv(all_pdbs, pdb_info_path)

            # Verify: PDB info should have only 2 entries (1ABC, 2DEF)
            # Not 6 entries (3 enzymes × 2 PDBs)
            with open(pdb_info_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                pdb_rows = list(reader)

            assert len(pdb_rows) == 2  # Only 2 unique PDB IDs

            # Verify: Junction table should have 6 entries (many-to-many)
            with open(enzyme_pdb_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                junction_rows = list(reader)

            assert len(junction_rows) == 6  # 3 enzymes × 2 PDBs each

        finally:
            os.unlink(json_path)
            os.unlink(enzyme_pdb_path)
            os.unlink(pdb_info_path)

    def test_many_to_many_relationship(self):
        """Test many-to-many relationship: one enzyme has many PDBs, one PDB has many enzymes."""
        import json

        test_data = {
            "reactions": [
                {"enzyme_name": "E1", "pdb_ids": ["1ABC", "2DEF", "3GHI"]},  # 1 enzyme → 3 PDBs
                {"enzyme_name": "E2", "pdb_ids": ["1ABC"]},                 # 2 enzymes → 1 PDB
                {"enzyme_name": "E3", "pdb_ids": ["1ABC"]}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json_path = f.name
            json.dump(test_data, f)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            enzyme_pdb_path = f.name

        try:
            enzyme_to_pdbs, all_pdbs, enzyme_pdb_is_new = extract_pdb_relationships(json_path)
            create_enzyme_pdb_csv(enzyme_to_pdbs, enzyme_pdb_is_new, enzyme_pdb_path)

            with open(enzyme_pdb_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Count relationships
            e1_count = sum(1 for r in rows if r['enzyme_name'] == 'E1')
            e2_count = sum(1 for r in rows if r['enzyme_name'] == 'E2')
            e3_count = sum(1 for r in rows if r['enzyme_name'] == 'E3')
            abc_count = sum(1 for r in rows if r['pdb_id'] == '1ABC')

            # Verify: E1 has 3 PDBs
            assert e1_count == 3

            # Verify: 1ABC has 3 enzymes (E1, E2, E3)
            assert abc_count == 3

            # Verify: E2 and E3 each have 1 PDB
            assert e2_count == 1
            assert e3_count == 1

        finally:
            os.unlink(json_path)
            os.unlink(enzyme_pdb_path)


class TestRealWorldExample:
    """Test with real-world data structure from listov2025."""

    def test_listov2025_structure(self):
        """Test that real data follows expected structure."""
        enzyme_pdb_path = '/Users/ryan/Code/GPTase/data/extraction/enzyme_to_pdb.csv'
        pdb_info_path = '/Users/ryan/Code/GPTase/data/extraction/pdb_info.csv'

        # Skip if files don't exist (e.g., in CI environment)
        if not os.path.exists(enzyme_pdb_path) or not os.path.exists(pdb_info_path):
            pytest.skip("Real data files not found")

        # Read enzyme_to_pdb.csv
        with open(enzyme_pdb_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            enzyme_rows = list(reader)

        # Read pdb_info.csv
        with open(pdb_info_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            pdb_rows = list(reader)

        # Basic sanity checks
        assert len(enzyme_rows) > 0, "enzyme_to_pdb.csv should have data"
        assert len(pdb_rows) > 0, "pdb_info.csv should have data"

        # Verify columns
        assert set(enzyme_rows[0].keys()) == {'enzyme_name', 'pdb_id'}
        assert 'pdb_id' in pdb_rows[0]
        assert 'ec_numbers' in pdb_rows[0]

        # Get unique counts
        unique_enzymes = set(r['enzyme_name'] for r in enzyme_rows)
        unique_pdbs = set(r['pdb_id'] for r in enzyme_rows)

        # Verify junction table has more rows than unique enzymes (many-to-many)
        assert len(enzyme_rows) > len(unique_enzymes), \
            "Should be many-to-many relationship"

        # Verify PDB info has one entry per unique PDB
        assert len(pdb_rows) == len(unique_pdbs), \
            "pdb_info.csv should have one entry per unique PDB"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
