"""Tests for CSV handling in enzyme extraction pipeline."""

import pytest
import csv
import tempfile
import os
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.json_to_csv import flatten_reaction, validate_and_clean, convert_to_csv


class TestFlattenReaction:
    """Test flatten_reaction function."""

    def test_flatten_reaction_basic(self):
        """Test basic flattening of reaction data."""
        reaction = {
            'enzyme_name': 'TestEnzyme',
            'substrates': ['substrate1'],
            'products': ['product1'],
            'mutations': ['F113L', 'D162A'],
            'yield_percent': 85.5,
            'citations': ['DOI:10.1234/test'],
            'pdb_ids': ['1ABC'],
            'conditions': {
                'temperature': '25 °C',
                'pH': '7.3',
                'buffer': 'HEPES',
                'time': '1 h',
                'notes': None
            },
            'kinetics': {
                'Km': 0.5,
                'Km_unit': 'mM',
                'Vmax': 10.0,
                'Vmax_unit': 'μmol/s',
                'kcat': 25.0,
                'kcat_unit': 's^-1',
                'kcat_over_KM': 50.0,
                'kcat_over_KM_unit': 'M^-1s^-1',
                'Tm': 55.0,
                'Tm_unit': '°C'
            }
        }

        flattened = flatten_reaction(reaction)

        assert flattened['enzyme_name'] == 'TestEnzyme'
        assert flattened['substrates'] == 'substrate1'
        assert flattened['products'] == 'product1'
        assert flattened['mutations'] == 'F113L|D162A'  # Pipe delimiter
        assert flattened['yield_percent'] == 85.5
        assert flattened['temperature'] == '25 °C'
        assert flattened['pH'] == '7.3'
        assert flattened['Km'] == 0.5
        assert flattened['kcat'] == 25.0

    def test_flatten_reaction_empty_fields(self):
        """Test flattening with empty/null fields."""
        reaction = {
            'enzyme_name': 'TestEnzyme',
            'substrates': [],
            'products': [],
            'mutations': [],
            'yield_percent': None,
            'citations': [],
            'pdb_ids': [],
            'conditions': {},
            'kinetics': {}
        }

        flattened = flatten_reaction(reaction)

        assert flattened['enzyme_name'] == 'TestEnzyme'
        assert flattened['substrates'] == ''
        assert flattened['products'] == ''
        assert flattened['mutations'] == ''
        assert flattened['yield_percent'] == ''
        assert flattened['temperature'] == ''
        assert flattened['Km'] == ''

    def test_mutations_use_pipe_delimiter(self):
        """Test that mutations field uses pipe delimiter."""
        reaction = {
            'enzyme_name': 'TestEnzyme',
            'mutations': ['F113L', 'D162A', 'Ile54Val'],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        assert flattened['mutations'] == 'F113L|D162A|Ile54Val'
        assert ',' not in flattened['mutations']  # No comma delimiter


class TestCSVQuoting:
    """Test CSV quoting for fields with special characters."""

    def test_csv_quoting_with_commas_in_notes(self):
        """Test that CSV writer properly quotes fields with commas."""
        reactions = [{
            'enzyme_name': 'Test',
            'mutations': ['F113L'],
            'substrates': [],
            'products': [],
            'conditions': {'notes': '1 mM acetonitrile, 96-well plates, 200 µl volume'},
            'kinetics': {},
            'citations': [],
            'pdb_ids': [],
            'yield_percent': None
        }]

        # Write to temporary CSV
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            convert_to_csv(reactions, output_path, validate=False)

            # Read back and verify
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            # Commas should be preserved within quoted field
            assert '96-well plates' in rows[0]['notes']
            assert '200 µl volume' in rows[0]['notes']
        finally:
            os.unlink(output_path)

    def test_csv_roundtrip_preserves_data(self):
        """Test that CSV roundtrip preserves all data."""
        reactions = [
            {
                'enzyme_name': 'Enzyme1',
                'mutations': ['F113L', 'D162A'],
                'substrates': ['substrate1, substrate2'],  # Substrate with comma
                'conditions': {'notes': 'Complex buffer, pH 7.3, 25 °C'},
                'kinetics': {'kcat': 25.0, 'kcat_unit': 's^-1'},
                'citations': [],
                'pdb_ids': [],
                'products': [],
                'yield_percent': None
            },
            {
                'enzyme_name': 'Enzyme2',
                'mutations': ['Ile54Val'],
                'substrates': ['substrate3'],
                'conditions': {},
                'kinetics': {},
                'citations': [],
                'pdb_ids': [],
                'products': [],
                'yield_percent': None
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_path = f.name

        try:
            convert_to_csv(reactions, output_path, validate=False)

            # Read back
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]['enzyme_name'] == 'Enzyme1'
            assert rows[0]['mutations'] == 'F113L|D162A'
            assert rows[1]['enzyme_name'] == 'Enzyme2'
            assert rows[1]['mutations'] == 'Ile54Val'
        finally:
            os.unlink(output_path)


class TestValidation:
    """Test validate_and_clean function."""

    def test_validate_outliers_detects_impossible_tm(self):
        """Test that validation catches impossible melting temperatures."""
        reactions = [
            {
                'enzyme_name': 'Invalid1',
                'Tm': -10,  # Below absolute zero
                'mutations': '',
                'substrates': '',
                'products': '',
                'temperature': '',
                'pH': '',
                'buffer': '',
                'time': '',
                'notes': '',
                'Km': '',
                'Km_unit': '',
                'Vmax': '',
                'Vmax_unit': '',
                'kcat': '',
                'kcat_unit': '',
                'kcat_over_KM': '',
                'kcat_over_KM_unit': '',
                'Tm_unit': '°C',
                'yield_percent': '',
                'citations': '',
                'pdb_ids': ''
            },
            {
                'enzyme_name': 'Invalid2',
                'Tm': 200,  # Above protein denaturation
                'mutations': '',
                'substrates': '',
                'products': '',
                'temperature': '',
                'pH': '',
                'buffer': '',
                'time': '',
                'notes': '',
                'Km': '',
                'Km_unit': '',
                'Vmax': '',
                'Vmax_unit': '',
                'kcat': '',
                'kcat_unit': '',
                'kcat_over_KM': '',
                'kcat_over_KM_unit': '',
                'Tm_unit': '°C',
                'yield_percent': '',
                'citations': '',
                'pdb_ids': ''
            }
        ]

        cleaned, warnings = validate_and_clean(reactions)

        assert len(warnings) == 2
        assert any('Invalid1' in w and '-10' in w and 'unrealistic' in w for w in warnings)
        assert any('Invalid2' in w and '200' in w and 'unrealistic' in w for w in warnings)

    def test_validate_detects_negative_kcat(self):
        """Test that validation catches negative turnover rates."""
        reactions = [{
            'enzyme_name': 'Invalid',
            'kcat': -5,  # Negative turnover
            'kcat_unit': 's^-1',
            'mutations': '',
            'substrates': '',
            'products': '',
            'temperature': '',
            'pH': '',
            'buffer': '',
            'time': '',
            'notes': '',
            'Km': '',
            'Km_unit': '',
            'Vmax': '',
            'Vmax_unit': '',
            'kcat_over_KM': '',
            'kcat_over_KM_unit': '',
            'Tm': '',
            'Tm_unit': '',
            'yield_percent': '',
            'citations': '',
            'pdb_ids': ''
        }]

        cleaned, warnings = validate_and_clean(reactions)

        assert len(warnings) == 1
        assert 'Invalid' in warnings[0]
        assert 'kcat' in warnings[0]
        assert 'negative' in warnings[0]

    def test_validate_detects_missing_units(self):
        """Test that validation catches missing units for kinetic parameters."""
        reactions = [{
            'enzyme_name': 'Incomplete',
            'kcat': 25.0,
            'kcat_unit': '',  # Missing unit
            'Km': 0.5,
            'Km_unit': 'mM',
            'mutations': '',
            'substrates': '',
            'products': '',
            'temperature': '',
            'pH': '',
            'buffer': '',
            'time': '',
            'notes': '',
            'Vmax': '',
            'Vmax_unit': '',
            'kcat_over_KM': '',
            'kcat_over_KM_unit': '',
            'Tm': '',
            'Tm_unit': '',
            'yield_percent': '',
            'citations': '',
            'pdb_ids': ''
        }]

        cleaned, warnings = validate_and_clean(reactions)

        assert len(warnings) == 1
        assert 'Incomplete' in warnings[0]
        assert 'kcat' in warnings[0]
        assert 'no unit' in warnings[0]

    def test_validate_handles_special_values(self):
        """Test that validation handles n.c., n.d., n.m. values."""
        reactions = [{
            'enzyme_name': 'Valid',
            'kcat': 'n.c.',  # Not calculable
            'kcat_unit': 's^-1',
            'mutations': '',
            'substrates': '',
            'products': '',
            'temperature': '',
            'pH': '',
            'buffer': '',
            'time': '',
            'notes': '',
            'Km': '',
            'Km_unit': '',
            'Vmax': '',
            'Vmax_unit': '',
            'kcat_over_KM': '',
            'kcat_over_KM_unit': '',
            'Tm': '',
            'Tm_unit': '',
            'yield_percent': '',
            'citations': '',
            'pdb_ids': ''
        }]

        cleaned, warnings = validate_and_clean(reactions)

        # Should not produce warnings for n.c. values
        assert len(warnings) == 0
        assert cleaned[0]['kcat'] == ''  # Converted to empty string

    def test_validate_yield_percent_range(self):
        """Test that validation checks yield percent is 0-100."""
        reactions = [{
            'enzyme_name': 'Invalid',
            'yield_percent': 150,  # Over 100%
            'mutations': '',
            'substrates': '',
            'products': '',
            'temperature': '',
            'pH': '',
            'buffer': '',
            'time': '',
            'notes': '',
            'Km': '',
            'Km_unit': '',
            'Vmax': '',
            'Vmax_unit': '',
            'kcat': '',
            'kcat_unit': '',
            'kcat_over_KM': '',
            'kcat_over_KM_unit': '',
            'Tm': '',
            'Tm_unit': '',
            'citations': '',
            'pdb_ids': ''
        }]

        cleaned, warnings = validate_and_clean(reactions)

        assert len(warnings) == 1
        assert 'yield' in warnings[0].lower()
        assert '0-100' in warnings[0]

    def test_validate_mutation_cleaning(self):
        """Test that validation cleans mutation formatting."""
        reactions = [{
            'enzyme_name': 'Test',
            'mutations': 'F113L | D162A | Ile54Val',  # Extra spaces
            'substrates': '',
            'products': '',
            'temperature': '',
            'pH': '',
            'buffer': '',
            'time': '',
            'notes': '',
            'Km': '',
            'Km_unit': '',
            'Vmax': '',
            'Vmax_unit': '',
            'kcat': '',
            'kcat_unit': '',
            'kcat_over_KM': '',
            'kcat_over_KM_unit': '',
            'Tm': '',
            'Tm_unit': '',
            'yield_percent': '',
            'citations': '',
            'pdb_ids': ''
        }]

        cleaned, warnings = validate_and_clean(reactions)

        # Mutations should be cleaned (no extra spaces)
        assert cleaned[0]['mutations'] == 'F113L|D162A|Ile54Val'
        assert len(warnings) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
