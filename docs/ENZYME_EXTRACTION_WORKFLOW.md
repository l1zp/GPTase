# Enzyme Reaction Extraction Workflow

This document provides a comprehensive reference for the enzyme reaction extraction pipeline, as implemented in `examples/reaction_extractor_demo.py`. Use this as a guide for understanding, extending, and improving the extraction system.

## Overview

The enzyme extraction pipeline uses a **two-phase approach** to extract structured biochemical reaction data from scientific literature:

1. **Phase 1: Document Structure Analysis** - Identify and locate tables, key sections, and relevant content
2. **Phase 2: Targeted LLM Extraction** - Extract structured data only from identified relevant sections

This approach significantly improves accuracy by focusing the LLM on relevant content and maintaining traceability of data sources.

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

## Component Reference

### 1. DocumentStructureAnalyzer (NEW!)

**Location**: `src/tools/document_structure_analyzer.py`

**Purpose**: Analyze document structure to identify tables and key sections before LLM extraction

**Class**: `DocumentStructureAnalyzer(BaseTool)`

**Key Methods**:
```python
async def execute(text: str, source_file: str = None) -> ToolResult
```

**Methods**:
```python
_identify_sections(text: str) -> List[Dict[str, Any]]
_extract_tables(text: str) -> List[Dict[str, Any]]
_identify_key_paragraphs(text: str, sections: List) -> List[Dict[str, Any]]
_is_reaction_related(text: str) -> bool
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

**Output**:
```python
{
    "source_file": "data/listov2025.md",
    "total_tables": 6,
    "total_key_paragraphs": 83,
    "sections": [...],
    "tables": [...],
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
| `src/agents/specialized/llm_enzyme_extractor.py` | Extraction agent |
| `src/tools/implementations.py` | Document loader |
| `src/tools/markdown_enzyme_parser.py` | Result schema |
| `src/utils.py` | Model initialization |
| `config/llm_config.template.json` | LLM configuration |

### Modify Extraction Behavior

| Goal | Location |
|------|----------|
| Change prompt | `llm_enzyme_extractor.py:SYSTEM_PROMPT` |
| Add fields | `markdown_enzyme_parser.py:Reaction` |
| Add validation | `llm_enzyme_extractor.py:extract_with_llm()` |
| Process multiple files | `reaction_extractor_demo.py:main()` |

---

## Changelog

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
