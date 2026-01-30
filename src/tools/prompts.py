"""Prompts for document structure analysis tools."""

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
