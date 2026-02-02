# Database Tools Examples

This directory contains examples of external database lookup tools.

## Available Examples

### 1. Base Class Demo (`base_class_demo.py`)
**Purpose**: Demonstrate reusable base classes for creating new database tools

**Features**:
- HTTP session management
- Automatic retry logic
- Rate limiting
- Context manager support

**Run**:
```bash
python examples/database_tools/base_class_demo.py
```

**Learn**: How to create your own database tool in 30 seconds using base classes

---

### 2. ExPASy EC Number Lookup (`ec_number_lookup_demo.py`)
**Purpose**: Query enzyme reaction information from ExPASy database

**Features**:
- Look up enzymes by EC number
- Get catalyzed reactions
- Extract substrates, products, cofactors
- Retrieve functional comments

**Run**:
```bash
python examples/database_tools/ec_number_lookup_demo.py
```

**Database**: [ExPASy Enzyme Database](https://enzyme.expasy.org/)

---

### 3. PubChem Compound Lookup (`pubchem_lookup_demo.py`)
**Purpose**: Search chemical compounds and retrieve SMILES strings

**Features**:
- Search by compound name, CID, or SMILES
- Get SMILES strings and molecular properties
- Extract CAS numbers

**Run**:
```bash
python examples/database_tools/pubchem_lookup_demo.py
```

**Database**: [PubChem](https://pubchem.ncbi.nlm.nih.gov/)

---

### 4. Rhea Reaction Database (`rhea_demo.py`)
**Purpose**: Comprehensive demo of Rhea biochemical reaction database

**Features**:
- Part 1: Basic queries (Rhea ID, EC number, compound, ChEBI ID)
- Part 2: Mechanism information extraction
- Part 3: Advanced features (cross-references, batch queries)
- Part 4: Save results to file

**Run**:
```bash
# Run all demos
python examples/database_tools/rhea_demo.py

# Run specific sections
python examples/database_tools/rhea_demo.py --section basic
python examples/database_tools/rhea_demo.py --section mechanism
python examples/database_tools/rhea_demo.py --section advanced
python examples/database_tools/rhea_demo.py --section save
python examples/database_tools/rhea_demo.py --section summary
```

**Database**: [Rhea](https://www.rhea-db.org/)

**Example Output**:
```
Part 1: Basic Rhea Queries
================================================================================

1.1 Query by Rhea ID
--------------------------------------------------------------------------------
Rhea ID: RHEA:15109
Equation: 2-dehydro-3-deoxy-D-gluconate + NADP(+) = (4S,5S)-4,5-dihydroxy-2,6-dioxohexanoate + NADPH + H(+)
Substrates: 2-dehydro-3-deoxy-D-gluconate, NADP(+)
Products: (4S,5S)-4,5-dihydroxy-2,6-dioxohexanoate, NADPH, H(+)

Part 2: Mechanism Information
================================================================================

Mechanism Information Sources:
1. Rhea Web Page: https://www.rhea-db.org/21020
2. PubMed Articles: Links to mechanistic studies
3. ChEBI Stereochemistry: SMILES and InChIKey data
```

---

### 5. KEGG Pathway Database (`kegg_demo.py`)
**Purpose**: Comprehensive demo of KEGG pathway database lookup

**Features**:
- Part 1: Pathway search (by ID and keyword)
- Part 2: Organism-specific pathways (human, E. coli, etc.)
- Part 3: Gene search within organisms
- Part 4: Compound search (by name and ID)
- Part 5: Detailed pathway information (genes, reactions, compounds)

**Run**:
```bash
python examples/database_tools/kegg_demo.py
```

**Database**: [KEGG - Kyoto Encyclopedia of Genes and Genomes](https://www.genome.jp/kegg/)

**Example Output**:
```
Part 1: Pathway Search
--------------------------------------------------------------------------------
1.1 Search by Pathway ID (Glycolysis)
Pathway ID: map00010
Name: Glycolysis / Gluconeogenesis
Genes: 25 genes
Compounds: 31 compounds

1.2 Search by Keyword (glycolysis)
Found 1 pathways:
  hsa00010: Glycolysis / Gluconeogenesis - Homo sapiens (human)

Part 2: Organism-Specific Pathways
Found 369 human pathways
First 5 pathways:
  hsa01100: Metabolic pathways
  hsa01200: Carbon metabolism
  hsa01210: 2-Oxocarboxylic acid metabolism
  ...
```

---

### 6. MinerU Tool Test (`test_mineru_tool.py`)
**Purpose**: Test the MinerU PDF parsing tool

**Run**:
```bash
python examples/database_tools/test_mineru_tool.py
```

---

## 🎯 When to Use Each Tool

| Task | Use This Tool | Example |
|------|--------------|---------|
| Find enzyme reaction info | ExPASy | Get EC 1.1.1.1 reaction details |
| Get compound structure | PubChem | Find glucose SMILES string |
| Find biochemical reactions | Rhea | Look up ATP hydrolysis reaction |
| Get reaction mechanisms | Rhea | Find chorismate synthase mechanism |
| Search metabolic pathways | KEGG | Get glycolysis pathway genes and compounds |
| Find organism-specific pathways | KEGG | List all human metabolic pathways |
| Search genes in pathways | KEGG | Find hexokinase genes in human |
| Create new database tool | Base Classes | Implement UniProt lookup |

---

## 📚 Related Documentation

- [Base Classes Guide](../../src/tools/external_databases/QUICKSTART.md)
- [Database Tools README](../../src/tools/external_databases/README.md)
- [Rhea Examples](../../src/tools/external_databases/EXAMPLES.md)
