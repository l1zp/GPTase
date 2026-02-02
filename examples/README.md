# GPTase Examples

This directory contains example scripts demonstrating various features of the GPTase framework.

## 📁 Directory Structure

```
examples/
├── chat_demo.py              # Chat interface with thinking mode
├── reaction_extractor.py     # Enzyme reaction extraction from literature
├── vision_image_analyzer.py  # Scientific figure analysis
│
├── database_tools/           # External database lookup examples
│   ├── base_class_demo.py        # Reusable base classes demo
│   ├── ec_number_lookup_demo.py  # ExPASy enzyme database lookup
│   ├── pubchem_lookup_demo.py    # PubChem compound lookup
│   ├── rhea_lookup_demo.py       # Rhea reaction database lookup
│   ├── rhea_mechanism_demo.py    # Rhea mechanism information extraction
│   └── test_mineru_tool.py       # MinerU PDF parsing test
│
└── summaries/                 # Summary generation examples
    ├── enzyme_summary_demo.py    # Enzyme extraction summary
    └── generate_summary.py       # Generic summary generation
```

## 🚀 Quick Start

### Core Features

#### 1. Chat Interface (`chat_demo.py`)
```bash
python examples/chat_demo.py
```
Demonstrates the chat interface with streaming responses and thinking mode.

#### 2. Reaction Extraction (`reaction_extractor.py`)
```bash
python examples/reaction_extractor.py -i data/paper.md
```
Extracts enzyme kinetics data from scientific literature using a two-phase pipeline.

#### 3. Vision Analysis (`vision_image_analyzer.py`)
```bash
python examples/vision_image_analyzer.py --image-number 7
```
Analyzes scientific figures and extracts tabular data using vision models.

---

## 🗄️ Database Tools (`database_tools/`)

### ExPASy Enzyme Database
```bash
python examples/database_tools/ec_number_lookup_demo.py
```
Lookup enzyme reaction information by EC number from ExPASy database.

**Output:**
- Enzyme name and classification
- Catalyzed reactions
- Substrates, products, cofactors
- Functional comments

### PubChem Compound Database
```bash
python examples/database_tools/pubchem_lookup_demo.py
```
Search chemical compounds and retrieve SMILES strings from PubChem.

**Output:**
- Compound names and identifiers
- SMILES strings
- Molecular formulas and weights
- CAS numbers

### Rhea Reaction Database
```bash
# Basic lookup
python examples/database_tools/rhea_lookup_demo.py

# Mechanism information
python examples/database_tools/rhea_mechanism_demo.py
```

Query biochemical reactions from Rhea database:

**Basic Lookup:**
- Reactions by Rhea ID, EC number, or compound
- Reaction equations (substrates ↔ products)
- ChEBI compound identifiers
- Cross-references (KEGG, MetaCyc, etc.)

**Mechanism Information:**
- PubMed article links for mechanistic studies
- M-CSA catalytic mechanism entries
- ChEBI stereochemistry data
- Literature references

### Base Classes Demo
```bash
python examples/database_tools/base_class_demo.py
```
Demonstrates the reusable base classes for creating new database tools.

**Features:**
- HTTP session management
- Automatic retry logic
- Rate limiting
- Context manager support

### MinerU PDF Parsing
```bash
python examples/database_tools/test_mineru_tool.py
```
Test the MinerU PDF parsing tool.

---

## 📊 Summary Generation (`summaries/`)

### Enzyme Extraction Summary
```bash
python examples/summaries/enzyme_summary_demo.py
```
Generate comprehensive summaries of enzyme extraction results.

### Generic Summary Generation
```bash
python examples/summaries/generate_summary.py
```
Generate summaries from various data sources.

---

## 📖 Usage Tips

### Running Examples

Most examples require the environment to be properly set up:

```bash
# Install dependencies
pip install -e .

# Set API key if needed
export API_KEY="your-api-key"

# Run example
python examples/chat_demo.py
```

### Customizing Examples

Examples are designed to be easily modified:

1. **Change input data**: Modify input file paths or query parameters
2. **Adjust output format**: Change how results are displayed
3. **Combine features**: Mix and match different tools and features

### Common Options

Many examples support command-line arguments:

```bash
# Get help
python examples/reaction_extractor.py --help

# Specify input file
python examples/reaction_extractor.py -i data/paper.md

# Limit output
python examples/vision_image_analyzer.py --max-images 5
```

---

## 🎯 Learning Path

Recommended order for exploring examples:

1. **Start simple**: `chat_demo.py` - Basic chat interface
2. **Database queries**: `database_tools/pubchem_lookup_demo.py` - Simple API lookup
3. **Advanced queries**: `database_tools/rhea_lookup_demo.py` - Complex database
4. **Vision**: `vision_image_analyzer.py` - Image analysis
5. **Extraction**: `reaction_extractor.py` - Full pipeline
6. **Code reuse**: `database_tools/base_class_demo.py` - Create your own tools

---

## 🔧 Troubleshooting

### Import Errors

```
ImportError: No module named 'src'
```
**Solution**: Set `PYTHONPATH`:
```bash
export PYTHONPATH=/path/to/GPTase
python examples/chat_demo.py
```

### API Key Issues

```
Error: API key not found
```
**Solution**: Set the `API_KEY` environment variable or configure in `config/llm_config.template.json`.

### Missing Dependencies

```
ModuleNotFoundError: No module named 'bs4'
```
**Solution**: Install missing dependencies:
```bash
pip install beautifulsoup4
```

---

## 📚 Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project overview and development guidelines
- [src/tools/external_databases/README.md](../src/tools/external_databases/README.md) - Database tools documentation
- [src/tools/external_databases/QUICKSTART.md](../src/tools/external_databases/QUICKSTART.md) - Database tools quick start

---

## 🤝 Contributing

When adding new examples:

1. **Choose appropriate directory**: Core features, database_tools, or summaries
2. **Follow naming convention**: Use descriptive names with `_demo.py` suffix
3. **Add docstrings**: Explain what the example does
4. **Include usage comments**: Show how to run and customize
5. **Update this README**: Add description of the new example
