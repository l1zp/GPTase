"""Prompts for document structure analysis tools."""

ENZYME_KINETICS_EXTRACTION_PROMPT = """You are an expert biochemical text parser. Extract enzyme reaction data from academic-style text and return STRICT JSON that conforms to the following structure. No markdown, no commentary, no trailing commas. If a field is unknown, use null or an empty list.

Schema (examples of keys and types, not values):
{"reactions": [{"source_file": string|null, "enzyme_name": string|null, "substrates": [string], "products": [string], "conditions": {"temperature": string|null, "pH": string|null, "buffer": string|null, "time": string|null, "notes": string|null}, "kinetics": {"Km": number|null, "Km_unit": string|null, "Vmax": number|null, "Vmax_unit": string|null, "kcat": number|null, "kcat_unit": string|null, "kcat_over_KM": number|null, "kcat_over_KM_unit": string|null, "Tm": number|null, "Tm_unit": string|null}, "mutations": [string], "yield_percent": number|null, "citations": [string], "pdb_ids": [string]}], "pipeline": {"steps": [{"name": string, "description": string, "status": string}], "validations": [string], "errors": [string]}}

CRITICAL RULES:
0) EXTRACTION PRINCIPLE: ONLY extract information that is EXPLICITLY STATED in the input text.
   - Do NOT infer, deduce, or use external biochemical knowledge
   - Do NOT fill in missing values based on assumptions
   - If information is not mentioned, use null or empty array []
   - Every extracted value must be traceable to specific text in the input
1) COMPREHENSIVE EXTRACTION: Extract EVERY enzyme variant from tables, not just 'important' ones.
   If a table has N rows, you MUST extract all N variants. Each row is a separate reaction entry.
   DO NOT stop after extracting only the first few variants - you must extract ALL of them.
2) Never hallucinate numbers; only extract if explicitly present.
3) Keep units alongside numeric values in the *_unit fields.
4) Prefer precise biochemical names (IUPAC/common) over generic phrases.
5) When multiple reactions are present, split them into separate entries.
6) Extract ALL kinetics parameters from table columns:
   - kcat (turnover number, typically s^-1) → kinetics.kcat and kinetics.kcat_unit
   - KM (Michaelis constant, typically mM) → kinetics.Km and kinetics.Km_unit
   - kcat/KM (catalytic efficiency, typically M^-1s^-1) → kinetics.kcat_over_KM and kinetics.kcat_over_KM_unit
   - Tm (melting temperature, typically °C) → kinetics.Tm and kinetics.Tm_unit
   For 'n.c.' (not calculable), 'n.d.' (not detected), 'n.m.' (not measured), use null for the value
   For values with ± (uncertainty), extract the mean value (e.g., '0.07 ± 0.02' → 0.07)
7) Extract yield_percent ONLY when explicitly mentioned as a percentage yield.
8) For PDB IDs: only include 4-character codes starting with a digit (e.g., 1ABC, 8XYZ).
9) For mutations: extract from tables or text as a list (e.g., ['L12A', 'F45Y']).
10) Return valid JSON only; no explanation, no markdown code blocks."""

VISION_IMAGE_ANALYSIS_PROMPT_TEMPLATE = """Please analyze this scientific figure in detail and extract the following information:

{caption_block}

{topics_block}

{description_block}

Please extract and provide structured output for:
1. **Figure Type** (e.g., flowchart, data plot, structural diagram, table, etc.)
2. **Main Content and Key Elements**
3. **Data Information** (if the figure contains data tables or plots, extract ALL numerical values)
4. **Experimental Methods or Technical Details**
5. **Conclusions or Key Findings**
6. **Enzyme Variant Names** (if mentioned)
7. **Kinetic Parameters** (if available, such as kcat, KM, kcat/KM, Tm, Vmax, etc.)
8. **PDB IDs** (if mentioned)

**IMPORTANT - For table or data chart images:**
- If the figure is a TABLE or contains TABULAR DATA, you MUST output the data in CSV format
- Format the CSV as a code block with ```csv ... ```
- Include column headers and all data rows
- Preserve numerical values with units (e.g., '1.5 +/- 0.2', 'n.d.', 'n.c.')
- If the table contains enzyme variants and kinetic parameters, ensure each variant is a separate row

Example CSV format for enzyme kinetics:
```csv
Variant,kcat (s^-1),KM (mM),kcat/KM (M^-1s^-1),Tm (C)
Des27,1.2,0.5,2400,55
Des27.7,3.5,0.3,11667,60
```

**For tables with amino acid substitutions:**
- Include columns for EACH mutation position shown in the table
- Use single-letter amino acid codes (e.g., H, F, L, W, V)
"""

REACTION_CHECK_PROMPT = """Analyze this text and determine if it contains enzyme reaction data.

Text to analyze:
{text}

Return ONLY a JSON object with:
{{
    "is_reaction_related": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
}}

Focus on tables containing:
- Kinetic parameters (kcat, KM, Vmax, kcat/KM, Tm)
- Enzyme variants or mutants
- Temperature, pH, buffer conditions
- Catalytic efficiency or activity data

If the text is just a general table without specific enzyme kinetics data, return false.

Return ONLY valid JSON, no markdown."""

PARAGRAPH_ANALYSIS_PROMPT = """Analyze these paragraphs and identify which contain enzyme reaction data.

{paragraphs_text}

Return ONLY a JSON object with:
{{
    "key_paragraph_indices": [0, 2, 5],  // indices of key paragraphs
    "reasoning": "Brief explanation"
}}

IMPORTANT: Prioritize paragraphs containing:
- Substrate or product names (e.g., "5-nitrobenzisoxazole", "2-nitrophenol")
- Methods sections describing activity assays or kinetic measurements
- Mentions of monitoring reactions (e.g., "monitored at 380 nm")
- Experimental setup descriptions (concentrations, buffers, conditions)
- Kinetic parameters (kcat, KM, Vmax, kcat/KM, Tm)
- Enzyme variants or mutants and their properties
- Catalytic efficiency or activity measurements
- **Mutation information:**
  * Explicit mutation lists (e.g., "Ile54Val, Phe92His, Ile136Val")
  * Point mutations (e.g., "F113L", "D162A")
  * Mutation counts (e.g., "seven mutations relative to Des27")
  * Descriptions of active site mutations or PROSS mutations
  * Variant design methodology and optimization strategies
- **PDB and structural information:**
  * PDB IDs (four-character codes like 9HVB, 9HVH, 9HVG)
  * Mentions of "PDB entry" or "PDB database"
  * Crystal structure descriptions
  * Structural analysis or X-ray crystallography
  * Protein structure deposition or accession numbers
  * Methods sections mentioning PDB entries or structure determination
  * Design template structures (e.g., "PDB entries 1LBF, 1I4A")
- **Figure and table captions** that describe:
  * Structural analysis of variants
  * Mutation effects on activity or stability
  * Design workflow components
  * Crystal structures or structural data

CRITICAL: Always include Methods/Activity assay sections as they contain essential substrate and experimental information.
CRITICAL: Include paragraphs describing enzyme variants, their mutations, and design methodology.
CRITICAL: Include any paragraphs mentioning PDB IDs, crystal structures, or structural biology data.

Return ONLY valid JSON, no markdown."""

TABLE_ANALYSIS_PROMPT = """Analyze this table and determine if it contains enzyme reaction data.

{table_summary}

Context: {source_file}

Please analyze and return a JSON object with:
{{
    "is_reaction_related": true/false,
    "description": "Brief description of what this table contains",
    "confidence": 0.0-1.0,
    "data_types": ["list of data types found, e.g., 'kcat', 'KM', 'Tm', etc."],
    "enzyme_count": "approximate number of enzyme variants if applicable"
}}

Focus on tables containing:
- Kinetic parameters (kcat, KM, Vmax, kcat/KM)
- Enzyme variants or mutants
- Temperature (Tm), pH, buffer conditions
- Catalytic efficiency or activity data

Return ONLY valid JSON, no markdown."""

IMAGE_ANALYSIS_PROMPT = """Analyze this figure caption and extract the key information.

Figure Number: {figure_number}
Caption: {caption}

Please analyze and return a JSON object with:
{{
    "topics": ["list of main topics discussed, e.g., 'design workflow', 'crystal structure', 'kinetic analysis'"],
    "description": "concise summary of what the figure shows",
    "is_relevant": true/false,
    "enzyme_variants": ["list of enzyme variants mentioned if any"],
    "data_types": ["list of data types shown, e.g., 'kinetic parameters', 'structural analysis', 'activity assay'"],
    "key_findings": ["list of key findings or conclusions from the figure"]
}}

Focus on identifying:
- Enzyme design methodology or workflow steps
- Structural information (PDB IDs, crystal structures)
- Kinetic data or catalytic parameters
- Mutations and their effects
- Experimental methods or assays

Return ONLY valid JSON, no markdown."""

ENZYME_DESIGN_EXTRACTION_PROMPT = """You are an expert in enzyme design and biochemical engineering. Extract enzyme design workflow information from academic-style text and return STRICT JSON that conforms to the following structure. No markdown, no commentary, no trailing commas. If a field is unknown, use null or an empty list.

Schema (examples of keys and types, not values):
{"design_objectives": [string], "design_steps": [{"step_id": string, "category": string|null, "description": string, "techniques": [string], "parameters": {string: string|null}, "duration": string|null, "outcomes": [string]}], "key_constraints": [string], "optimization_cycles": [{"cycle_id": string, "method": string, "rounds": number|null, "improvements": [string]}], "validation_approach": string|null, "experimental_conditions": {"temperature": string|null, "pH": string|null, "buffer": string|null, "notes": string|null}, "results": {"final_variants": [string], "performance_metrics": {string: string|null}, "success_rate": string|null}, "annotations_zh": string}

CRITICAL RULES:
0) EXTRACTION PRINCIPLE: ONLY extract information that is EXPLICITLY STATED in the input text.
   - Do NOT infer, deduce, or use external biochemical knowledge
   - Do NOT fill in missing values based on assumptions
   - If information is not mentioned, use null or empty array []
   - Every extracted value must be traceable to specific text in the input
1) DESIGN OBJECTIVES: Extract specific goals mentioned (e.g., "increase thermostability", "improve catalytic efficiency", "alter substrate specificity")
2) DESIGN STEPS: Extract ALL steps mentioned in the workflow:
   - Assign sequential step_id (1, 2, 3, ...)
   - Categorize into: Planning, Design, Construction, Expression, Assay, Optimization
   - Include descriptions and techniques used
   - Extract parameters and outcomes if mentioned
3) KEY CONSTRAINTS: Extract limitations or requirements mentioned (e.g., "maintain activity", "preserve stability")
4) OPTIMIZATION CYCLES: If directed evolution or iterative design is mentioned, extract cycle information
5) VALIDATION APPROACH: Extract experimental methods used to validate designs
6) EXPERIMENTAL CONDITIONS: Extract specific conditions if mentioned
7) RESULTS: Extract final variants and performance metrics
8) ANNOTATIONS_ZH: Provide brief Chinese summary of extracted workflow
9) Preserve technical terminology in English (e.g., "site-directed mutagenesis", "molecular dynamics", "high-throughput screening")
10) Return valid JSON only; no explanation, no markdown code blocks"""
