"""Tests for PDB to EC number conversion."""

import pytest
import csv
import tempfile
import os
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.add_ec_numbers import extract_pdb_ids_from_csv, lookup_ec_numbers, add_ec_numbers_to_csv


class TestExtractPDBIds:
    """Test PDB ID extraction from CSV."""

    def test_extract_pdb_ids_from_csv(self):
        """Test extracting PDB IDs from CSV file."""
        # Create temporary CSV with PDB IDs
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_path = f.name
            writer = csv.writer(f)
            writer.writerow(['enzyme_name', 'pdb_ids', 'kcat'])
            writer.writerow(['Enzyme1', '1ABC,2DEF', '25.0'])
            writer.writerow(['Enzyme2', '3GHI', '30.0'])
            writer.writerow(['Enzyme3', '', '20.0'])  # No PDB IDs
            writer.writerow(['Enzyme4', '4JKL,5MNO,6PQR', '15.0'])

        try:
            result = extract_pdb_ids_from_csv(csv_path)

            assert len(result) == 3  # Only enzymes with PDB IDs
            assert result['Enzyme1'] == ['1ABC', '2DEF']
            assert result['Enzyme2'] == ['3GHI']
            assert result['Enzyme4'] == ['4JKL', '5MNO', '6PQR']
            assert 'Enzyme3' not in result  # No PDB IDs
        finally:
            os.unlink(csv_path)

    def test_extract_pdb_ids_empty_csv(self):
        """Test extracting from CSV with no PDB IDs."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_path = f.name
            writer = csv.writer(f)
            writer.writerow(['enzyme_name', 'pdb_ids'])
            writer.writerow(['Enzyme1', ''])
            writer.writerow(['Enzyme2', ''])

        try:
            result = extract_pdb_ids_from_csv(csv_path)
            assert len(result) == 0
        finally:
            os.unlink(csv_path)

    def test_extract_pdb_ids_whitespace_handling(self):
        """Test that whitespace in PDB IDs is handled correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_path = f.name
            writer = csv.writer(f)
            writer.writerow(['enzyme_name', 'pdb_ids'])
            writer.writerow(['Enzyme1', '1ABC, 2DEF , 3GHI'])

        try:
            result = extract_pdb_ids_from_csv(csv_path)
            assert result['Enzyme1'] == ['1ABC', '2DEF', '3GHI']
        finally:
            os.unlink(csv_path)


class TestLookupECNumbers:
    """Test EC number lookup from PDB IDs."""

    def test_lookup_ec_numbers_real_pdb(self):
        """Test looking up EC numbers for a real PDB ID with known EC numbers."""
        # 4FB7 is a lyase with EC 4.1.1.48
        pdb_ids = ['4FB7']
        results = lookup_ec_numbers(pdb_ids)

        assert '4FB7' in results
        result = results['4FB7']
        assert 'ec_numbers' in result
        # Should find at least one EC number
        assert len(result['ec_numbers']) >= 1
        assert '4.1.1.48' in result['ec_numbers']

    def test_lookup_ec_numbers_invalid_pdb(self):
        """Test looking up EC numbers for invalid PDB ID."""
        pdb_ids = ['XXXX']  # Invalid PDB ID
        results = lookup_ec_numbers(pdb_ids)

        assert 'XXXX' in results
        result = results['XXXX']
        # Should handle error gracefully
        assert 'ec_numbers' in result
        assert len(result['ec_numbers']) == 0

    def test_lookup_ec_numbers_multiple_pdbs(self):
        """Test looking up EC numbers for multiple PDB IDs."""
        pdb_ids = ['1A6Z', '4FB7']  # Both have EC numbers
        results = lookup_ec_numbers(pdb_ids)

        assert len(results) == 2
        for pdb_id in pdb_ids:
            assert pdb_id in results
            assert 'ec_numbers' in results[pdb_id]


class TestAddECNumbersToCSV:
    """Test adding EC numbers to CSV."""

    def test_add_ec_numbers_to_csv(self):
        """Test adding EC numbers to CSV with PDB IDs."""
        # Create input CSV
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            input_csv = f.name
            writer = csv.writer(f)
            writer.writerow(['enzyme_name', 'pdb_ids', 'kcat'])
            writer.writerow(['Enzyme1', '1ABC', '25.0'])
            writer.writerow(['Enzyme2', '', '30.0'])

        output_csv = input_csv.replace('.csv', '_output.csv')

        try:
            # Mock lookup results
            pdb_ec_results = {
                '1ABC': {
                    'pdb_id': '1ABC',
                    'ec_numbers': ['1.1.1.1', '1.1.1.2'],
                    'errors': []
                }
            }

            add_ec_numbers_to_csv(input_csv, output_csv, pdb_ec_results)

            # Verify output
            with open(output_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]['ec_numbers'] == '1.1.1.1|1.1.1.2'
            assert rows[0]['ec_count'] == '2'
            assert rows[1]['ec_numbers'] == ''  # No PDB IDs
            assert rows[1]['ec_count'] == ''

        finally:
            os.unlink(input_csv)
            if os.path.exists(output_csv):
                os.unlink(output_csv)

    def test_add_ec_numbers_deduplicates(self):
        """Test that duplicate EC numbers are removed."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            input_csv = f.name
            writer = csv.writer(f)
            writer.writerow(['enzyme_name', 'pdb_ids'])
            writer.writerow(['Enzyme1', '1ABC,2DEF'])

        output_csv = input_csv.replace('.csv', '_output.csv')

        try:
            # Mock lookup results with duplicate EC numbers
            pdb_ec_results = {
                '1ABC': {
                    'pdb_id': '1ABC',
                    'ec_numbers': ['1.1.1.1', '1.1.1.2'],
                    'errors': []
                },
                '2DEF': {
                    'pdb_id': '2DEF',
                    'ec_numbers': ['1.1.1.1', '1.1.1.3'],  # Duplicate 1.1.1.1
                    'errors': []
                }
            }

            add_ec_numbers_to_csv(input_csv, output_csv, pdb_ec_results)

            # Verify deduplication
            with open(output_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            ec_numbers = rows[0]['ec_numbers'].split('|')
            assert len(ec_numbers) == 3  # 1.1.1.1, 1.1.1.2, 1.1.1.3 (deduplicated)
            assert ec_numbers.count('1.1.1.1') == 1

        finally:
            os.unlink(input_csv)
            if os.path.exists(output_csv):
                os.unlink(output_csv)

    def test_add_ec_numbers_preserves_existing_data(self):
        """Test that existing columns are preserved."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            input_csv = f.name
            writer = csv.writer(f)
            writer.writerow(['enzyme_name', 'pdb_ids', 'kcat', 'kcat_unit'])
            writer.writerow(['Enzyme1', '1ABC', '25.0', 's^-1'])

        output_csv = input_csv.replace('.csv', '_output.csv')

        try:
            pdb_ec_results = {
                '1ABC': {
                    'pdb_id': '1ABC',
                    'ec_numbers': ['1.1.1.1'],
                    'errors': []
                }
            }

            add_ec_numbers_to_csv(input_csv, output_csv, pdb_ec_results)

            # Verify all columns preserved
            with open(output_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert rows[0]['enzyme_name'] == 'Enzyme1'
            assert rows[0]['pdb_ids'] == '1ABC'
            assert rows[0]['kcat'] == '25.0'
            assert rows[0]['kcat_unit'] == 's^-1'
            assert rows[0]['ec_numbers'] == '1.1.1.1'

        finally:
            os.unlink(input_csv)
            if os.path.exists(output_csv):
                os.unlink(output_csv)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
