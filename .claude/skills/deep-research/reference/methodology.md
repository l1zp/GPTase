# Deep Research Methodology: 8-Phase Pipeline

## Overview

This document contains the detailed methodology for conducting deep research. The 8 phases represent a comprehensive approach to gathering, verifying, and synthesizing information from multiple sources.

---

## Phase 1: SCOPE - Research Framing

**Objective:** Define research boundaries and success criteria

**Activities:**
1. Decompose the question into core components
2. Identify stakeholder perspectives
3. Define scope boundaries (what's in/out)
4. Establish success criteria
5. List key assumptions to validate

**Ultrathink Application:** Use extended reasoning to explore multiple framings of the question before committing to scope.

**Output:** Structured scope document with research boundaries

---

## Phase 2: PLAN - Strategy Formulation

**Objective:** Create an intelligent research roadmap

**Activities:**
1. Identify primary and secondary sources
2. Map knowledge dependencies (what must be understood first)
3. Create search query strategy with variants
4. Plan triangulation approach
5. Estimate time/effort per phase
6. Define quality gates

**Graph-of-Thoughts:** Branch into multiple potential research paths, then converge on optimal strategy.

**Output:** Research plan with prioritized investigation paths

---

## Phase 3: RETRIEVE - Parallel Information Gathering

**Objective:** Systematically collect information from multiple sources using parallel execution for maximum speed

**CRITICAL: Execute ALL searches in parallel using a single message with multiple tool calls**

### Search Engine Strategy (3-Tier Architecture)

**Tier 1: Brave Search (Fast Broad Coverage)**
- Tool: `mcp__brave-search__brave_web_search`
- Use for: Quick broad searches, news, general web content
- Strengths: Speed, privacy-focused, clean results
- Parameters: `query` (required), `count` (1-20, default 10)
- Example: `mcp__brave-search__brave_web_search(query="quantum computing 2025", count=10)`

**Tier 2: Tavily Search (Deep Research)**
- Tool: `mcp__tavily-search__tavily_search`
- Use for: In-depth research, comprehensive analysis, technical topics
- Strengths: Research-optimized, includes raw content, advanced filtering
- Parameters:
  - `query` (required)
  - `max_results` (5-20, default 5)
  - `search_depth` ("basic"/"advanced", default "basic")
  - `include_raw_content` (true/false)
  - `include_domains` / `exclude_domains` (list)
  - `time_range` ("day"/"week"/"month"/"year")
- Advanced tools:
  - `mcp__tavily-search__tavily_extract`: Extract content from specific URLs
  - `mcp__tavily-search__tavily_crawl`: Crawl websites for comprehensive coverage
  - `mcp__tavily-search__tavily_research`: AI-powered comprehensive research
- Example: `mcp__tavily-search__tavily_search(query="quantum computing", max_results=10, search_depth="advanced")`

**Tier 3: OpenAlex (Academic Papers)**
- Tool: WebFetch to `https://api.openalex.org/works`
- Use for: Peer-reviewed papers, citations, author information
- Strengths: Academic rigor, citation data, DOI lookup, open access links
- Query patterns:
  - Basic search: `?search={query}&per-page=20&sort=publication_date:desc`
  - Filter by year: `&filter=from_publication_date:2024-01-01`
  - Open access only: `&filter=is_oa:true`
  - Sort by citations: `&sort=cited_by_count:desc`
  - Filter by type: `&filter=type:article`
- Example: `WebFetch("https://api.openalex.org/works?search=quantum+computing&per-page=15&sort=publication_date:desc")`

### Query Decomposition Strategy

Before launching searches, decompose the research question into 5-10 independent search angles:

1. **Core topic (semantic search)** - Meaning-based exploration of main concept
2. **Technical details (keyword search)** - Specific terms, APIs, implementations
3. **Recent developments (date-filtered)** - What's new in 2024-2025
4. **Academic sources (domain-specific)** - Papers, research, formal analysis
5. **Alternative perspectives (comparison)** - Competing approaches, criticisms
6. **Statistical/data sources** - Quantitative evidence, metrics, benchmarks
7. **Industry analysis** - Commercial applications, market trends
8. **Critical analysis/limitations** - Known problems, failure modes, edge cases

### Parallel Execution Protocol

**Step 1: Launch ALL searches concurrently (single message)**

**CRITICAL: Use ALL three search engines in parallel for comprehensive coverage**

**Example parallel execution (multi-engine):**
```
[Single message with 12-18 parallel tool calls]

# Tier 1: Brave Search (3-4 queries for broad coverage)
mcp__brave-search__brave_web_search(query="quantum computing 2025 state of the art", count=10)
mcp__brave-search__brave_web_search(query="quantum computing commercial applications", count=10)
mcp__brave-search__brave_web_search(query="quantum computing industry trends 2024", count=10)

# Tier 2: Tavily Search (3-4 queries for depth)
mcp__tavily-search__tavily_search(query="quantum computing limitations challenges", max_results=10, search_depth="advanced")
mcp__tavily-search__tavily_search(query="quantum error correction research", max_results=10, include_raw_content=true)
mcp__tavily-search__tavily_search(query="quantum computing vs classical comparison", max_results=10)

# Tier 3: OpenAlex (2-3 queries for academic)
WebFetch("https://api.openalex.org/works?search=quantum+computing&per-page=15&sort=publication_date:desc&filter=from_publication_date:2024-01-01")
WebFetch("https://api.openalex.org/works?search=quantum+computing&per-page=10&sort=cited_by_count:desc&filter=is_oa:true")

# Spawn parallel deep-dive agents (3-5 agents)
Task(subagent_type="general-purpose", description="Analyze academic papers", prompt="Extract key findings from OpenAlex results on quantum computing")
Task(subagent_type="general-purpose", description="Industry analysis", prompt="Analyze industry trends from Tavily and Brave results")
Task(subagent_type="general-purpose", description="Technical deep dive", prompt="Extract technical details from research sources")
```

**Step 2: Content Extraction**

After initial results, use additional tools:
- `mcp__tavily-search__tavily_extract`: Deep-dive into 5-10 most promising URLs
- `mcp__tavily-search__tavily_crawl`: For comprehensive site coverage (max_depth=2)
- WebFetch: For OpenAlex paper abstracts and detailed source content

**Step 3: Collect and organize results**

As results arrive:
1. Extract key passages with source metadata (title, URL, date, credibility)
2. Track which search engine found each source (Brave/Tavily/OpenAlex)
3. Track information gaps that emerge
4. Follow promising tangents with additional targeted searches
5. Maintain source diversity (mix academic, industry, news, technical docs)
6. Monitor for quality threshold (see FFS pattern below)

### Engine Selection Guide

| Scenario | Primary Engine | Secondary | Academic Source |
|----------|---------------|-----------|-----------------|
| Breaking news/trends | Brave | Tavily | - |
| Technical research | Tavily | Brave | OpenAlex |
| Academic analysis | OpenAlex | Tavily | OpenAlex |
| Market analysis | Brave + Tavily | - | OpenAlex (optional) |
| Comparative study | All three in parallel | - | OpenAlex |
| Literature review | OpenAlex (primary) | Tavily | OpenAlex |

### First Finish Search (FFS) Pattern

**Adaptive completion based on quality threshold:**

**Quality gate:** Proceed to Phase 4 when FIRST threshold reached:
- **Quick mode:** 10+ sources with avg credibility >60/100 OR 2 minutes elapsed
- **Standard mode:** 20+ sources with avg credibility >60/100 (at least 3 from OpenAlex) OR 5 minutes elapsed
- **Deep mode:** 30+ sources with avg credibility >70/100 (at least 5 from OpenAlex) OR 10 minutes elapsed
- **UltraDeep mode:** 40+ sources with avg credibility >75/100 (at least 8 from OpenAlex) OR 15 minutes elapsed

**Continue background searches:**
- If threshold reached early, continue remaining parallel searches in background
- Additional sources used in Phase 5 (SYNTHESIZE) for depth and diversity
- Allows fast progression without sacrificing thoroughness

### Quality Standards

**Source diversity requirements:**
- Minimum 3 source types (academic, industry, news, technical docs)
- **Academic sources required for Standard/Deep/UltraDeep modes** (use OpenAlex)
- Temporal diversity (mix of recent 2024-2025 + foundational older sources)
- Perspective diversity (proponents + critics + neutral analysis)
- Geographic diversity (not just US sources)
- Engine diversity (sources from at least 2 of 3 engines)

**Credibility tracking:**
- Score each source 0-100 using source_evaluator.py
- Academic papers from OpenAlex start at credibility 80+
- Flag low-credibility sources (<40) for additional verification
- Prioritize high-credibility sources (>80) for core claims

**Source metadata tracking:**
- URL/location
- Title
- Key excerpts
- Relevance score (1-10)
- Source type (web/academic/news/documentation)
- Search engine used (Brave/Tavily/OpenAlex)
- Retrieved timestamp

**Output:** Organized information repository with source tracking, credibility scores, engine attribution, and coverage map

---

## Phase 4: TRIANGULATE - Cross-Reference Verification

**Objective:** Validate information across multiple independent sources

**Activities:**
1. Identify claims requiring verification
2. Cross-reference facts across 3+ sources
3. Flag contradictions or uncertainties
4. Assess source credibility
5. Note consensus vs. debate areas
6. Document verification status per claim

**Quality Standards:**
- Core claims must have 3+ independent sources
- Flag any single-source information
- Note recency of information
- Identify potential biases

**Output:** Verified fact base with confidence levels

---

## Phase 4.5: OUTLINE REFINEMENT - Dynamic Evolution (WebWeaver 2025)

**Objective:** Adapt research direction based on evidence discovered

**Problem Solved:** Prevents "locked-in" research when evidence points to different conclusions or uncovers more important angles than initially planned.

**When to Execute:**
- **Standard/Deep/UltraDeep modes only** (Quick mode skips this)
- After Phase 4 (TRIANGULATE) completes
- Before Phase 5 (SYNTHESIZE)

**Activities:**

1. **Review Initial Scope vs. Actual Findings**
   - Compare Phase 1 scope with Phase 3-4 discoveries
   - Identify unexpected patterns or contradictions
   - Note underexplored angles that emerged as critical
   - Flag overexplored areas that proved less important

2. **Evaluate Outline Adaptation Need**

   **Signals for adaptation (ANY triggers refinement):**
   - Major findings contradict initial assumptions
   - Evidence reveals more important angle than originally scoped
   - Critical subtopic emerged that wasn't in original plan
   - Original research question was too broad/narrow based on evidence
   - Sources consistently discuss aspects not in initial outline

   **Signals to keep current outline:**
   - Evidence aligns with initial scope
   - All key angles adequately covered
   - No major gaps or surprises

3. **Refine Outline (if needed)**

   **Update structure to reflect evidence:**
   - Add sections for unexpected but important findings
   - Demote/remove sections with insufficient evidence
   - Reorder sections based on evidence strength and importance
   - Adjust scope boundaries based on what's actually discoverable

   **Example adaptation:**
   ```
   Original outline:
   1. Introduction
   2. Technical Architecture
   3. Performance Benchmarks
   4. Conclusion

   Refined after Phase 4 (evidence revealed security as critical):
   1. Introduction
   2. Technical Architecture
   3. **Security Vulnerabilities (NEW - major finding)**
   4. Performance Benchmarks (demoted - less critical than expected)
   5. **Real-World Failure Modes (NEW - pattern emerged)**
   6. Synthesis & Recommendations
   ```

4. **Targeted Gap Filling (if major gaps found)**

   If outline refinement reveals critical knowledge gaps:
   - Launch 2-3 targeted searches for newly identified angles
   - Quick retrieval only (don't restart full Phase 3)
   - Time-box to 2-5 minutes
   - Update triangulation for new evidence only

5. **Document Adaptation Rationale**

   Record in methodology appendix:
   - What changed in outline
   - Why it changed (evidence-driven reasons)
   - What additional research was conducted (if any)

**Quality Standards:**
- Adaptation must be evidence-driven (cite specific sources that prompted change)
- No more than 50% outline restructuring (if more needed, scope was severely mis scoped)
- Retain original research question core (don't drift into different topic entirely)
- New sections must have supporting evidence already gathered

**Output:** Refined outline that accurately reflects evidence landscape, ready for synthesis

**Anti-Pattern Warning:**
- ❌ DON'T adapt outline based on speculation or "what would be interesting"
- ❌ DON'T add sections without supporting evidence already in hand
- ❌ DON'T completely abandon original research question
- ✅ DO adapt when evidence clearly indicates better structure
- ✅ DO document rationale for changes
- ✅ DO stay within original topic scope

---

## Phase 5: SYNTHESIZE - Deep Analysis

**Objective:** Connect insights and generate novel understanding

**Activities:**
1. Identify patterns across sources
2. Map relationships between concepts
3. Generate insights beyond source material
4. Create conceptual frameworks
5. Build argument structures
6. Develop evidence hierarchies

**Ultrathink Integration:** Use extended reasoning to explore non-obvious connections and second-order implications.

**Output:** Synthesized understanding with insight generation

---

## Phase 6: CRITIQUE - Quality Assurance

**Objective:** Rigorously evaluate research quality

**Activities:**
1. Review for logical consistency
2. Check citation completeness
3. Identify gaps or weaknesses
4. Assess balance and objectivity
5. Verify claims against sources
6. Test alternative interpretations

**Red Team Questions:**
- What's missing?
- What could be wrong?
- What alternative explanations exist?
- What biases might be present?
- What counterfactuals should be considered?

**Output:** Critique report with improvement recommendations

---

## Phase 7: REFINE - Iterative Improvement

**Objective:** Address gaps and strengthen weak areas

**Activities:**
1. Conduct additional research for gaps
2. Strengthen weak arguments
3. Add missing perspectives
4. Resolve contradictions
5. Enhance clarity
6. Verify revised content

**Output:** Strengthened research with addressed deficiencies

---

## Phase 8: PACKAGE - Report Generation

**Objective:** Deliver professional, actionable research

**Activities:**
1. Structure report with clear hierarchy
2. Write executive summary
3. Develop detailed sections
4. Create visualizations (tables, diagrams)
5. Compile full bibliography
6. Add methodology appendix

**Output:** Complete research report ready for use

---

## Advanced Features

### Graph-of-Thoughts Reasoning

Rather than linear thinking, branch into multiple reasoning paths:
- Explore alternative framings in parallel
- Pursue tangential leads that might be relevant
- Merge insights from different branches
- Backtrack and revise as new information emerges

### Parallel Agent Deployment

Use Task tool to spawn sub-agents for:
- Parallel source retrieval
- Independent verification paths
- Competing hypothesis evaluation
- Specialized domain analysis

### Adaptive Depth Control

Automatically adjust research depth based on:
- Information complexity
- Source availability
- Time constraints
- Confidence levels

### Citation Intelligence

Smart citation management:
- Track provenance of every claim
- Link to original sources
- Assess source credibility
- Handle conflicting sources
- Generate proper bibliographies
