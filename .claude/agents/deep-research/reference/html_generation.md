# HTML Report Generation

This document describes the process for generating McKinsey-style HTML reports from deep-research output.

## Overview

The deep-research skill generates professional HTML reports using a McKinsey-style template. These reports feature:
- Sharp corners (no border-radius)
- Muted corporate colors (navy #003d5c, gray #f8f9fa)
- Ultra-compact layout
- Info-first structure
- Metrics dashboard at top

## Generation Steps

### Step 1: Read McKinsey Template

```python
template_path = "./templates/mckinsey_report_template.html"
with open(template_path, 'r') as f:
    template = f.read()
```

### Step 2: Extract Key Metrics for Dashboard

Extract 3-4 key quantitative findings from the research for the metrics dashboard:
- Market sizes
- Growth rates
- Key statistics
- Comparison metrics

### Step 3: Convert Markdown to HTML

Use the provided Python script:

```bash
cd ~/.claude/skills/deep-research
python scripts/md_to_html.py [markdown_report_path]
```

The script returns two parts:
- **Part A ({{CONTENT}}):** All sections except Bibliography, converted to HTML
- **Part B ({{BIBLIOGRAPHY}}):** Bibliography section only, formatted as HTML

**Conversion rules:**
- `##` → `<div class="section"><h2 class="section-title">`
- `###` → `<h3 class="subsection-title">`
- Markdown bullets → `<ul><li>` with proper nesting
- Markdown tables → `<table>` with thead/tbody
- Paragraphs wrapped in `<p>` tags
- `**text**` → `<strong>`, `*text*` → `<em>`
- Citations `[N]` preserved for tooltip conversion

### Step 4: Add Citation Tooltips (Optional)

For each `[N]` citation in {{CONTENT}}, optionally add interactive tooltips:

```html
<span class="citation">[N]
  <span class="citation-tooltip">
    <div class="tooltip-title">[Source Title]</div>
    <div class="tooltip-source">[Author/Publisher]</div>
    <div class="tooltip-claim">
      <div class="tooltip-claim-label">Supports Claim:</div>
      [Extract sentence with this citation]
    </div>
  </span>
</span>
```

Note: This step is optional for speed. Basic `[N]` citations are sufficient.

### Step 5: Replace Template Placeholders

Replace the following placeholders in the template:

| Placeholder | Value |
|-------------|-------|
| `{{TITLE}}` | Report title (extract from first `##` heading) |
| `{{DATE}}` | Generation date (YYYY-MM-DD format) |
| `{{SOURCE_COUNT}}` | Number of unique sources |
| `{{METRICS_DASHBOARD}}` | Metrics HTML from Step 2 |
| `{{CONTENT}}` | HTML from Part A (script output) |
| `{{BIBLIOGRAPHY}}` | HTML from Part B (script output) |

### Step 6: Remove Emojis

**CRITICAL:** Remove any emoji characters from the final HTML. The McKinsey template uses a strictly professional style with no decorative elements.

```bash
# Use sed or Python to remove emojis
python -c "import re; content = open('report.html').read(); open('report.html', 'w').write(re.sub(r'[^\x00-\x7F]+', '', content))"
```

### Step 7: Save HTML File

Save to: `[Documents folder]/research_report_[YYYYMMDD]_[slug].html`

### Step 8: Verify HTML (MANDATORY)

Run verification script:

```bash
python scripts/verify_html.py --html [html_path] --md [md_path]
```

Checks:
- All sections present
- No missing placeholders
- Valid HTML structure
- Citation count matches

If check fails: Fix errors and re-run verification.

### Step 9: Open in Browser

```bash
open [html_path]
```

## Template Structure

The McKinsey template includes:

1. **Header** - Title, date, source count
2. **Metrics Dashboard** - 3-4 key quantitative findings
3. **Table of Contents** - Auto-generated from sections
4. **Main Content** - All findings and analysis
5. **Bibliography** - All sources cited
6. **Footer** - Generation metadata

## CSS Classes

Key CSS classes used in the template:

| Class | Purpose |
|-------|---------|
| `.section` | Section container |
| `.section-title` | Main section headings |
| `.subsection-title` | Subsection headings |
| `.citation` | Citation wrapper |
| `.citation-tooltip` | Hover tooltip for citations |
| `.metrics-dashboard` | Top metrics display |
| `.data-table` | Tables with data |

## Example Output Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>Research Report: [Topic]</title>
  <style>/* McKinsey styles */</style>
</head>
<body>
  <header>
    <h1>Research Report: [Topic]</h1>
    <div class="metadata">Date: 2025-03-11 | Sources: 25</div>
  </header>

  <div class="metrics-dashboard">
    <div class="metric">Market Size: $2.4B</div>
    <div class="metric">Growth Rate: 15%</div>
    <div class="metric">Key Players: 5</div>
  </div>

  <main>
    <div class="section">
      <h2 class="section-title">Executive Summary</h2>
      <p>...</p>
    </div>

    <div class="section">
      <h2 class="section-title">Main Analysis</h2>
      <p>...</p>
    </div>

    <!-- More sections -->
  </main>

  <footer>
    <h2 class="section-title">Bibliography</h2>
    <ol>
      <li>[1] Source citation...</li>
      <!-- More citations -->
    </ol>
  </footer>
</body>
</html>
```

## PDF Generation

After HTML is generated and verified, use the generating-pdf skill to create a professional PDF:

1. Use Task tool with general-purpose agent
2. Invoke generating-pdf skill with markdown as input
3. Save to: `[folder]/research_report_[YYYYMMDD]_[slug].pdf`
4. PDF will auto-open when complete
