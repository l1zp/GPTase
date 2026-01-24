"""Tests for mutation extraction and validation."""

import pytest
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.json_to_csv import flatten_reaction


def is_valid_mutation_format(mutation: str) -> bool:
    """
    Validate mutation format.

    Standard mutation formats:
    - Point mutations: F113L, D162A (one letter code + number + one letter code)
    - Extended notation: Ile54Val, Phe92His (three letter code + number + three letter code)

    Returns:
        True if mutation format is valid, False otherwise
    """
    if not mutation or not isinstance(mutation, str):
        return False

    mutation = mutation.strip()

    # Check for standard one-letter format (e.g., F113L)
    if len(mutation) >= 3:
        # Format: Letter + Number(s) + Letter
        has_letter_start = mutation[0].isalpha()
        has_digit_middle = any(c.isdigit() for c in mutation[1:-1])
        has_letter_end = mutation[-1].isalpha()

        if has_letter_start and has_digit_middle and has_letter_end:
            return True

    # Check for extended three-letter format (e.g., Ile54Val)
    # This is more complex and would require amino acid code mapping
    # For now, we'll be lenient with extended formats
    if len(mutation) > 5:
        parts = mutation.split()
        if len(parts) == 2:
            # Could be "Ile54Val" format
            return True

    return False


class TestMutationFormatValidation:
    """Test mutation format validation."""

    def test_valid_point_mutations(self):
        """Test validation of standard point mutations."""
        valid_mutations = [
            'F113L',    # Standard format
            'D162A',    # Standard format
            'I54V',     # Short format
            'Y123F',    # Standard format
            'W100R',    # Standard format
        ]

        for mutation in valid_mutations:
            assert is_valid_mutation_format(mutation), f"{mutation} should be valid"

    def test_valid_extended_mutations(self):
        """Test validation of extended notation mutations."""
        valid_extended = [
            'Ile54Val',
            'Phe92His',
            'Ile136Val',
            'Phe113Leu',
            'Asp162Ala',
        ]

        for mutation in valid_extended:
            # Extended formats are handled leniently
            assert is_valid_mutation_format(mutation), f"{mutation} should be valid"

    def test_invalid_mutation_formats(self):
        """Test rejection of invalid mutation formats."""
        invalid_mutations = [
            'D162',      # Missing second amino acid
            '162A',      # Missing first amino acid
            'FD',        # No number
            '123',       # Only numbers
            '',          # Empty string
            'F',         # Single letter
        ]

        for mutation in invalid_mutations:
            result = is_valid_mutation_format(mutation)
            assert not result, f"{mutation} should be invalid"

    def test_mutation_case_sensitivity(self):
        """Test that mutation validation handles different cases."""
        # Standard format is case-sensitive (uppercase letters)
        assert is_valid_mutation_format('F113L')
        assert is_valid_mutation_format('f113l')  # Lowercase should also work
        assert is_valid_mutation_format('F113l')  # Mixed case


class TestMutationExtraction:
    """Test mutation extraction in flatten_reaction."""

    def test_extract_single_mutation(self):
        """Test extraction of single mutation."""
        reaction = {
            'enzyme_name': 'TestEnzyme',
            'mutations': ['F113L'],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        assert flattened['mutations'] == 'F113L'

    def test_extract_multiple_mutations(self):
        """Test extraction of multiple mutations."""
        reaction = {
            'enzyme_name': 'Des27.7',
            'mutations': ['Ile54Val', 'Phe92His', 'Ile136Val', 'Val183Ile', 'Leu236Val', 'Ile216Val'],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        expected = 'Ile54Val|Phe92His|Ile136Val|Val183Ile|Leu236Val|Ile216Val'
        assert flattened['mutations'] == expected

    def test_extract_mutations_mixed_formats(self):
        """Test extraction of mutations in mixed formats."""
        reaction = {
            'enzyme_name': 'MixedVariant',
            'mutations': ['F113L', 'Ile54Val', 'D162A'],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        expected = 'F113L|Ile54Val|D162A'
        assert flattened['mutations'] == expected

    def test_extract_empty_mutations(self):
        """Test extraction when no mutations are present."""
        reaction = {
            'enzyme_name': 'WildType',
            'mutations': [],
            'substrates': ['substrate1'],
            'products': ['product1'],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        assert flattened['mutations'] == ''

    def test_extract_null_mutations(self):
        """Test extraction when mutations field is None."""
        reaction = {
            'enzyme_name': 'WildType',
            'mutations': None,
            'substrates': ['substrate1'],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        assert flattened['mutations'] == ''

    def test_mutations_preserve_pipe_delimiter(self):
        """Test that mutations use pipe delimiter, not comma."""
        reaction = {
            'enzyme_name': 'Test',
            'mutations': ['F113L', 'D162A', 'Ile54Val'],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        # Should use pipe delimiter
        assert '|' in flattened['mutations']
        # Should NOT use comma delimiter (unless part of amino acid name)
        # Check that mutations are separated by pipes
        assert flattened['mutations'].count('|') == 2


class TestMutationFormats:
    """Test various mutation format representations."""

    def test_point_mutations_from_paper(self):
        """Test point mutations mentioned in the paper."""
        paper_mutations = [
            'F113L',  # Phe113Leu
            'F113M',  # Phe113Met
            'D162A',  # Asp162Ala
        ]

        for mutation in paper_mutations:
            assert is_valid_mutation_format(mutation), f"{mutation} from paper should be valid"

    def test_des27_7_mutations(self):
        """Test Des27.7 mutations from the paper."""
        des27_7_mutations = [
            'Ile54Val',
            'Phe92His',
            'Ile136Val',
            'Val183Ile',
            'Leu236Val',
            'Ile216Val',
        ]

        for mutation in des27_7_mutations:
            assert is_valid_mutation_format(mutation), f"{mutation} from Des27.7 should be valid"

    def test_mutation_string_preservation(self):
        """Test that mutation strings are preserved as-is."""
        original_mutations = ['Ile54Val', 'Phe92His', 'Ile136Val']

        reaction = {
            'enzyme_name': 'Test',
            'mutations': original_mutations.copy(),
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        # When split back, should get original mutations
        reconstructed = flattened['mutations'].split('|')
        assert reconstructed == original_mutations


class TestMutationEdgeCases:
    """Test edge cases in mutation handling."""

    def test_mutation_with_spaces(self):
        """Test mutations with extra spaces are handled."""
        reaction = {
            'enzyme_name': 'Test',
            'mutations': ['F113L ', ' D162A', ' Ile54Val '],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        # Spaces should be preserved in the string
        # (validation would clean them, but flatten_reaction doesn't)
        assert 'F113L' in flattened['mutations']
        assert 'D162A' in flattened['mutations']

    def test_duplicate_mutations(self):
        """Test handling of duplicate mutations."""
        reaction = {
            'enzyme_name': 'Test',
            'mutations': ['F113L', 'F113L', 'D162A'],
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        # Duplicates should be preserved (validation could deduplicate)
        assert flattened['mutations'].count('F113L') == 2

    def test_mutation_order_preserved(self):
        """Test that mutation order is preserved."""
        original_order = ['Ile54Val', 'Phe92His', 'Ile136Val']

        reaction = {
            'enzyme_name': 'Test',
            'mutations': original_order.copy(),
            'substrates': [],
            'products': [],
            'conditions': {},
            'kinetics': {},
            'citations': [],
            'pdb_ids': []
        }

        flattened = flatten_reaction(reaction)

        reconstructed = flattened['mutations'].split('|')
        assert reconstructed == original_order


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
