"""Test LLM-enhanced document structure analyzer."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.document_structure_analyzer import DocumentStructureAnalyzer
from src.utils import default_manager


@pytest.mark.asyncio
async def test_llm_enhanced_analyzer():
    """Test the LLM-enhanced document structure analyzer."""
    # Initialize manager
    manager = default_manager()

    # Create LLM-enhanced analyzer
    analyzer = DocumentStructureAnalyzer(model_manager=manager,
                                         use_llm_enhancement=True)

    # Read a sample document
    with open('data/listov2025.md', 'r') as f:
        text = f.read()

    print(f"Document size: {len(text)} characters")
    print("\n" + "=" * 60)
    print("Testing LLM-Enhanced Document Structure Analyzer")
    print("=" * 60 + "\n")

    # Analyze with LLM enhancement
    print("Analyzing document with LLM enhancement...")
    result = await analyzer.execute(text=text, source_file='data/listov2025.md')

    assert result.status.value == 'success', f"Analysis failed: {result.error}"
    data = result.data

    print(f"✓ LLM-enhanced analysis complete!")
    print(f"  - Total tables: {data['total_tables']}")
    print(
        f"  - Reaction-related tables: {sum(1 for t in data['tables'] if t.get('is_reaction_related'))}"
    )
    print(f"  - Key paragraphs: {data['total_key_paragraphs']}")
    print(f"  - LLM enhanced: {data.get('llm_enhanced', False)}")
    print()

    # Show LLM analysis for each table
    print("=" * 60)
    print("LLM Analysis Results for Tables")
    print("=" * 60 + "\n")

    for table in data['tables']:
        print(f"Table {table['table_number']}:")
        print(f"  Type: {table['type']}")
        print(f"  Headers: {table.get('headers', [])}")
        print(f"  Rows: {table['row_count']}")
        print(f"  Reaction related: {table['is_reaction_related']}")

        # Show LLM analysis if available
        if 'llm_analysis' in table:
            llm_analysis = table['llm_analysis']
            print(f"  LLM Analysis:")
            print(f"    - Description: {llm_analysis.get('description', 'N/A')}")
            print(f"    - Confidence: {llm_analysis.get('confidence', 0):.2f}")
            print(f"    - Data types: {', '.join(llm_analysis.get('data_types', []))}")
            if llm_analysis.get('enzyme_count'):
                print(f"    - Enzyme count: {llm_analysis['enzyme_count']}")

        print()


@pytest.mark.asyncio
async def test_analyzer_without_llm():
    """Test the analyzer without LLM enhancement (baseline)."""
    analyzer = DocumentStructureAnalyzer(model_manager=None, use_llm_enhancement=False)

    # Simple test with table content
    test_text = """
# Test Document

## Table 1

| Enzyme | kcat (s-1) | KM (mM) |
|--------|-----------|---------|
| E1     | 10.5      | 0.5     |
| E2     | 20.3      | 1.2     |

## Random Section

This is just text without tables.
"""

    result = await analyzer.execute(text=test_text, source_file='test_file')
    assert result.status.value == 'success'
    data = result.data

    # Should still work without LLM
    assert data['total_tables'] >= 1  # May detect 1 or more tables
    assert not data.get('llm_enhanced', False)

    # At least one table should be detected
    assert len(data['tables']) > 0

    print("✓ Non-LLM analyzer works correctly")


if __name__ == "__main__":
    import asyncio

    async def main():
        print("Running tests...\n")

        # Test 1: Non-LLM analyzer
        print("Test 1: Non-LLM Analyzer")
        print("-" * 40)
        test_analyzer_without_llm()
        print()

        # Test 2: LLM-enhanced analyzer (requires API key)
        print("Test 2: LLM-Enhanced Analyzer")
        print("-" * 40)
        try:
            await test_llm_enhanced_analyzer()
        except Exception as e:
            print(f"⚠ LLM test failed (expected if no API key): {e}")

    asyncio.run(main())
