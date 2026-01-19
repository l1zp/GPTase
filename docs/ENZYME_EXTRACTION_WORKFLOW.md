# Enzyme Reaction Extraction Workflow

This document provides a comprehensive reference for the enzyme reaction extraction pipeline, as implemented in `examples/reaction_extractor_demo.py`. Use this as a guide for understanding, extending, and improving the extraction system.

## Overview

GPTase provides two complementary enzyme analysis pipelines for extracting structured biochemical data from scientific literature:

**Pipeline 1: Enzyme Reaction Extraction** (Two-Phase Approach)
1. **Phase 1: Document Structure Analysis** - Identify and locate tables, key sections, and relevant content
2. **Phase 2: Targeted LLM Extraction** - Extract structured data only from identified relevant sections

**Pipeline 2: Enzyme Design Step Extraction** (Keyword-Based Approach)
- Uses predefined keyword categories to identify design steps
- Confidence-based scoring with Chinese language support
- Alternative to LLM-based extraction for design-focused documents

This approach significantly improves accuracy by focusing the LLM on relevant content and maintaining traceability of data sources. Additional tools include PDB/EC number lookup for enrichment and optional LLM enhancement for table analysis.

### High-Level Architecture (Updated)

```
┌──────────────┐
│   Config     │  config/llm_config.template.json + API_KEY env var
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Model Manager│  default_manager() - Initialize LLM connection
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Components │  ToolRegistry + MemoryManager + Agent
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│     Phase 1: Structure Analysis          │
│  • Identify document sections             │
│  • Extract tables (Markdown + HTML)      │
│  • Locate key paragraphs with keywords   │
│  • Save analysis to data/analysis/        │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Phase 2: Targeted Extraction         │
│  • Combine relevant tables + paragraphs  │
│  • Send to LLM for extraction            │
│  • Validate and structure results         │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────┐
│    Output    │  Save JSON + analysis to data/extraction/
└──────────────┘
```

### Key Benefits of Two-Phase Approach

1. **Improved Accuracy**: LLM focuses only on relevant content, reducing noise
2. **Traceability**: Every extracted data point can be traced to its source (table/paragraph)
3. **Efficiency**: Reduced token usage by filtering irrelevant content
4. **Debuggability**: Structure analysis saved for inspection
5. **Extensibility**: Easy to add new recognition rules

### Dual Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      GPTase Enzyme Analysis                         │
│                                                                      │
│  ┌──────────────────────────┐      ┌──────────────────────────┐    │
│  │ Pipeline 1: Reaction     │      │ Pipeline 2: Design        │    │
│  │ Extraction (LLM-based)   │      │ Extraction (Keyword)      │    │
│  │                          │      │                          │    │
│  │  • DocumentStructureAnalyzer    │  • EnzymeDesignAgent      │    │
│  │  • LLMEnzymeExtractorAgent      │  • Keyword scoring        │    │
│  │  • PDB/EC lookup (optional)     │  • 6 categories           │    │
│  │  • Kinetic parameters           │  • Chinese labels         │    │
│  └──────────────────────────┘      └──────────────────────────┘    │
│              │                                 │                     │
│              └──────────────┬──────────────────┘                     │
│                             ▼                                        │
│              ┌──────────────────────────┐                           │
│              │   Orchestrator Access    │                           │
│              │   agents["enzyme_kinetics_extractor"] │              │
│              │   agents["enzyme_design_parser"]     │              │
│              └──────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

**Pipeline Comparison**:

| Feature | Reaction Extraction | Design Extraction |
|---------|-------------------|-------------------|
| Method | LLM-based | Keyword-based |
| Input | Tables + paragraphs | Text/HTML paragraphs |
| Output | Structured reaction data | Design steps with categories |
| Language | English | English + Chinese labels |
| Confidence | LLM-based | Score-based (0.3 threshold) |
| Use case | Kinetic parameters | Design workflows |

## Detailed Workflow Steps

### Phase 1: Initialization

**Location**: `examples/reaction_extractor_demo.py:21-23`

```python
manager = default_manager()
```

**What Happens**:

1. Read configuration from `config/llm_config.template.json`
2. Resolve API key in this order:
   - Value from config file (if not a placeholder like `${API_KEY}`)
   - Environment variable: `API_KEY`
   - Environment variable: `OPENAI_API_KEY`
   - Environment variable: `GPTASE_OPENAI_API_KEY`

3. Initialize Model instance with:
   - Model name (e.g., "Kimi-K2", "gpt-4")
   - API key
   - Base URL (for custom endpoints)
   - Temperature, max_tokens, timeout

**Output**: Configured `Model` manager ready for LLM calls

**Dependencies**:
- `src/utils.py:default_manager()`
- `config/llm_config.template.json`

---

### Phase 2: File Discovery

**Location**: `examples/reaction_extractor_demo.py:25-31`

```python
data_dir = Path(__file__).resolve().parent.parent / "data"
md_files = sorted(data_dir.glob("*.md"))

if not md_files:
    print("No Markdown files found in ./data.")
    return
```

**What Happens**:

1. Locate project `data/` directory
2. Scan for all `.md` files
3. Sort alphabetically for consistent ordering
4. Validate at least one file exists

**Output**: List of markdown file paths to process

**Default File**: `data/listov2025.md`

---

### Phase 3: Component Setup

**Location**: `examples/reaction_extractor_demo.py:34-41`

```python
tool_registry = ToolRegistry()
tool_registry.register_tools([DocumentLoaderTool()])
memory_manager = MemoryManager()
agent = LLMEnzymeExtractorAgent("enzyme",
                                memory_manager,
                                tool_registry,
                                model_manager=manager)
```

**What Happens**:

1. **ToolRegistry Creation** (`src/tools/registry.py`)
   - Manages available tools for agent use
   - Registers tools by category

2. **DocumentLoaderTool Registration** (`src/tools/implementations.py`)
   - Loads markdown/text files
   - Calculates word count and token estimates
   - Returns document content as string

3. **MemoryManager Initialization** (`src/memory/manager.py`)
   - Manages agent state and context
   - Provides persistent storage for agent operations

4. **Agent Creation** (`src/agents/specialized/llm_enzyme_extractor.py`)
   - Named "enzyme"
   - Receives memory_manager, tool_registry, and model_manager
   - Ready to process extraction tasks

**Output**: Fully configured agent with all dependencies

**Component Diagram**:

```
┌─────────────────────────────────────────────┐
│         LLMEnzymeExtractorAgent             │
│  ┌─────────────────────────────────────┐   │
│  │         MemoryManager                │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │         ToolRegistry                 │   │
│  │  ┌──────────────────────────────┐   │   │
│  │  │    DocumentLoaderTool        │   │   │
│  │  └──────────────────────────────┘   │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │         Model Manager                │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

### Phase 4: Document Processing (Two-Phase Approach)

**Location**: `examples/reaction_extractor_demo.py:42-46` and `src/agents/specialized/llm_enzyme_extractor.py:147-242`

```python
result = await agent.process_task({
    "document": {
        "source_type": "file",
        "path": str(target_file)
    }
})
```

**What Happens Inside the Agent**:

#### Step 4.1: Document Loading

```
agent.process_task() → tool_registry.execute("document_loader")
```

**DocumentLoaderTool** (`src/tools/implementations.py`):
- Opens file at specified path
- Reads content as text
- Calculates statistics:
  - `char_length`: Total characters
  - `word_count`: Estimated words
  - `line_count`: Total lines
  - `approx_tokens`: Rough token estimate (words × 1.3)
  - `tokens_precise`: More accurate count

**Output**: Document metadata + content string

---

#### Step 4.2: Structure Analysis (PHASE 1 - NEW!)

```
agent.process_task() → DocumentStructureAnalyzer.execute()
```

**DocumentStructureAnalyzer** (`src/tools/document_structure_analyzer.py`):

**Location**: `src/tools/document_structure_analyzer.py:30-199`

**What It Does**:

1. **Identify Document Sections**
   ```python
   sections = analyzer._identify_sections(text)
   ```
   - Finds all markdown headers (# ## ###)
   - Organizes document hierarchy
   - Extracts section content
   - Returns: List of sections with line numbers and content

2. **Extract Tables**
   ```python
   tables = analyzer._extract_tables(text)
   ```
   - **Markdown tables**: Standard pipe-separated tables
   - **HTML tables**: `<table><tr><td>` format (NEW!)
   - Detects table headers and rows
   - Classifies as reaction-related if contains keywords (kcat, KM, substrate, etc.)
   - Returns: List of tables with metadata

   **Example Table Found**:
   ```
   Table 2 (HTML):
   Headers: ['', 'kcat(s-1)', 'KM(mM)', 'kcat/KM(M-1s-1)', 'Tm(°C)']
   Rows: 32
   Reaction related: True

   Sample data:
   - Des27: kcat=0.07, KM=0.5, kcat/KM=131
   - Des27.7: kcat=2.85, KM=0.22, kcat/KM=12,696
   - Des27.7 F113L: kcat=30.0, KM=0.25, kcat/KM=123,274
   ```

3. **Identify Key Paragraphs**
   ```python
   key_paragraphs = analyzer._identify_key_paragraphs(text, sections)
   ```
   - Searches for keywords: kcat, km, substrate, efficiency, kinetics, pH, temperature
   - Locates paragraphs containing kinetic parameters
   - Tracks which keywords were found
   - Returns: List of key paragraphs with location and content

4. **Save Analysis Results**
   ```python
   save_document_analysis(analysis, Path('data/analysis'))
   ```
   - Saves to: `data/analysis/{filename}_structure_analysis.json`
   - Contains:
     - All sections with line numbers
     - All tables (headers + rows + content)
     - All key paragraphs (content + keywords + location)
     - Metadata (counts, classifications)

**Output**: Structured analysis object containing:
```json
{
  "source_file": "data/listov2025.md",
  "total_tables": 6,
  "total_key_paragraphs": 83,
  "sections": [...],
  "tables": [
    {
      "table_number": 2,
      "type": "html",
      "headers": ["", "kcat(s-1)", "KM(mM)", "kcat/KM(M-1s-1)", "Tm(°C)"],
      "is_reaction_related": true,
      "row_count": 32,
      ...
    }
  ],
  "key_paragraphs": [...]
}
```

---

#### Step 4.3: Content Preparation for Extraction

```python
relevant_content = get_relevant_content_for_extraction(analysis)
```

**What It Does**:

1. **Combine Reaction-Related Tables**
   - Extracts tables where `is_reaction_related == true`
   - Formats as plain text for LLM
   - Includes table headers and data

2. **Add Key Paragraphs**
   - Includes all identified key paragraphs
   - Preserves section context
   - Maintains paragraph structure

3. **Fallback Handling**
   - If no relevant content found, uses full document
   - Sets `fallback_to_full_text = true` flag

**Output**: Focused content string (typically 60-80% of original document)

**Example**:
```python
# Before: Full document (98,811 characters)
# After: Relevant content only (82,441 characters - 83% of original)
```

---

#### Step 4.4: LLM Extraction (PHASE 2)

Now using only the relevant content identified in Phase 1.

**System Prompt** (`src/agents/specialized/llm_enzyme_extractor.py:18-30`):

```
You are an expert biochemical text parser. Extract enzyme reaction data
from academic-style text and return STRICT JSON that conforms to the
following structure. No markdown, no commentary, no trailing commas.

Schema: {
  "reactions": [{
    "source_file": string|null,
    "enzyme_name": string|null,
    "substrates": [string],
    "products": [string],
    "conditions": {
      "temperature": string|null,
      "pH": string|null,
      "buffer": string|null,
      "time": string|null,
      "notes": string|null
    },
    "kinetics": {
      "Km": number|null,
      "Km_unit": string|null,
      "Vmax": number|null,
      "Vmax_unit": string|null
    },
    "yield_percent": number|null,
    "citations": [string],
    "pdb_ids": [string]
  }],
  "pipeline": {
    "steps": [{"name": string, "description": string, "status": string}],
    "validations": [string],
    "errors": [string]
  }
}

Rules:
1. Never hallucinate numbers; only extract if explicitly present
2. Keep units alongside numeric values in the *_unit fields
3. Prefer precise biochemical names (IUPAC/common)
4. When multiple reactions are present, split them
5. PDB IDs are four-character codes (first is a digit) like 1ABC
```

**User Prompt** (`src/agents/specialized/llm_enzyme_extractor.py:33-47`):

```
Task: Extract enzyme reaction information from the following content.

Required:
- Enzyme name (prefer exact names, include isoforms if stated)
- Substrates and products (lists)
- Conditions: temperature, pH, buffer, time, notes (strings)
- Kinetics: Km and Vmax (numbers) with *_unit strings if present
- Yield percent if explicitly stated
- Citations (DOI, PubMed, journal references as strings)
- PDB IDs found in the text (four-character alphanumeric codes)

Context: source file = listov2025.md
Output: STRICT JSON only, conforming to the described schema.

Content: [DOCUMENT CONTENT HERE]
```

#### Step 4.3: LLM Extraction

```
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_prompt_with_content}
]

response = await model_manager.generate(messages, role=ModelRole.GENERAL)
```

**Flow**:
1. Send messages to LLM API
2. Wait for response (with timeout)
3. Parse response content as JSON
4. Validate against schema

#### Step 4.4: PDB ID Extraction

**Location**: `src/agents/specialized/llm_enzyme_extractor.py:50-58`

```python
def extract_pdb_ids_from_text(text: str) -> List[str]:
    candidates = re.findall(r"\b[1-9][A-Za-z0-9]{3}\b", text)
    filtered = []
    for c in candidates:
        if any(ch.isalpha() for ch in c[1:]):
            filtered.append(c.upper())
    return sorted(set(filtered))
```

**What It Does**:
- Searches for 4-character codes starting with digit
- Filters out purely numeric matches
- Converts to uppercase
- Removes duplicates
- Sorts alphabetically

**Output**: List of PDB IDs found in document

#### Step 4.5: Result Assembly

```python
# Merge LLM-extracted PDB IDs with regex-extracted ones
for reaction in data.get("reactions", []):
    llm_pdbs = reaction.get("pdb_ids", [])
    all_pdbs = sorted(set(llm_pdbs + regex_pdbs))
    reaction["pdb_ids"] = all_pdbs

# Add validation step
pipeline["steps"].append({
    "name": "llm_extract",
    "description": "LLM extraction completed",
    "status": "success"
})
pipeline["validations"].append(f"pdb_ids_extracted:{len(regex_pdbs)}")
```

**Output**: Complete extraction result with reactions and metadata

---

### Phase 5: Output Generation

**Location**: `examples/reaction_extractor_demo.py:48-63`

```python
if result["status"] == "success":
    extraction = result["data"].get("extraction", {})
    reactions = extraction.get("reactions", [])
    print(f"Reactions parsed: {len(reactions)}")

    # Save results
    output_file = data_dir / "extraction" / "listov2025_extraction.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(result["data"], f, indent=2, default=str)
    print(f"Extraction results saved to: {output_file}")
else:
    print(f"Extraction failed: {result.get('error')}")
```

**What Happens**:

1. Check extraction status
2. Extract reactions array from result
3. Print summary (count of reactions)
4. Create `data/extraction/` directory if needed
5. Save complete result as JSON
6. Print output location

**Output**: JSON file saved to `data/extraction/{filename}_extraction.json`

---

### Alternative Workflow: Enzyme Design Step Extraction

**Location**: `src/agents/specialized/enzyme_design.py:62-131`

**What It Does**:
Extracts enzyme design steps from documents using keyword-based scoring. This is an alternative to LLM-based reaction extraction, specifically designed for enzyme engineering workflows.

**Key Features**:
- **Keyword-based scoring**: Uses predefined term categories for matching
- **Confidence threshold**: 0.3 minimum score for step inclusion
- **Chinese language support**: Provides Chinese labels via CATEGORY_ZH
- **HTML support**: Processes both text and HTML content
- **Six categories**: Planning, Design, Construction, Expression, Assay, Optimization

**Categories and Keywords**:

```python
# From src/tools/enzyme_terms.py

Planning: literature review, background, prior work, objective
Design: active site, sequence design, computational design, docking,
        scoring function, molecular dynamics, MD simulation, structural modeling
Construction: mutagenesis, site-directed, library construction, cloning, vector, transformation
Expression: expression, culture, fermentation, induction, purification, SDS-PAGE
Assay: kinetic assay, Km, kcat, activity, substrate, buffer, temperature
Optimization: directed evolution, rounds, screening, selection, fitness, improvement

Chinese Labels (CATEGORY_ZH):
Planning → "规划与调研"
Design → "设计（保留术语）"
Construction → "构建与突变"
Expression → "表达与纯化"
Assay → "测定与表征"
Optimization → "优化与进化"
```

**Usage Example**:

```python
from src.agents.specialized.enzyme_design import EnzymeDesignAgent
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry
from src.tools.implementations import DocumentLoaderTool

# Setup agent
tool_registry = ToolRegistry()
tool_registry.register_tools([DocumentLoaderTool()])
memory_manager = MemoryManager()

agent = EnzymeDesignAgent("enzyme_design_parser", memory_manager, tool_registry)

# Extract design steps
result = await agent.process_task({
    "document": {
        "source_type": "file",  # or "text", "html"
        "path": "data/enzyme_design_paper.md"
    }
})
```

**Result Structure**:

```python
{
    "status": "success",
    "data": {
        "steps": [
            {
                "step_id": "1",
                "category": "Design",
                "label_zh": "设计（保留术语）",
                "description": "Full paragraph text describing the design step...",
                "evidence": "First 200 characters of the paragraph...",
                "confidence": 0.85
            },
            {
                "step_id": "2",
                "category": "Assay",
                "label_zh": "测定与表征",
                "description": "Kinetic assay was performed to measure...",
                "evidence": "Kinetic assay was performed...",
                "confidence": 0.72
            }
        ],
        "components": {
            "Design": [
                "Step 1: Full description...",
                "Step 3: Full description..."
            ],
            "Assay": [
                "Step 2: Full description..."
            ],
            "Optimization": [
                "Step 4: Full description..."
            ]
        },
        "confidence_overall": 0.75,
        "annotations_zh": "提取到的步骤含保留英文术语，并提供中文标签说明。"
    }
}
```

**Scoring Algorithm**:

Located in `src/tools/enzyme_extractor.py:48-66`

```python
def _score_snippet(snippet: str, keywords: List[str]) -> float:
    """Score based on keyword hits and length."""
    s = snippet.lower()
    hits = sum(1 for k in keywords if k.lower() in s)

    if hits == 0:
        return 0.0

    # Length penalty: prefer shorter, focused snippets
    length_penalty = min(1.0, 1000 / max(50, len(snippet)))

    # Base score: 0.6 per hit, capped at 1.0
    base = min(1.0, 0.6 * hits)

    return round(base * length_penalty, 3)
```

**Process Flow**:

1. **Text Normalization** (`normalize_text`)
   - Standardize line endings
   - Remove excessive whitespace

2. **Paragraph Splitting**
   - Split by newlines
   - Filter empty paragraphs

3. **Category Scoring** (`_score_categories`)
   - Score each paragraph against all 6 keyword categories
   - Return dictionary: `{category: score}`

4. **Filtering** (MIN_CONFIDENCE_THRESHOLD = 0.3)
   - Keep only steps with score ≥ 0.3
   - Create step records with metadata

5. **Grouping** (`_group_by_component`)
   - Group steps by Design, Assay, Optimization
   - Planning, Construction, Expression tracked but not grouped

6. **Overall Confidence**
   - Average of all step confidences

**Source Types**:

- `text`: Direct text content in `document.content`
- `file`: Load from file path via DocumentLoaderTool
- `html`: HTML content (tags stripped before processing)
- `url`: Load from URL (future feature)

**Component Reference**:

**1. EnzymeDesignAgent**
- **Location**: `src/agents/specialized/enzyme_design.py:33-131`
- **Purpose**: Extract enzyme design steps using keyword scoring
- **Capabilities**:
  - `enzyme_design_extraction`: Core extraction capability
  - `nlp_parsing`: Natural language processing
  - `pdf_html_text_support`: Multiple format support

**2. extract_steps()**
- **Location**: `src/tools/enzyme_extractor.py:81-115`
- **Purpose**: Core extraction logic for text content
- **Input**: Text string
- **Output**: Dictionary with steps, components, confidence_overall

**3. extract_from_html()**
- **Location**: `src/tools/enzyme_extractor.py:186-197`
- **Purpose**: Extract from HTML by stripping tags first
- **Input**: HTML string
- **Output**: Same as extract_steps()

**4. TERMS and CATEGORY_ZH**
- **Location**: `src/tools/enzyme_terms.py:1-56`
- **Purpose**: Keyword definitions and Chinese labels
- **Customization**: Add keywords to TERMS to extend extraction

---

## Component Reference

### 1. DocumentStructureAnalyzer (NEW!)

**Location**: `src/tools/document_structure_analyzer.py`

**Purpose**: Analyze document structure to identify tables and key sections before LLM extraction

**Class**: `DocumentStructureAnalyzer(BaseTool)`

**Key Methods**:
```python
async def execute(text: str, source_file: str = None,
                  use_llm_enhancement: bool = False) -> ToolResult
```

**Methods**:
```python
_identify_sections(text: str) -> List[Dict[str, Any]]
_extract_tables(text: str) -> List[Dict[str, Any]]
_identify_key_paragraphs(text: str, sections: List) -> List[Dict[str, Any]]
_is_reaction_related(text: str) -> bool
_enhance_tables_with_llm(tables: List, full_text: str, source_file: str) -> List
_create_table_summary(table: Dict) -> str
_build_table_analysis_prompt(table_summary: str, source_file: str) -> str
_parse_llm_table_analysis(llm_response: str) -> Dict
```

**Capabilities**:
- **Section Detection**: Finds all markdown headers (# ## ###) and organizes hierarchy
- **Table Extraction**:
  - Markdown tables (pipe-separated)
  - HTML tables (`<table><tr><td>`)
  - Detects table headers and rows
  - Classifies as reaction-related
- **Key Paragraph Identification**: Locates paragraphs containing kinetic keywords
- **Analysis Saving**: Stores structure analysis to JSON file

**LLM Enhancement Feature** (lines 424-578):
- **Optional feature**: Set `use_llm_enhancement=True` when calling `execute()`
- **Uses LLM to analyze tables** for relevance and extract metadata
- **Provides confidence scores** (0.0-1.0) for table relevance
- **Enhanced metadata**: descriptions, data types, enzyme counts
- **Overrides keyword detection** when LLM confidence > 0.7

**Enhanced Table Output** (with LLM enhancement):
```python
{
    "table_number": 2,
    "type": "html",
    "headers": ["", "kcat(s-1)", "KM(mM)", "kcat/KM(M-1s-1)", "Tm(°C)"],
    "row_count": 32,
    "is_reaction_related": true,
    "confidence": 0.85,  # NEW: LLM confidence score
    "description": "Kinetic parameters for 32 enzyme variants",  # NEW
    "llm_analysis": {  # NEW: Full LLM analysis
        "is_reaction_related": true,
        "description": "Kinetic parameters for enzyme variants...",
        "confidence": 0.85,
        "data_types": ["kcat", "KM", "kcat/KM", "Tm"],
        "enzyme_count": "32"
    },
    "rows": [...]
}
```

**Standard Table Output** (without LLM enhancement):
```python
{
    "table_number": 2,
    "type": "html",
    "headers": ["", "kcat(s-1)", "KM(mM)", ...],
    "row_count": 32,
    "is_reaction_related": true,
    "rows": [...]
}
```

**Output**:
```python
{
    "source_file": "data/listov2025.md",
    "total_tables": 6,
    "total_key_paragraphs": 83,
    "sections": [...],
    "tables": [...],  # Enhanced with LLM if use_llm_enhancement=True
    "key_paragraphs": [...]
}
```

**Keywords Detected**:
- Kinetic: kcat, km, vmax, catalytic efficiency, turnover, michaelis
- Conditions: temperature, ph, buffer, substrate, product
- Reaction: enzyme, catalyst, kinetics, mutant, variant

**Helper Functions**:
```python
save_document_analysis(analysis: Dict, output_dir: Path) -> Path
get_relevant_content_for_extraction(analysis: Dict) -> str
```

---

### 2. default_manager()

**Location**: `src/utils.py`

**Purpose**: Initialize Model manager with configuration from template file

**Signature**:
```python
def default_manager() -> Model
```

**Returns**: Configured Model instance

**Configuration**:
- Reads: `config/llm_config.template.json`
- Environment variables: `API_KEY`, `OPENAI_API_KEY`, `GPTASE_OPENAI_API_KEY`

---

### 2. ToolRegistry

**Location**: `src/tools/registry.py`

**Purpose**: Manages available tools for agent operations

**Methods**:
```python
register_tools(tools: List[BaseTool]) -> None
get_tool(tool_name: str) -> BaseTool
execute(tool_name: str, **kwargs) -> Any
```

**Categories**:
- `general`: General-purpose tools (document_loader)
- Custom categories can be defined

---

### 3. DocumentLoaderTool

**Location**: `src/tools/implementations.py`

**Purpose**: Load and analyze document files

**Input**:
```python
{
    "source_type": "file",
    "path": "/path/to/document.md"
}
```

**Output**:
```python
{
    "status": "success",
    "content": "# Document content here...",
    "metadata": {
        "char_length": 98811,
        "word_count": 15281,
        "line_count": 655,
        "approx_tokens": 24703,
        "tokens_precise": 27775
    }
}
```

**Supported Formats**: Markdown (.md), plain text (.txt)

---

### 4. MemoryManager

**Location**: `src/memory/manager.py`

**Purpose**: Manage agent state and persistent context

**Key Features**:
- Store and retrieve conversation history
- Maintain agent state across operations
- Provide context for multi-turn operations

---

### 5. LLMEnzymeExtractorAgent

**Location**: `src/agents/specialized/llm_enzyme_extractor.py`

**Purpose**: Coordinate enzyme extraction workflow

**Constructor**:
```python
def __init__(
    name: str,
    memory_manager: MemoryManager,
    tool_registry: ToolRegistry,
    model_manager: Model
)
```

**Key Method**:
```python
async def process_task(task: Dict) -> Dict
```

**Process**:
1. Use DocumentLoaderTool to load file
2. Construct system and user prompts
3. Call LLM for extraction
4. Extract PDB IDs via regex
5. Validate and assemble result
6. Return structured extraction

---

### 6. ExtractionResult Schema

**Location**: `src/tools/markdown_enzyme_parser.py`

**Purpose**: Define the structure of extraction results

**Schema**:
```python
class ExtractionResult(BaseModel):
    reactions: List[Reaction]
    pipeline: PipelineInfo

class Reaction(BaseModel):
    source_file: Optional[str]
    enzyme_name: Optional[str]
    substrates: List[str]
    products: List[str]
    conditions: ReactionConditions
    kinetics: KineticData
    yield_percent: Optional[float]
    citations: List[str]
    pdb_ids: List[str]

class ReactionConditions(BaseModel):
    temperature: Optional[str]
    pH: Optional[str]
    buffer: Optional[str]
    time: Optional[str]
    notes: Optional[str]

class KineticData(BaseModel):
    Km: Optional[float]
    Km_unit: Optional[str]
    Vmax: Optional[float]
    Vmax_unit: Optional[str]

class PipelineInfo(BaseModel):
    steps: List[PipelineStep]
    validations: List[str]
    errors: List[str]
```

---

### 7. PDB/EC Number Lookup Tool

**Location**: `src/tools/pdb_ec_lookup.py`

**Purpose**: Fetch Enzyme Commission (EC) numbers for PDB IDs from RCSB Protein Data Bank API. This tool enriches extracted enzyme data by adding standardized EC classifications.

**Key Features**:
- **Dual API support**: Primary RCSB Data API + legacy customReport API fallback
- **Entity-level mapping**: Returns EC numbers per polymer entity (e.g., "4FB7_1")
- **Input validation**: Strict PDB ID format checking (4 alphanumeric chars, must have letter in last 3)
- **Error handling**: Retries with exponential backoff, graceful degradation
- **Rate limiting**: Semaphore-based concurrency limit (4 concurrent requests)
- **Sync and async interfaces**: Both `get_ec_numbers_for_pdb()` and `get_ec_numbers_for_pdb_sync()`

**Usage Examples**:

```python
# Async usage (recommended for multiple lookups)
from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb

result = await get_ec_numbers_for_pdb("4FB7")

# Returns:
# {
#   "pdb_id": "4FB7",
#   "ec_numbers": ["1.1.1.1"],
#   "entities": {"4FB7_1": ["1.1.1.1"]},
#   "source": "rcsb",
#   "errors": []
# }

# Synchronous usage
from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb_sync

result = get_ec_numbers_for_pdb_sync("4FB7")

# Command line usage
python -m src.tools.pdb_ec_lookup 4FB7
```

**Key Functions**:

**1. validate_pdb_id()** (lines 52-69)
```python
def validate_pdb_id(pdb_id: str) -> str:
    """Validate PDB ID format.

    Rules:
    - Length 4, alphanumeric
    - At least one letter among last 3 characters
    - Normalize to uppercase

    Raises ValueError if invalid.
    """
```

**2. get_ec_numbers_for_pdb()** (lines 124-262)
```python
async def get_ec_numbers_for_pdb(
    pdb_id: str,
    *,
    timeout: float = 10.0,
    max_retries: int = 3,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Fetch EC numbers from RCSB.

    Process:
    1. Validate PDB ID
    2. Fetch entry metadata to get polymer entity IDs
    3. Query each entity for EC annotations
    4. Extract EC numbers from multiple fields
    5. Fallback to legacy API if needed
    6. Return structured results

    Returns: {"pdb_id", "ec_numbers", "entities", "source", "errors"}
    """
```

**3. get_ec_numbers_for_pdb_sync()** (lines 265-273)
```python
def get_ec_numbers_for_pdb_sync(
    pdb_id: str,
    *,
    timeout: float = 10.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Synchronous wrapper around async lookup."""
    return asyncio.run(
        get_ec_numbers_for_pdb(pdb_id, timeout=timeout, max_retries=max_retries)
    )
```

**API Endpoints**:
- **Entry**: `https://data.rcsb.org/rest/v1/core/entry/{pdb_id}`
- **Entity**: `https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}`
- **Legacy**: `https://www.rcsb.org/pdb/rest/customReport.json?structureId={pdb_id}&customReportColumns=ecNo,entityId`

**EC Number Extraction**:

Located in `_extract_ec_numbers_from_text()` (lines 72-81)
```python
# Matches canonical EC formats: "1.1.1.1" or partials "1.1.-.-"
pattern = r"\b\d+\.\d+\.(\d+|-)\.(\d+|-)\b"
```

The tool walks the entire JSON response tree to find EC numbers in any string field, ensuring comprehensive coverage.

**Error Handling**:
- Network errors: Retries with exponential backoff (0.5s → 1s → 2s)
- 404 responses: Returns empty EC numbers list
- Invalid PDB IDs: Raises `ValueError` with descriptive message
- Missing EC data: Returns gracefully with empty arrays
- All errors logged in `result["errors"]` list

**Rate Limiting**:
```python
_SEMAPHORE = asyncio.Semaphore(4)  # Max 4 concurrent requests
```

Prevents overwhelming the RCSB API when doing batch lookups.

**Example Integration with Extraction**:

```python
# After extracting PDB IDs from document
pdb_ids = extraction.get("pdb_ids", [])  # ["4FB7", "1ABC", ...]

# Fetch EC numbers for all PDB IDs
ec_data = {}
for pdb_id in pdb_ids:
    result = await get_ec_numbers_for_pdb(pdb_id)
    ec_data[pdb_id] = result["ec_numbers"]

# Add EC numbers to extraction results
extraction["pdb_ec_mapping"] = ec_data
```

---

## Data Flow

### Input Format

**File**: Markdown document in `data/` directory

**Structure**:
```markdown
# Enzyme Name

## Reaction Conditions
Temperature: 25°C
pH: 7.5
Buffer: Tris-HCl

## Kinetics
Km: 0.15 mM
Vmax: 45.2 μmol/min/mg

## Substrates
- Acetolactate
- NADPH

## Products
- 2,3-dihydroxy-3-isovalerate
- NADP+

## PDB IDs
1YZH, 2ABC
```

### Internal Data Transformation

```
Raw File (bytes)
    ↓
DocumentLoaderTool → Content String (str)
    ↓
build_user_prompt() → Prompt (str)
    ↓
LLM.generate() → Response String (JSON str)
    ↓
json.loads() → Parsed Dict (dict)
    ↓
extract_pdb_ids_from_text() → PDB IDs (List[str])
    ↓
Merge & Validate → ExtractionResult (Pydantic model)
    ↓
json.dump() → JSON File (file on disk)
```

### Alternative Data Transformation: Enzyme Design Extraction

```
Raw File (bytes) or HTML/text content
    ↓
DocumentLoaderTool / Content String (str)
    ↓
extract_steps() or extract_from_html()
    ↓
normalize_text() → Clean text (str)
    ↓
Split into paragraphs (List[str])
    ↓
_score_categories() → Score against 6 categories
    ↓
Filter by threshold (confidence ≥ 0.3)
    ↓
_create_step_record() → Step with metadata
    ↓
_group_by_component() → Group by Design/Assay/Optimization
    ↓
_calculate_overall_confidence() → Average score
    ↓
Return result with Chinese labels
```

**Comparison**:

| Aspect | Reaction Extraction | Design Extraction |
|--------|-------------------|-------------------|
| Input | Tables + paragraphs | Text/HTML paragraphs |
| Processing | LLM-based | Keyword scoring |
| Categories | Structured fields | 6 predefined categories |
| Output | Reaction objects | Step objects with confidence |
| Language | English | English + Chinese labels |
| Use case | Kinetic parameters | Design workflows |

### Output Format

**File**: `data/extraction/{filename}_extraction.json`

**Structure**:
```json
{
  "extraction": {
    "reactions": [
      {
        "source_file": "listov2025.md",
        "enzyme_name": "ketol-acid reductoisomerase",
        "substrates": ["acetolactate", "NADPH"],
        "products": ["2,3-dihydroxy-3-isovalerate", "NADP+"],
        "conditions": {
          "temperature": "25°C",
          "pH": "7.5",
          "buffer": "Tris-HCl",
          "time": "30 min",
          "notes": "Optimal conditions"
        },
        "kinetics": {
          "Km": 0.15,
          "Km_unit": "mM",
          "Vmax": 45.2,
          "Vmax_unit": "μmol/min/mg"
        },
        "yield_percent": 85.0,
        "citations": ["DOI:10.1016/j.chembiol.2024.01.001"],
        "pdb_ids": ["1YZH", "2ABC"]
      }
    ],
    "pipeline": {
      "steps": [
        {
          "name": "llm_extract",
          "description": "LLM extraction completed",
          "status": "success"
        }
      ],
      "validations": ["pdb_ids_extracted:2"],
      "errors": []
    }
  }
}
```

---

## Extension Points

### 1. Customize System Prompt

**Location**: `src/agents/specialized/llm_enzyme_extractor.py:18-30`

**How**: Modify `SYSTEM_PROMPT` constant

**Example**:
```python
SYSTEM_PROMPT = (
    "You are an expert in enzyme kinetics. "
    "Extract the following additional information:\n"
    "- Activation energy\n"
    "- Inhibitor constants\n"
    "- pH optimum profile\n"
    # ... rest of prompt
)
```

---

### 2. Add New Extraction Fields

**Location**: `src/tools/markdown_enzyme_parser.py`

**How**: Extend `Reaction` model

**Example**:
```python
class Reaction(BaseModel):
    # ... existing fields ...

    # New fields
    activation_energy: Optional[float]  # in kJ/mol
    inhibitors: List[str]  # List of inhibitors
    cofactors: List[str]  # Required cofactors
```

Then update system prompt to request these fields.

---

### 3. Add Validation Step

**Location**: `src/agents/specialized/llm_enzyme_extractor.py`

**How**: Add validation function after LLM extraction

**Example**:
```python
def validate_extraction(extraction: Dict) -> List[str]:
    errors = []
    for reaction in extraction.get("reactions", []):
        if not reaction.get("enzyme_name"):
            errors.append("Missing enzyme name")
        if not reaction.get("substrates"):
            errors.append("Missing substrates")
    return errors

# In extract_with_llm():
validation_errors = validate_extraction(data)
if validation_errors:
    pipeline["errors"].extend(validation_errors)
```

---

### 4. Process Multiple Files

**Location**: `examples/reaction_extractor_demo.py`

**How**: Loop through all markdown files

**Example**:
```python
# Instead of processing just listov2025.md
for md_file in md_files:
    print(f"Processing {md_file.name}...")
    result = await agent.process_task({
        "document": {
            "source_type": "file",
            "path": str(md_file)
        }
    })

    if result["status"] == "success":
        output_file = data_dir / "extraction" / f"{md_file.stem}_extraction.json"
        with open(output_file, "w") as f:
            json.dump(result["data"], f, indent=2, default=str)
        print(f"Saved to {output_file}")
```

---

### 5. Add Post-Processing

**Location**: `examples/reaction_extractor_demo.py` or agent

**How**: Process results after extraction

**Example**:
```python
# Add to demo after extraction
if result["status"] == "success":
    reactions = result["data"]["extraction"]["reactions"]

    # Post-process: find common enzymes
    enzyme_counts = {}
    for r in reactions:
        enzyme = r.get("enzyme_name", "Unknown")
        enzyme_counts[enzyme] = enzyme_counts.get(enzyme, 0) + 1

    print("Most common enzymes:")
    for enzyme, count in sorted(enzyme_counts.items(),
                                key=lambda x: x[1],
                                reverse=True)[:5]:
        print(f"  {enzyme}: {count} reactions")
```

---

### 6. Batch Processing with Parallelization

**How**: Use asyncio for concurrent processing

**Example**:
```python
async def process_file(agent, file_path):
    return await agent.process_task({
        "document": {
            "source_type": "file",
            "path": str(file_path)
        }
    })

# Process all files in parallel
tasks = [process_file(agent, md_file) for md_file in md_files]
results = await asyncio.gather(*tasks)

for md_file, result in zip(md_files, results):
    # Save each result
    pass
```

---

### 7. Add Result Enrichment

**How**: Fetch additional data from external APIs

**Example**:
```python
async def enrich_pdb_data(pdb_ids: List[str]) -> Dict:
    """Fetch PDB metadata from RCSB API."""
    enriched = {}
    for pdb_id in pdb_ids:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
            )
            enriched[pdb_id] = response.json()
    return enriched

# In workflow:
pdb_ids = extraction.get("pdb_ids", [])
pdb_metadata = await enrich_pdb_data(pdb_ids)
extraction["pdb_metadata"] = pdb_metadata
```

---

### 8. Complete Example: Enzyme Design with EC Number Enrichment

**How**: Combine enzyme design extraction with PDB/EC lookup

**Example**:
```python
"""Complete workflow: Enzyme design extraction with PDB/EC lookup"""

import asyncio
from src.agents.specialized.enzyme_design import EnzymeDesignAgent
from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb
from src.tools.implementations import DocumentLoaderTool
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

# Setup
tool_registry = ToolRegistry()
tool_registry.register_tools([DocumentLoaderTool()])
memory_manager = MemoryManager()
agent = EnzymeDesignAgent("enzyme_design_parser", memory_manager, tool_registry)

# Extract design steps
result = await agent.process_task({
    "document": {
        "source_type": "file",
        "path": "data/enzyme_engineering_paper.md"
    }
})

if result["status"] == "success":
    data = result["data"]
    print(f"Extracted {len(data['steps'])} design steps")
    print(f"Overall confidence: {data['confidence_overall']:.2f}")

    # Display steps by category
    for category, steps in data["components"].items():
        if steps:
            print(f"\n{category}: {len(steps)} steps")
            for step in steps[:3]:  # Show first 3
                print(f"  - {step[:80]}...")

    # Enrich with EC numbers (if PDB IDs are mentioned)
    # Note: You would need to extract PDB IDs separately from the document
    # This is a simplified example
    pdb_ids = ["4FB7", "1ABC"]  # From document analysis

    print("\nFetching EC numbers...")
    for pdb_id in pdb_ids:
        try:
            ec_result = await get_ec_numbers_for_pdb(pdb_id)
            if ec_result["ec_numbers"]:
                print(f"{pdb_id}: EC = {', '.join(ec_result['ec_numbers'])}")
            else:
                print(f"{pdb_id}: No EC numbers found")
        except Exception as e:
            print(f"{pdb_id}: Error - {e}")

    # Save results
    output_path = f"data/extraction/enzyme_design_extraction.json"
    # Save logic here...
```

**Expected Output**:
```
Extracted 24 design steps
Overall confidence: 0.72

Design: 8 steps
  - Active site residues were identified through structural analysis...
  - Computational design was performed using Rosetta...
  - Molecular dynamics simulations confirmed stability...

Assay: 6 steps
  - Kinetic assays were performed at 25°C...
  - KM was measured using varying substrate concentrations...
  - kcat values were calculated from initial rates...

Optimization: 10 steps
  - Directed evolution was conducted over 5 rounds...
  - Screening identified variants with improved activity...
  - Final optimized variant showed 3-fold improvement...

Fetching EC numbers...
4FB7: EC = 1.1.1.1
1ABC: EC = 2.7.7.1
```

---

## Future Improvements

### Short-Term Enhancements

1. **Better Error Handling**
   - Retry logic for LLM API timeouts
   - Graceful degradation for partial results
   - Detailed error messages for debugging

2. **Performance Optimization**
   - Batch process multiple documents
   - Cache LLM responses for repeated content
   - Parallel PDB ID enrichment

3. **Enhanced Validation**
   - Schema validation with detailed error reporting
   - Cross-field validation (e.g., units match values)
   - Confidence scores for extracted fields

4. **User Experience**
   - Progress bars for long-running operations
   - Summary statistics across multiple documents
   - Diff view for comparing extractions

### Medium-Term Features

1. **Multi-Document Processing**
   - Extract and merge reactions from multiple papers
   - Detect and resolve conflicts
   - Build comprehensive reaction database

2. **Result Browser**
   - Web interface to browse extracted reactions
   - Search and filter capabilities
   - Export to various formats (CSV, Excel)

3. **Quality Metrics**
   - Calculate extraction confidence
   - Flag uncertain extractions for review
   - Track improvement over time

4. **Integration Points**
   - Connect to biochemical databases (KEGG, BRENDA)
   - Validate extracted enzymes against databases
   - Enrich with external data

### Long-Term Vision

1. **Learning Loop**
   - Collect user corrections
   - Fine-tune prompts based on feedback
   - Improve extraction accuracy over time

2. **Advanced NLP**
   - Entity recognition for enzymes and chemicals
   - Relationship extraction between components
   - Context-aware interpretation

3. **Knowledge Graph**
   - Build knowledge graph from extracted data
   - Enable semantic queries
   - Discover hidden patterns

4. **Workflow Automation**
   - Automated literature monitoring
   - Continuous database updates
   - Alert system for new findings

---

## Troubleshooting

### Common Issues

**Issue**: "Missing API key" error

**Solution**:
```bash
export API_KEY="your-api-key"
python examples/reaction_extractor_demo.py
```

---

**Issue**: "No Markdown files found"

**Solution**:
- Ensure `.md` files are in `data/` directory
- Check file permissions
- Verify current working directory

---

**Issue**: LLM request timeout

**Solution**:
- Increase timeout in `config/llm_config.template.json`
- Check network connectivity
- Verify API endpoint is accessible
- Consider reducing document size

---

**Issue**: Empty extraction result

**Solution**:
- Check if document contains relevant data
- Review LLM response for errors
- Verify system prompt is appropriate
- Test with simpler document

---

**Issue**: Schema validation errors

**Solution**:
- Review LLM response format
- Check if all required fields are present
- Ensure data types match schema
- Validate JSON structure

**Issue**: LLM extracts data but validation returns 0 reactions

**Root Cause**: LLM returns `null` for list fields (e.g., `"products": null`) but schema requires a list

**Debugging Process**:
1. Check the extraction JSON error messages - if you see "Input should be a valid list [type=list_type, input_value=None, input_type=NoneType]" errors, this is the issue
2. Count how many validation errors appear - this indicates how many reactions the LLM actually extracted before validation failed
3. Review `src/agents/specialized/llm_enzyme_extractor.py` for sanitization logic

**Solution Applied**:
Added LLM output sanitization in `extract_with_llm()` function (`src/agents/specialized/llm_enzyme_extractor.py:92-97`):

```python
# Sanitize LLM output: convert None values in list fields to empty lists
for reaction in data.get("reactions", []):
    list_fields = ["substrates", "products", "citations", "pdb_ids"]
    for field in list_fields:
        if reaction.get(field) is None:
            reaction[field] = []
```

This ensures that any `null` values from the LLM are converted to empty lists before Pydantic validation.

**Verification**: After fix, check extraction count should match the number of validation errors you saw before

---

**Issue**: Enzyme design extraction returns no steps

**Solution**:
- Check if document contains relevant keywords from enzyme_terms.py
- Lower confidence threshold: modify `MIN_CONFIDENCE_THRESHOLD` in `src/tools/enzyme_extractor.py` (default: 0.3)
- Review `TERMS` dictionary in `src/tools/enzyme_terms.py` for relevant keywords
- Try processing as HTML if source is HTML (`source_type: "html"`)
- Verify paragraphs are not too long (long paragraphs get length penalty)

---

**Issue**: PDB/EC lookup returns empty EC numbers

**Solution**:
- Verify PDB ID is valid (4 alphanumeric characters, must have letter in last 3)
- Check network connectivity to data.rcsb.org
- Review error messages in `result["errors"]` field
- Some PDB entries may not have EC annotations (check RCSB website manually)
- Try the legacy API if primary API fails (automatic fallback)

---

**Issue**: LLM enhancement feature significantly increases processing cost

**Solution**:
- Disable LLM enhancement: omit `use_llm_enhancement` or set to `False`
- Use keyword-based extraction only (default behavior)
- Consider enabling LLM enhancement only for specific tables
- Batch multiple tables in single LLM call if possible

---

**Issue**: Chinese labels not appearing in design extraction results

**Solution**:
- Verify `CATEGORY_ZH` dictionary exists in `src/tools/enzyme_terms.py`
- Check that `label_zh` field is included in step records
- Ensure `label_zh` is being set in `_create_step_record()` function
- If missing, add: `"label_zh": CATEGORY_ZH.get(category, category)`

---

**Issue**: Orchestrator returns "agent not found" error

**Solution**:
- Verify orchestrator is initialized correctly: `orchestrator = AgentOrchestrator(FrameworkConfig())`
- Check agent name: use `agents["enzyme_kinetics_extractor"]` or `agents["enzyme_design_parser"]` (lowercase)
- Ensure config file is properly set up
- Verify agents are registered in orchestrator initialization

---

## Orchestrator Integration

**Location**: `src/agents/orchestrator.py:85-97`

Both enzyme extraction agents are integrated into the main `AgentOrchestrator`, providing unified access to all framework capabilities.

**Available Agents**:

```python
# In orchestrator.py initialization
self.agents = {
    "planner": PlannerAgent(...),
    "executor": ExecutorAgent(...),
    "tool_manager": ToolManagerAgent(...),
    "memory_manager": MemoryManagerAgent(...),
    "enzyme": LLMEnzymeExtractorAgent(...),      # Reaction extraction
    "enzyme_design_parser": EnzymeDesignAgent(...),  # Design parsing
}
```

**Usage via Orchestrator**:

```python
from src.core.config import FrameworkConfig
from src.agents.orchestrator import AgentOrchestrator

# Initialize orchestrator
config = FrameworkConfig()
orchestrator = AgentOrchestrator(config)

# Access enzyme reaction extraction agent
enzyme_agent = orchestrator.agents["enzyme_kinetics_extractor"]
result = await enzyme_agent.process_task({
    "document": {
        "source_type": "file",
        "path": "data/enzyme_paper.md"
    }
})

# Access enzyme design extraction agent
design_agent = orchestrator.agents["enzyme_design_parser"]
result = await design_agent.process_task({
    "document": {
        "source_type": "file",
        "path": "data/enzyme_design_paper.md"
    }
})
```

**Benefits of Orchestrator Integration**:

1. **Unified Access**: Single entry point for all framework agents
2. **Shared Resources**: Common memory manager and tool registry
3. **Consistent Configuration**: Centralized model manager setup
4. **Interoperability**: Easy to combine multiple agents in workflows

**Example: Combined Workflow**:

```python
# Extract reaction data and design steps from the same document
orchestrator = AgentOrchestrator(FrameworkConfig())

# Get reaction data
enzyme_result = await orchestrator.agents["enzyme_kinetics_extractor"].process_task({
    "document": {"source_type": "file", "path": "paper.md"}
})

# Get design workflow
design_result = await orchestrator.agents["enzyme_design_parser"].process_task({
    "document": {"source_type": "file", "path": "paper.md"}
})

# Combine results
combined = {
    "reactions": enzyme_result["data"]["extraction"]["reactions"],
    "design_steps": design_result["data"]["steps"],
    "confidence_overall": design_result["data"]["confidence_overall"]
}
```

---

## Quick Reference

### Run the Demo

```bash
# Set API key
export API_KEY="your-api-key"

# Run extraction
python examples/reaction_extractor_demo.py
```

### Key Files

| File | Purpose |
|------|---------|
| `examples/reaction_extractor_demo.py` | Main demo script |
| `src/agents/specialized/llm_enzyme_extractor.py` | LLM-based reaction extraction agent |
| `src/agents/specialized/enzyme_design.py` | Keyword-based design extraction agent |
| `src/tools/document_structure_analyzer.py` | Document structure analysis (tables, sections) |
| `src/tools/enzyme_extractor.py` | Keyword-based step extraction logic |
| `src/tools/enzyme_terms.py` | Category definitions (Chinese labels) |
| `src/tools/pdb_ec_lookup.py` | PDB to EC number lookup |
| `src/tools/implementations.py` | Document loader |
| `src/tools/markdown_enzyme_parser.py` | Result schema |
| `src/utils.py` | Model initialization |
| `config/llm_config.template.json` | LLM configuration |

### Modify Extraction Behavior

| Goal | Location |
|------|----------|
| Use enzyme design extraction | Create `EnzymeDesignAgent` instead of `LLMEnzymeExtractorAgent` |
| Enable LLM table enhancement | Set `use_llm_enhancement=True` in DocumentStructureAnalyzer |
| Add EC number lookup | Call `get_ec_numbers_for_pdb()` or `get_ec_numbers_for_pdb_sync()` |
| Change reaction extraction prompt | `llm_enzyme_extractor.py:SYSTEM_PROMPT` |
| Add reaction fields | `markdown_enzyme_parser.py:Reaction` |
| Add design keywords | `enzyme_terms.py:TERMS` dictionary |
| Add validation | `llm_enzyme_extractor.py:extract_with_llm()` |
| Process multiple files | `reaction_extractor_demo.py:main()` |

---

## Changelog

### Version 1.2 (2025-01-19)

**New Features**:
- Added EnzymeDesignAgent for keyword-based enzyme design step extraction
- Added PDB/EC number lookup tool with RCSB API integration
- Added LLM enhancement feature to DocumentStructureAnalyzer
- Added Chinese language support for enzyme design categories (CATEGORY_ZH)
- Added both enzyme agents to orchestrator (enzyme_kinetics_extractor, enzyme_design_parser)

**Enzyme Design Extraction**:
- Six categories: Planning, Design, Construction, Expression, Assay, Optimization
- Confidence-based scoring with 0.3 threshold
- Supports text and HTML content
- Provides Chinese labels for all categories
- Alternative to LLM-based extraction for design-focused documents

**PDB/EC Lookup Tool**:
- Fetches EC numbers from RCSB Protein Data Bank Data API
- Entity-level EC number mapping (e.g., "4FB7_1")
- Sync and async interfaces available
- Input validation with strict PDB ID format checking
- Dual API support: core endpoints + legacy fallback
- Rate limiting (4 concurrent requests)
- Comprehensive error handling with retries

**LLM Enhancement**:
- Optional LLM-based table analysis (`use_llm_enhancement=True`)
- Confidence scores (0.0-1.0) for table relevance
- Enhanced metadata: descriptions, data types, enzyme counts
- Overrides keyword detection when LLM confidence > 0.7

**Architecture Updates**:
- Dual pipeline architecture showing both extraction workflows
- Orchestrator integration for unified agent access
- Updated component references with all new tools
- Enhanced documentation with complete usage examples

**Documentation**:
- Comprehensive enzyme design workflow section
- PDB/EC lookup tool reference
- Updated quick reference tables
- New usage examples combining multiple tools
- Enhanced troubleshooting section

---

### Version 1.1 (2025-01-12)

**Bug Fix**: LLM output sanitization for list fields
- Added sanitization to convert `null` values to empty lists for required list fields
- Fixed issue where LLM extracted reactions but validation failed due to `products: null`
- This fix allows proper extraction of reactions from tables where products may not be explicitly stated
- See troubleshooting section: "LLM extracts data but validation returns 0 reactions"

### Version 1.0 (2025-01-11)

- Initial extraction pipeline
- Two-phase approach: document structure analysis + targeted LLM extraction
- DocumentStructureAnalyzer for identifying tables and key sections
- HTML table extraction support
- LLM-based extraction with PDB ID detection
- Single document processing
- JSON output with schema validation

---

## Contributing

When making changes to the extraction workflow:

1. Update this document to reflect changes
2. Add examples for new features
3. Update component reference section
4. Document new extension points
5. Add troubleshooting entries for new issues

---

**Last Updated**: 2025-01-12

**Maintainer**: GPTase Development Team
