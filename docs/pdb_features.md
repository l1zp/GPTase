# PDB Features in GPTase

This document consolidates all PDB-related functionality in the GPTase enzyme extraction pipeline.

## Overview

The pipeline provides comprehensive PDB ID handling with three key features:
1. **Extraction**: Automatic PDB ID extraction from scientific literature
2. **Classification**: Boolean flags indicating novelty (new vs. previous work)
3. **Normalization**: Separated CSV structure following database design principles

## Data Architecture

### File Structure

```
data/extraction/
├── {paper}_extraction.json      # Raw LLM extraction with PDB data
├── {paper}_extraction.csv       # Reaction data (no PDB column by default)
├── enzyme_to_pdb.csv            # Enzyme-PDB relationships (junction table)
└── pdb_info.csv                 # PDB metadata (EC numbers, titles)
```

### JSON Schema

```json
{
  "reactions": [{
    "enzyme_name": "Des27",
    "pdb_ids": ["9HVB", "9HVH", "1I4A"],
    "pdb_is_new": [true, true, false],
    "substrates": [...],
    "kinetics": {...}
  }]
}
```

**Fields**:
- `pdb_ids`: List of 4-character PDB identifiers
- `pdb_is_new`: Boolean list indicating novelty (parallel to pdb_ids)
  - `true`: Newly determined in this study
  - `false`: Referenced from previous work

## Feature 1: PDB ID Extraction

### How It Works

**Phase 1: Document Structure Analysis**
- Identifies paragraphs mentioning PDB IDs
- Searches for keywords: "PDB", "crystal structure", "X-ray", etc.
- Outputs: Selected paragraphs with PDB information

**Phase 2: LLM Extraction**
- Parses selected paragraphs
- Extracts PDB IDs with context
- Classifies novelty (see Feature 2)
- Outputs: Structured JSON with `pdb_ids` and `pdb_is_new`

### Extraction Accuracy

**Example from listov2025.md**:
```
Before fix: 0 PDB IDs extracted
After fix:  32/32 enzymes have PDB IDs (8 unique PDBs)
```

**Problem Solved**: Document structure analyzer wasn't selecting PDB-containing paragraphs. Fixed by adding explicit PDB keywords to selection prompt.

## Feature 2: Novelty Classification

### Boolean Classification System

**Mark as `true` (new structure)** when text indicates:
- "we determined the crystal structure"
- "we solved"
- "deposited as PDB entry"
- "this study determined"
- "new structure"

**Mark as `false` (previous work)** when text indicates:
- "template structure"
- "previously determined"
- "used as starting point"
- "reported by [other authors]"
- "design template"

**Default**: `false` (conservative when uncertain)

### Example

**Text**: "In this study, we determined the crystal structures of Des27 and Des27.7 (PDB entries 9HVB and 9HVH) at 2.1 Å resolution. These were compared to template structure 1I4A used for design."

**Extraction**:
```json
{
  "enzyme_name": "Des27",
  "pdb_ids": ["9HVB", "9HVH", "1I4A"],
  "pdb_is_new": [true, true, false]
}
```

### Applications

```python
import pandas as pd

# Load enzyme-PDB relationships
df = pd.read_csv('data/extraction/enzyme_to_pdb.csv')

# Calculate novelty rate
new_count = df['pdb_is_new'].sum()
total_count = len(df)
novelty_rate = new_count / total_count * 100

print(f"Novel structures: {new_count}/{total_count} ({novelty_rate:.1f}%)")

# Get paper's contribution
new_pdbs = df[df['pdb_is_new'] == True]['pdb_id'].unique()
print(f"This paper contributed: {sorted(new_pdbs)}")
```

## Feature 3: Normalized CSV Structure

### Database Design Principles

**Separation of Concerns**:
- Reaction data: Kinetics, conditions, substrates
- PDB relationships: Many-to-many enzyme-PDB mapping
- PDB metadata: EC numbers, titles, deposition info

**Benefits**:
- ✅ No redundancy (PDB metadata stored once)
- ✅ Easy updates (change EC in one place)
- ✅ Query flexibility (join as needed)
- ✅ Database-ready (can import to SQL)

### File Formats

#### enzyme_to_pdb.csv (Junction Table)

```csv
enzyme_name,pdb_id,pdb_is_new
Des27,1I4A,false
Des27,9HVB,true
Des27,9HVH,true
Des27.1,1I4A,false
Des27.1,9HVB,true
```

**Schema**:
- `enzyme_name`: Enzyme variant identifier
- `pdb_id`: 4-character PDB code
- `pdb_is_new`: Boolean as string ("true" or "false")

#### pdb_info.csv (Metadata Table)

```csv
pdb_id,ec_numbers,ec_count,title
1JCM,4.1.1.48|5.3.1.24,2,
4FB7,4.1.1.48,1,
9HVB,4.1.1.48,1,
```

**Schema**:
- `pdb_id`: Primary key
- `ec_numbers`: Pipe-delimited EC number list
- `ec_count`: Number of EC numbers
- `title`: PDB structure title (optional)

#### Reaction CSV (without PDB column)

```csv
enzyme_name,substrates,products,kinetics,...
Des27,5-nitrobenzisoxazole,2-nitrophenol,...
```

**Note**: PDB IDs excluded by default. Use `--include-pdb-ids` flag to add them back (not recommended).

### Query Examples

**Find all PDBs for an enzyme**:
```bash
grep "Des27.7" data/extraction/enzyme_to_pdb.csv | cut -d',' -f2
```

**Find enzymes with specific EC number**:
```python
import pandas as pd

# Step 1: Find PDBs with EC 4.1.1.48
pdb_df = pd.read_csv('pdb_info.csv')
pdbs = pdb_df[pdb_df['ec_numbers'].str.contains('4.1.1.48')]['pdb_id']

# Step 2: Find enzymes using those PDBs
rel_df = pd.read_csv('enzyme_to_pdb.csv')
enzymes = rel_df[rel_df['pdb_id'].isin(pdbs)]['enzyme_name'].unique()

print(f"Enzymes with EC 4.1.1.48: {len(enzymes)}")
```

## Pipeline Usage

### 1. Extract from Literature

```bash
python examples/reaction_extractor.py -i data/paper.md
```

**Output**: `{paper}_extraction.json` with PDB IDs and novelty flags

### 2. Generate CSV Files

```bash
# Step 1: Convert JSON to CSV (without PDB column)
python pipelines/json_to_csv.py -i data/extraction/paper_extraction.json

# Step 2: Extract PDB information to separate files
python pipelines/extract_pdb_info.py -i data/extraction/paper_extraction.json
```

**Output**:
- `paper_extraction.csv` - Reaction data
- `enzyme_to_pdb.csv` - Enzyme-PDB relationships
- `pdb_info.csv` - PDB metadata with EC numbers

### 3. Include PDB Column in Reaction CSV (Optional)

```bash
python pipelines/json_to_csv.py --include-pdb-ids
```

**Not recommended**: Creates data redundancy. Use separate PDB files instead.

## EC Number Lookup

### Automatic EC Number Retrieval

The pipeline queries RCSB PDB Data API to retrieve EC numbers for all PDB IDs:

```python
from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb_sync

result = get_ec_numbers_for_pdb_sync("4FB7")
# Returns: {"pdb_id": "4FB7", "ec_numbers": ["4.1.1.48"], ...}
```

### API Details

- **Endpoint**: RCSB PDB Data API (core + legacy)
- **Rate limiting**: 4 concurrent requests
- **Timeout**: 10 seconds per request
- **Retries**: 3 attempts with exponential backoff

### Multiple EC Numbers

Some PDB entries have multiple EC numbers:

| PDB ID | EC Numbers | Enzyme Activities |
|--------|------------|-------------------|
| 1JCM   | 4.1.1.48, 5.3.1.24 | Lyase + Isomerase |
| 4FB7   | 4.1.1.48 | Lyase only |

**Why**: Proteins can have multiple catalytic activities or promiscuous functions.

## Testing

All PDB features have comprehensive test coverage:

```bash
# Run all PDB tests
pytest tests/test_pdb_novelty.py tests/test_pdb_data_structure.py -v
```

**Test coverage**:
- ✅ PDB extraction from JSON
- ✅ Novelty classification (boolean flags)
- ✅ CSV generation (enzyme_to_pdb.csv, pdb_info.csv)
- ✅ EC number lookup
- ✅ Data normalization (no redundancy)
- ✅ Real-world scenarios

## Real-World Example: Listov 2025

### Statistics

| Metric | Value |
|--------|-------|
| Enzyme variants | 32 |
| Unique PDB IDs | 8 |
| Total relationships | 256 (32 × 8) |
| New structures | 3 (9HVB, 9HVH, 9HVG) |
| Template structures | 5 (1I4A, 1JCM, 1LBF, 1VC4, 4FB7) |
| Novelty rate | 37.5% (3/8) |
| EC coverage | 87.5% (7/8 have EC numbers) |

### Data Distribution

```
New structures (this paper):
  - 9HVB, 9HVH, 9HVG (determined in this study)

Template structures (previous work):
  - 1I4A, 1JCM, 1LBF, 1VC4, 4FB7 (used for design)
  - All 32 enzymes reference these 5 templates
```

### CSV Output

```csv
enzyme_name,pdb_id,pdb_is_new
De61,1I4A,false
De61,9HVB,true
Des27,1I4A,false
Des27,9HVB,true
...
```

## Best Practices

### 1. Use Separate PDB Files

**Do**:
```bash
python pipelines/json_to_csv.py  # No PDB column
python pipelines/extract_pdb_info.py  # Separate PDB files
```

**Don't**:
```bash
python pipelines/json_to_csv.py --include-pdb-ids  # Creates redundancy
```

### 2. Verify Novelty Classification

After extraction, manually review a sample:

```python
import json

with open('data/extraction/paper_extraction.json') as f:
    data = json.load(f)

for rxn in data['reactions'][:5]:  # Check first 5
    print(f"{rxn['enzyme_name']}: {rxn['pdb_is_new']}")
```

### 3. Check EC Number Coverage

```python
import pandas as pd

pdb_df = pd.read_csv('data/extraction/pdb_info.csv')
coverage = (pdb_df['ec_count'] > 0).sum() / len(pdb_df) * 100
print(f"EC number coverage: {coverage:.1f}%")
```

## Troubleshooting

### Problem: No PDB IDs Extracted

**Symptoms**: `pdb_ids` field is empty in extraction JSON

**Diagnosis**:
```bash
# Check Phase 1 output
cat data/analysis/paper_structure_analysis.json | jq '.paragraphs_selected'
```

**Solution**: Verify document structure analyzer selected PDB-containing paragraphs. Add explicit PDB keywords if needed.

### Problem: Wrong Novelty Classification

**Symptoms**: Template marked as `true` or vice versa

**Diagnosis**: Check if text contains explicit markers:
```bash
# Search for "we determined" (should be true)
grep -i "we determined\|we solved\|deposited" data/paper.md

# Search for "template" (should be false)
grep -i "template\|previously\|starting point" data/paper.md
```

**Solution**: Improve LLM prompt with more examples from your specific domain.

### Problem: Missing EC Numbers

**Symptoms**: Some PDB IDs have no EC numbers in `pdb_info.csv`

**Check**:
1. Is PDB ID valid? (4 characters, starts with digit)
2. Does PDB entry exist in RCSB database?
3. Does entry have EC annotations?

**Example**: PDB 1I4A has no EC numbers (legitimate - may be a structure without enzyme annotation).

## Future Enhancements

Potential additions to PDB features:

1. **Deposition Dates**: Add `deposition_date` to track when structures were released
2. **Confidence Scores**: Assign confidence to novelty classification
3. **Source Literature**: Track which paper first deposited each PDB
4. **Structure Resolution**: Add resolution data for X-ray structures
5. **Batch Validation**: Automatically verify PDB IDs against RCSB database

## References

- **RCSB PDB Data API**: https://data.rcsb.org/
- **Enzyme Commission (EC) Numbers**: https://www.qmul.ac.uk/sbcs/iubmb/enzyme/
- **PDB File Format Guide**: https://www.wwpdb.org/documentation/file-format

## Summary

The GPTase PDB feature suite provides:
- ✅ **Automatic extraction** of PDB IDs from literature
- ✅ **Novelty classification** using boolean flags
- ✅ **Normalized structure** following database design principles
- ✅ **EC number lookup** via RCSB API
- ✅ **Comprehensive testing** with 14 passing tests
- ✅ **Production-ready** for real-world analysis

---

**Last Updated**: 2025-01-24
**Maintainer**: GPTase Development Team
**Related Files**:
- `pipelines/extract_pdb_info.py`
- `pipelines/json_to_csv.py`
- `src/tools/pdb_ec_lookup.py`
- `tests/test_pdb_novelty.py`
- `tests/test_pdb_data_structure.py`
