# Enzyme Extraction Data Analysis Pipeline

This directory contains a modular pipeline for processing and analyzing enzyme kinetics extraction data from scientific literature.

## Overview

The pipeline processes JSON extraction results through multiple steps to generate analysis-ready CSV files enriched with variant metadata.

## Pipeline Steps

### Step 1: JSON to CSV Conversion (`json_to_csv.py`)

Converts nested JSON extraction results to flat CSV format.

**Features:**
- Flattens nested structures (conditions, kinetics)
- Handles null values and special characters
- Preserves scientific notation (e.g., superscripts for units)
- Generates basic statistics
- **CSV Structure Safety**:
  - Uses pipe (`|`) delimiter for mutations field to avoid comma conflicts
  - Applies `QUOTE_MINIMAL` quoting for text fields (preserves commas, quotes, newlines)
  - Compatible with Excel, pandas, and other CSV tools
- **Data Validation** (optional with `--validate` flag):
  - Detects impossible values (negative temperatures, unrealistic melting points)
  - Validates numeric fields (kcat, Km, Tm, etc.)
  - Checks for missing units (kcat without kcat_unit, etc.)
  - Handles special values (n.c., n.d., n.m.)
  - Reports warnings for data quality issues

**Input:** `data/extraction/*.json`
**Output:** `data/extraction/*.csv`

**Usage:**
```bash
# Basic conversion
python pipelines/json_to_csv.py

# With custom input/output
python pipelines/json_to_csv.py -i data/extraction/my_extraction.json -o output.csv

# With statistics
python pipelines/json_to_csv.py --stats

# With data validation (recommended)
python pipelines/json_to_csv.py --validate
```

**CSV Format Specification:**
- **Delimiter**: Comma (`,`) for most fields
- **Mutations Field**: Pipe (`|`) delimiter for mutation lists (e.g., `F113L|D162A|Ile54Val`)
- **Quoting**: `QUOTE_MINIMAL` - fields with commas, quotes, or newlines are automatically wrapped in double quotes
- **Encoding**: UTF-8
- **Null Values**: Empty strings

### Step 2: Add Variant Information (`add_variant_info.py`)

Extracts and adds variant metadata by parsing enzyme names.

**Features:**
- Parses enzyme naming conventions from the paper
- Identifies design methods (modular assembly, RoseTTAFold)
- Categorizes variant types (base design, FuncLib, point mutants)
- Tracks mutation counts and optimization strategies

**Enzyme Naming Conventions:**
- `Des27`, `Des61`: Base designs from modular assembly
- `Des27.X`, `Des61.X`: FuncLib variants with X mutations
- `R2.Des39.X`: RoseTTAFold-based designs
- `MA`, `MA + PROSS`: Component ablation variants
- `Des27.7 F113L`: Specific point mutants

**Input:** CSV from Step 1
**Output:**
- `*_with_variants.csv` - Enriched CSV with variant columns
- Added columns: `variant_type`, `design_method`, `optimization`, `mutations`, `mutation_count`, `base_design`

**Usage:**
```bash
python pipelines/add_variant_info.py
python pipelines/add_variant_info.py -i data/extraction/listov2025_extraction.csv
```

### Step 3: Add Mutation Details (`add_mutation_details.py`)

Extracts detailed mutation information from the original paper text.

**Features:**
- Maps enzyme names to specific mutations mentioned in the paper
- Adds known mutations for key variants (Des27.7, point mutants, etc.)
- Tracks total mutation counts, PROSS mutations, active site mutations
- Provides descriptions for well-characterized variants

**Known Mutations from Paper:**
- `Des27.7`: Ile54Val, Phe92His, Ile136Val, Val183Ile, Leu236Val, Ile216Val (6 FuncLib mutations)
- `Des27.7 F113L`: Phe113Leu (point mutant - 123,000 M⁻¹s⁻¹ efficiency!)
- `Des27.7 F113M`: Phe113Met (point mutant)
- `Des27.7 D162A`: Asp162Ala (catalytic base - abolishes activity)
- `MA`, `MA + PROSS`, etc.: Component ablation variants with known mutation counts

**Limitations:**
- Most FuncLib variants (Des27.X, Des61.X, R2.Des39.X) don't have explicit mutations in the main text
- For complete mutation lists, refer to Supplementary Table 1 in the paper

**Input:** CSV from Step 2
**Output:**
- `*_with_mutations.csv` - CSV with detailed mutation information
- Added columns: `specific_mutations`, `mutation_list`, `total_mutation_count`, `PROSS_mutations`, `active_site_mutations`, `mutation_description`, `key_mutations`

**Usage:**
```bash
python pipelines/add_mutation_details.py
python pipelines/add_mutation_details.py -i data/extraction/listov2025_extraction_with_variants.csv
```

### Step 4: Add EC Numbers from PDB IDs (`add_ec_numbers.py`)

Retrieves Enzyme Commission (EC) numbers from RCSB PDB database for enzymes with PDB IDs.

**Features:**
- Queries RCSB PDB Data API to retrieve EC numbers
- Handles multiple PDB IDs per enzyme
- Supports multiple EC numbers per PDB ID
- Deduplicates EC numbers across multiple PDB IDs
- Graceful error handling for missing/invalid PDB IDs
- Real-time progress reporting during lookups

**API Details:**
- Uses RCSB PDB Data API (core and legacy endpoints)
- Retrieves EC numbers from polymer entity annotations
- Falls back to customReport API if needed
- Rate-limited to 4 concurrent requests
- 10-second timeout per request with 3 retries

**Input:** CSV from Step 3
**Output:**
- `*_with_ec.csv` - CSV with EC number information
- Added columns: `ec_numbers` (pipe-delimited), `ec_count`

**Usage:**
```bash
python pipelines/add_ec_numbers.py
python pipelines/add_ec_numbers.py -i data/extraction/listov2025_extraction_with_mutations.csv
```

**Example Output:**
```
🔍 Looking up EC numbers for 5 unique PDB IDs...
   [1/5] 4FB7 → 4.1.1.48
   [2/5] 1ABC → No EC numbers found
   [3/5] 2DEF → 1.1.1.1, 1.1.1.2
   ...
📈 Summary: 3/5 PDB IDs had EC numbers
✅ Added EC numbers to CSV: output_with_ec.csv
```

## Running the Complete Pipeline

Use the main pipeline runner to execute multiple steps:

```bash
# Run complete pipeline (all 4 steps)
python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json

# Run with data validation (recommended)
python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json --validate

# Run with statistics and validation
python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json --stats --validate

# Run specific steps
python pipelines/run_analysis.py --steps 1 --input data/extraction/listov2025_extraction.json
python pipelines/run_analysis.py --steps 2 --input data/extraction/listov2025_extraction.csv
python pipelines/run_analysis.py --steps 1,2 --input data/extraction/listov2025_extraction.json
python pipelines/run_analysis.py --steps 4 --input data/extraction/listov2025_extraction_with_mutations.csv

# Run Step 1 with validation only
python pipelines/run_analysis.py --steps 1 --input data/extraction/listov2025_extraction.json --validate
```

# Run specific steps
python pipelines/run_analysis.py --steps 1 --input data/extraction/listov2025_extraction.json
python pipelines/run_analysis.py --steps 2 --input data/extraction/listov2025_extraction.csv
python pipelines/run_analysis.py --steps 1,2 --input data/extraction/listov2025_extraction.json

# Run Step 1 with validation only
python pipelines/run_analysis.py --steps 1 --input data/extraction/listov2025_extraction.json --validate
```

## Output Structure

The final CSV contains the following columns:

**Core Data:**
- `enzyme_name` - Original enzyme name
- `substrates`, `products` - Reaction components
- `Km`, `kcat`, `kcat_over_KM`, `Tm` - Kinetic parameters
- `temperature`, `pH`, `buffer` - Experimental conditions

**Variant Metadata (added in Step 2):**
- `variant_type` - Category (base_design, FuncLib_variant, point_mutant, etc.)
- `design_method` - modular_assembly, RoseTTAFold
- `optimization` - FuncLib, PROSS, site-directed_mutagenesis
- `mutations` - Specific mutations (e.g., F113L)
- `mutation_count` - Number of mutations
- `base_design` - Parent enzyme design

**Mutation Details (added in Step 3):**
- `specific_mutations` - Known mutations from paper text
- `mutation_list` - List of all mutations
- `total_mutation_count` - Total number of mutations
- `PROSS_mutations` - Number of PROSS stabilization mutations
- `active_site_mutations` - Number of active site mutations
- `mutation_description` - Human-readable description
- `key_mutations` - Important mutations to note

**EC Numbers (added in Step 4):**
- `ec_numbers` - Pipe-delimited list of EC numbers from PDB IDs
- `ec_count` - Number of unique EC numbers found

## Extending the Pipeline

To add a new pipeline step:

1. Create a new Python script in `pipelines/`
2. Implement a `main()` function that can be called from command line
3. Import it in `run_analysis.py`
4. Add step configuration to `get_step_name()`

Example template:
```python
#!/usr/bin/env python3
"""Pipeline Step X: Description."""

def main():
    # Your implementation here
    pass

if __name__ == '__main__':
    main()
```

## Future Steps

Potential pipeline enhancements:
- **Step 5**: Statistical analysis and visualization
  - Distribution of kinetic parameters
  - Correlation analysis (mutations vs. activity)
  - EC number classification and clustering
- **Step 6**: Comparison across datasets
  - Cross-paper enzyme comparisons
  - Performance benchmarking
  - Evolutionary analysis
- **Step 7**: Machine learning feature extraction
  - Predict kinetic parameters from mutations
  - Optimize enzyme designs
  - Generate novel enzyme variants

## Data Sources

The mutation information in Step 3 is extracted from:
1. **Main paper text** (listov2025.md):
   - Des27.7 mutations (page 70, Fig. 3 discussion)
   - Point mutant details (F113L, F113M, D162A)
   - Component ablation variants (Fig. 4)
   - Mutation counts for MA variants

2. **Supplementary Table 1** (referenced but not included):
   - Complete mutation lists for all FuncLib variants
   - Full sequence alignments
   - Detailed kinetic parameters

To get complete mutation data for all variants, you would need to:
- Access Supplementary Table 1 from the paper
- Parse the supplementary Excel/CSV files
- Add those mutations to the `KNOWN_MUTATIONS` dictionary in `add_mutation_details.py`

## Data Validation

The pipeline includes comprehensive data validation (enabled with `--validate` flag):

**Implemented in `validate_and_clean()` function:**

1. **Numeric Field Validation**:
   - Validates all kinetic parameters (Km, Vmax, kcat, kcat/KM, Tm, yield_percent)
   - Handles special values: "n.c." (not calculable), "n.d." (not detected), "n.m." (not measured)
   - Converts special values to empty strings for cleaner CSV output

2. **Outlier Detection**:
   - **Melting Temperature (Tm)**: Flags values < 0°C or > 150°C as unrealistic
   - **Kinetic Parameters**: Flags negative values for kcat, kcat/KM, Km, Vmax
   - **Yield Percent**: Flags values outside 0-100% range

3. **Units Consistency**:
   - Checks that kcat has kcat_unit
   - Checks that Km has Km_unit
   - Warns about missing units for kinetic parameters

4. **Mutation Field Cleaning**:
   - Removes extra whitespace from mutation names
   - Validates pipe delimiter formatting
   - Preserves original mutation notation (e.g., "F113L" vs "Ile54Val")

**Validation Output:**

When validation is enabled, warnings are displayed:
```
⚠️  Validation warnings: 3
   - EnzymeX: Tm=-10°C (unrealistic)
   - EnzymeY: kcat=-5 (negative value)
   - EnzymeZ: kcat has value but no unit
```

**Recommendation**: Always run with `--validate` flag for production data analysis to catch data quality issues early.

## Dependencies

- Python 3.8+
- Standard library only (csv, json, argparse, re, pathlib)

No external packages required for basic pipeline operation.
