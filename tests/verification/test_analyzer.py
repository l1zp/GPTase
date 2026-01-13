"""Test script for document structure analyzer."""

import sys
import json
import asyncio
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.document_structure_analyzer import (
    DocumentStructureAnalyzer,
    save_document_analysis,
)


@pytest.mark.asyncio
async def test_analyzer():
    """Test the document structure analyzer."""
    analyzer = DocumentStructureAnalyzer()

    # Read a sample of the document
    with open('data/listov2025.md', 'r') as f:
        text = f.read()

    print(f"Document size: {len(text)} characters")
    print(f"Lines: {text.count(chr(10)) + 1}")
    print()

    # Analyze
    print("Analyzing document structure...")
    result = await analyzer.execute(text=text, source_file='data/listov2025.md')

    if result.status.value == 'success':
        data = result.data
        print(f"✓ Analysis complete!")
        print(f"  - Total sections: {len(data.get('sections', []))}")
        print(f"  - Total tables found: {data['total_tables']}")
        print(f"  - Reaction-related tables: {sum(1 for t in data['tables'] if t.get('is_reaction_related'))}")
        print(f"  - Key paragraphs: {data['total_key_paragraphs']}")
        print()

        # Show section structure
        print("=== Document Sections ===")
        for section in data.get('sections', [])[:10]:
            indent = "  " * (section['level'] - 1)
            print(f"{indent}- {section['title']} (Level {section['level']})")
        print()

        # Show tables
        print("=== Tables Found ===")
        for i, table in enumerate(data['tables'][:5]):
            print(f"\nTable {i+1}:")
            print(f"  Location: Lines {table['start_line']}-{table['end_line']}")
            print(f"  Headers: {table['headers']}")
            print(f"  Rows: {table['row_count']}")
            print(f"  Reaction related: {table['is_reaction_related']}")
            if table['rows']:
                print(f"  First row preview: {table['rows'][0][:2]}")
        print()

        # Show key paragraphs
        print("=== Key Paragraphs (first 3) ===")
        for i, para in enumerate(data.get('key_paragraphs', [])[:3]):
            print(f"\nParagraph {i+1}:")
            print(f"  Section: {para['section']}")
            print(f"  Location: Line {para['start_line']}")
            print(f"  Keywords: {', '.join(para['keywords_found'][:5])}")
            print(f"  Content preview: {para['content'][:150]}...")
        print()

        # Save analysis
        output_dir = Path('data/analysis')
        save_document_analysis(data, output_dir)
        print(f"✓ Analysis saved to: data/analysis/listov2025_structure_analysis.json")
        print()

        # Show what content would be extracted
        from src.tools.document_structure_analyzer import get_relevant_content_for_extraction
        relevant = get_relevant_content_for_extraction(data)
        print(f"=== Relevant Content for Extraction ===")
        print(f"Total relevant content size: {len(relevant)} characters")
        print(f"Preview:")
        print(relevant[:500])
        print("...")

    else:
        print(f"✗ Analysis failed: {result.error}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_analyzer())
    sys.exit(exit_code)
