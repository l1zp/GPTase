---
name: chart-reader
description: >
  Extract quantitative data from chart and figure images with explicit uncertainty.
  Use when the user provides a chart, plot, or data-bearing scientific figure and wants
  numeric values, digitized points, bar heights, curve readings, percentages, heatmap
  cells, box-plot summaries, or verification of a value read from the image. Trigger for
  bar charts, line charts, scatter plots, pie or donut charts, heatmaps, box plots,
  violin plots, histograms, and subplot figures, including requests like "read this chart",
  "extract the values", "digitize this figure", or "what is the point on the fitted curve".
---

# Chart Reader

Extract defendable numbers, not vague descriptions. Inspect the figure first, then use the
most reliable measurement path available for the exact reading target.

## Core Workflow

### 1. Lock the scope before measuring

Inspect the image directly and write down:

- The panel to read if the figure has subplots
- The chart class
- The exact reading target: bars, segment boundaries, scatter points, fitted curve, pie slices, heatmap cells, box summaries
- The axis labels, units, visible tick labels, and whether each axis is linear or logarithmic
- Whether the plot has dual axes, and which side belongs to the target series
- The legend entries, colors, marker shapes, and text annotations that affect isolation

If a scatter plot also has a fitted line, explicitly state whether you are reading `scatter points`
or the `fitted curve`. Do not mix them in one extraction.

If the user asks for "the figure" but the image has multiple panels, do not merge panels. Name the
panel you measured, such as `Figure 2b` or `right panel`.

### 2. Choose the measurement path

Choose the most reliable path that is actually available:

- `Phase 2A: OpenCV measurement`
  Use when you have a local image path and shell access.
- `Phase 2B: Systematic visual estimation`
  Use when shell access is unavailable, the figure is too messy for scripting, or the image only exists in-thread. Follow [`references/visual-estimation.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/visual-estimation.md) instead of guessing.

For `Phase 2A`, always classify first and then choose the closest reference script from [`references/opencv-script-matrix.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/opencv-script-matrix.md):

- bars: [`scripts/measure_bar_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_bar_chart.py)
- lines or fitted curves: [`scripts/trace_line_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/trace_line_chart.py)
- scatter points: [`scripts/detect_scatter_points.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/detect_scatter_points.py)
- pie or donut charts: [`scripts/measure_pie_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_pie_chart.py)
- heatmaps: [`scripts/sample_heatmap.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/sample_heatmap.py)

Treat those scripts as editable references, not fixed pipelines. If the first run misses the target, adjust parameters or patch the script for the current figure.

Read [`references/chart-patterns.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/chart-patterns.md) when the chart is not a simple bar chart or you need chart-specific extraction tactics.

### 3. Calibrate before measuring

Treat visible ticks and labels as calibration anchors. Build the pixel-to-value mapping before
reading any feature values.

- Use at least two visible anchors per measured axis.
- For linear axes, interpolate linearly.
- For log axes, interpolate in log space.
- If the axis type is uncertain, state the evidence and your best determination.
- For dual-axis charts, calibrate only the axis used by the target series.
- For heatmaps, calibrate from the colorbar instead of the cell grid.

If the measured result conflicts with the visible axis range, assume calibration is wrong and
re-check the plot area, tick mapping, or axis choice.

### 4. Measure the target, not the chart in general

Choose the extraction tactic that matches the reading target:

- Bar, grouped bar, or stacked bar: measure top edges or segment boundaries
- Scatter plot: measure marker centroids
- Fitted curve or line chart: trace the line centerline and widen uncertainty for thick strokes
- Pie or donut chart: convert slice angle to percent and check that totals are about `100%`
- Heatmap: sample requested cells and map color through the colorbar
- Box plot: report whiskers, `Q1`, median, and `Q3`
- Violin plot: prefer qualitative density summaries unless the user explicitly requests width-at-y
- Histogram: report bin ranges and heights or counts, not just bar centers

Use [`references/chart-patterns.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/chart-patterns.md) for chart-specific tactics and failure modes.

### 5. Escalate or fall back cleanly

For the OpenCV path, do one focused extraction pass first:

- pass an explicit `--plot-area` when auto-detection is wrong
- rely on default auto text masking first when the chart has an in-plot annotation block
- add `--exclude-rects` when auto masking misses text or other non-target marks
- use `--disable-auto-text-mask` only when the auto mask is hiding data you actually need
- mask non-target series when they contaminate detection
- save and inspect a debug image before trusting dense or unusual charts

If the closest script is almost correct, patch it or adjust parameters. If one focused script
pass still cannot isolate the target, switch to visual estimation or partial extraction and say why.

### 6. Report data with uncertainty

Every extracted value must include uncertainty or an explicit uncertainty note.

- OpenCV path: usually report pixel-limited uncertainty, often based on `±1-2 px`
- Visual path: report range or percent uncertainty, usually `±5-15%`
- Log-scale readings: widen uncertainty if spacing or tick placement is ambiguous

Prefer tables. Include units. Mention missing categories or expected labels that are not actually
visible in the figure.

## Output Rules

Always include:

- What was read
- Which panel was read if the figure has multiple panels
- Which method was used: `OpenCV` or `visual estimation`
- Which chart class you identified before extraction
- Which axis was used when the figure has dual axes
- Whether the reading target was `scatter points` or `fitted curve` when both exist
- The extracted values with units and uncertainty
- Any important limits, ambiguities, or omitted values

If you cannot reliably isolate every value, return the subset you can defend and clearly
label the rest as uncertain, unreadable, or out of scope.

Do not invent hidden values, cropped labels, or off-panel data.

## OpenCV Rules

When you use shell-based extraction:

- Prefer passing an explicit `--plot-area` when auto-detection looks wrong.
- Expect scatter and fitted-curve scripts to auto-mask lower-panel text annotations by default.
- Add `--exclude-rects` when you need extra masking beyond the default auto mask.
- Use `--disable-auto-text-mask` if the auto mask overlaps real data.
- Crop or exclude in-plot text annotations when they would otherwise be detected as lines, points, or bars.
- Prefer tick-pair calibration over guessing from image bounds.
- Save and inspect a debug image before trusting the numbers when the chart is dense or unusual.
- If the closest reference script is almost right, edit it or add a small one-off mask instead of switching to pure guessing.
- If the chart still resists automation after one focused script pass, fall back to visual estimation and say why.

## Resource Guide

- Use [`references/opencv-script-matrix.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/opencv-script-matrix.md) to select the closest reference script for the chart class.
- Use [`scripts/measure_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_chart.py) as the legacy bar-chart entry point. It now delegates to the dedicated bar extractor.
- Use [`references/visual-estimation.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/visual-estimation.md) for manual interpolation, especially when shell access is denied or the axis is logarithmic.
- Use [`references/chart-patterns.md`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/references/chart-patterns.md) for chart-specific measurement patterns, calibration notes, and failure modes.
