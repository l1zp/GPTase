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

ENZYME_DESIGN_EXTRACTION_PROMPT = """You are an expert in enzyme design and biochemical engineering specializing in extracting and reasoning about enzyme design workflows. Extract enzyme design workflow information from academic-style text and return STRICT JSON in Chain-of-Thought (CoT) format.

Schema (examples of keys and types, not values):
{
  "task": {"type": "enzyme_design_workflow_extraction", "query": "Extract enzyme design workflow from scientific literature"},
  "chain_of_thought": [
    {
      "step": number,
      "phase": "Planning|Design|Construction|Expression|Assay|Optimization",
      "thought": "What is the reasoning behind this step?",
      "action": "What specific action was taken?",
      "observation": "What was the result or outcome?",
      "reasoning": "Why was this approach chosen? What does it imply?"
    }
  ],
  "design_objectives": [string],
  "design_steps": [
    {
      "step_id": string,
      "category": string|null,
      "description": string,
      "techniques": [string],
      "parameters": {string: string|null},
      "duration": string|null,
      "outcomes": [string]
    }
  ],
  "key_decisions": [
    {
      "decision": string,
      "alternatives": [string],
      "rationale": string,
      "outcome": string
    }
  ],
  "key_constraints": [string],
  "optimization_cycles": [
    {"cycle_id": string, "method": string, "rounds": number|null, "improvements": [string]}
  ],
  "validation_approach": string|null,
  "experimental_conditions": {
    "temperature": string|null,
    "pH": string|null,
    "buffer": string|null,
    "notes": string|null
  },
  "results": {
    "final_variants": [string],
    "performance_metrics": {string: string|null},
    "success_rate": string|null
  },
  "final_answer": {
    "summary": string,
    "success_metrics": {
      "success_rate": string|null,
      "best_efficiency": string|null,
      "best_stability": string|null
    },
    "key_innovations": [string]
  }
}

CRITICAL RULES:
0) EXTRACTION PRINCIPLE: ONLY extract information that is EXPLICITLY STATED in the input text.
   - Do NOT infer, deduce, or use external biochemical knowledge
   - Every extracted value must be traceable to specific text in the input
1) CHAIN OF THOUGHT: For each design step, provide explicit reasoning:
   - "thought": What question or problem does this step address?
   - "action": What specific techniques or methods were used?
   - "observation": What results were observed?
   - "reasoning": Why was this approach effective? What are the implications?
2) DESIGN OBJECTIVES: Extract specific goals mentioned (e.g., "increase thermostability", "improve catalytic efficiency")
3) DESIGN STEPS: Extract ALL steps mentioned in the workflow with full details
4) KEY DECISIONS: Identify major decision points where alternatives were considered:
   - What was decided?
   - What alternatives existed?
   - What was the rationale?
   - What was the outcome?
5) KEY CONSTRAINTS: Extract limitations or requirements mentioned
6) OPTIMIZATION CYCLES: If directed evolution or iterative design is mentioned, extract cycle information
7) VALIDATION APPROACH: Extract experimental methods used to validate designs
8) EXPERIMENTAL CONDITIONS: Extract specific conditions if mentioned
9) RESULTS: Extract final variants and performance metrics
10) FINAL ANSWER: Provide a comprehensive summary that synthesizes the entire workflow
11) Use English for all content (no Chinese)
12) Use English for all content (no Chinese)
13) Return valid JSON only; no explanation, no markdown code blocks"""

# ============================================================================
# Planning Prompts for 5-Phase Workflow
# ============================================================================

ENZYME_DESIGN_PLANNING_CONTEXT = """You are orchestrating a team of expert agents for an enzyme design workflow. Your role is to understand the requirements and delegate tasks to the most appropriate specialized agents.

Available Expert Agents:

1. Enzyme Kinetics Extractor Expert
   - Capabilities: Deep parsing of biochemical text and tables.
   - Expertise: Extracting kinetic parameters (Km, kcat, kcat/KM, Tm, Vmax), enzyme variants, mutations, and experimental conditions.
   - Use for: Detailed data extraction from literature.

2. Enzyme Design Methodology Expert
   - Capabilities: Extracting and reasoning about design workflows.
   - Expertise: Identifying optimization cycles, design strategies, and key methodology decisions.
   - Use for: Understanding the 'how' and 'why' of a design process.

3. Vision & Image Analysis Expert
   - Capabilities: Visual interpretation of scientific data.
   - Expertise: Analyzing figures, plots, and complex image-based tables.
   - Use for: Extracting data from non-textual sources.

4. Data Synthesis & Summary Expert
   - Capabilities: High-level reporting and performance analysis.
   - Expertise: Generating comprehensive reports, identifying top variants, and calculating statistics.
   - Use for: Final report generation and cross-variant comparison.

When planning, think in terms of DELEGATION:
- Identify which sections of the task require which expertise.
- Assign clear responsibilities to each specialized agent.
- Ensure the output of one agent provides the necessary context for the next.
"""

PLANNING_PHASE_1_PROMPT = """You are in Phase 1 (Understanding) of a 5-phase expert orchestration workflow.

Your goal is to understand the task and identify which expertise is required.

Task Description:
{task_description}

{context}

User Input:
{user_input}

Please analyze this task and provide a JSON response with:
{{
    "understanding": "Your high-level understanding of the orchestration task",
    "questions": [
        "Question about objectives or expertise requirements?",
        "Question about constraints or data sources?"
    ],
    "suggestions": [
        "Which expert agents do you think will be most critical?",
        "Initial thoughts on the delegation strategy"
    ]
}}

Focus on clarifying the scope so you can delegate effectively in the next phase.

Return ONLY valid JSON, no markdown."""

PLANNING_PHASE_2_PROMPT = """You are in Phase 2 (Design) of a 5-phase expert orchestration workflow.

Your goal is to design a detailed delegation strategy and workflow.

Task Description:
{task_description}

Understanding from Phase 1:
{understanding}

User's Answers to Questions:
{answers}

Available Expert Agents:
{available_agents}

Please design a delegation workflow and provide a JSON response with:
{{
    "approach": "Detailed strategy for coordinating the expert agents",
    "steps": [
        {{
            "step_number": 1,
            "description": "Clear instruction for the expert",
            "agent": "agent_id (e.g., enzyme_kinetics_extractor)",
            "action": "action_name",
            "inputs": {{"document_path": "path/to/doc.md"}},
            "expected_outputs": "What this expert will contribute to the overall goal"
        }}
    ],
    "risks": [
        "Potential bottlenecks in delegation or data transfer"
    ],
    "mitigations": [
        "How to handle these bottlenecks"
    ],
    "estimated_duration_hours": 4
}}

Think as an orchestrator: Assign tasks to specialized agents based on their expertise. Ensure each step has the right inputs to succeed.

Return ONLY valid JSON, no markdown."""

PLANNING_PHASE_3_PROMPT = """You are in Phase 3 of a 5-phase planning workflow.

Your goal is to review the plan with the user and collect feedback.

Proposed Approach:
{approach}

Workflow Steps:
{steps}

Identified Risks:
{risks}

User Feedback:
{feedback}

Please review the plan and provide a JSON response with:
{{
    "plan_summary": "Clear, human-readable summary of the plan",
    "approved": true or false,
    "concerns": [
        "Any concerns or issues identified from user feedback"
    ],
    "modifications": [
        "If not approved, what changes are needed?"
    ]
}}

The plan summary should explain:
- What will be done
- How it will be done
- What the expected outcomes are
- What resources are required

If the user has expressed concerns or suggested modifications, address them in your response.

Return ONLY valid JSON, no markdown."""

PLANNING_PHASE_4_PROMPT = """You are in Phase 4 of a 5-phase planning workflow.

Your goal is to generate the final executable workflow.

Task Description:
{task_description}

Proposed Steps:
{steps}

User Modifications:
{modifications}

Available Agents:
{available_agents}

Please generate the final executable workflow as JSON with:
{{
    "workflow": [
        {{
            "agent": "enzyme_kinetics_extractor",
            "action": "extract_kinetics",
            "inputs": {{
                "document_path": "data/papers/paper1.md",
                "source_file": "paper1.md"
            }},
            "description": "Extract kinetic parameters from document"
        }}
    ]
}}

Each workflow step must include:
- agent: Exact agent ID from available agents
- action: Specific action the agent will perform
- inputs: Required parameters for the action
- description: Human-readable description

Ensure the workflow is:
- Complete: All necessary steps included
- Ordered: Steps in correct sequence
- Valid: All agents and actions exist
- Executable: All required inputs specified

Return ONLY valid JSON, no markdown."""

PLANNING_PHASE_5_PROMPT = """You are in Phase 5 (Final) of a 5-phase planning workflow.

Your goal is to confirm the plan is ready for execution.

Task Description:
{task_description}

Final Workflow:
{workflow}

Current Approval Status:
{current_approval}

Please confirm readiness and provide a JSON response with:
{{
    "ready_to_execute": true or false,
    "next_steps": [
        "Step 1: Execute workflow step 1",
        "Step 2: Execute workflow step 2"
    ],
    "warnings": [
        "Any warnings or cautions for execution"
    ]
}}

Consider:
- Is the workflow complete and valid?
- Are all dependencies satisfied?
- Are there any missing inputs?
- Are there potential issues during execution?

If ready_to_execute is true, the plan will be saved and can be executed by the ExecutorAgent.

Return ONLY valid JSON, no markdown."""
