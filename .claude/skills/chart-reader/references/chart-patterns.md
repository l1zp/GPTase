# Chart Patterns

Use this file when the chart requires chart-specific extraction tactics beyond a simple
single-series bar chart.

## Bar and Grouped Bar

- Measure the top edge of each bar.
- Calibrate from y-axis ticks before converting bar tops to values.
- For grouped bars, isolate each series by color or by x-position.
- For stacked bars, measure each segment boundary, not just the total bar height.
- Start from [`measure_bar_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_bar_chart.py) when using OpenCV.

## Histograms

- Read bin ranges from the x-axis and heights from the y-axis.
- Report counts, density, or frequency exactly as labeled on the axis.
- Do not treat histogram bars as categorical bars unless the x-axis is categorical.
- If bins are uneven, report each bin width explicitly.

## Line Charts

- Calibrate both axes.
- Isolate each series by color when possible.
- Sample at visible x ticks or another stated interval.
- If a line is thick, use the centerline and widen uncertainty.
- Start from [`trace_line_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/trace_line_chart.py) when using OpenCV.

## Scatter Plots

- Measure marker centroids, not the fitted curve, unless the user asked for the curve.
- Distinguish series by marker color and shape.
- If points overlap heavily, report only the points you can separate confidently.
- Start from [`detect_scatter_points.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/detect_scatter_points.py) when using OpenCV.

## Fitted Curves

- State explicitly that the reading target is the fitted curve.
- Describe how the curve is distinguished from scatter points: smoothness, continuity, color, or line style.
- When asked for one value on the curve, project from the x-axis to the curve and then to the y-axis.

## Multi-Panel Figures

- Identify the exact panel before extracting anything.
- Keep results separated by panel label or position.
- Do not borrow axes or legends from neighboring panels unless the figure clearly shares them.

## Dual-Axis Charts

- Match the target series to the correct axis by color, side, label, or legend.
- State explicitly whether the left or right axis was used.
- If the axis-to-series mapping is ambiguous, report that ambiguity before giving values.

## Pie and Donut Charts

- Convert slice angle to percentage using `angle / 360`.
- Ensure reported percentages sum to about `100%`; explain any mismatch caused by rounding.
- Start from [`measure_pie_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_pie_chart.py) when using OpenCV.

## Heatmaps

- Read values through the colorbar, not by guessing from hue names.
- Calibrate several colorbar tick positions before estimating cell values.
- If the map is large, return the requested cells or summarize range and extremes.
- Start from [`sample_heatmap.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/sample_heatmap.py) when using OpenCV.

## Box Plots

- Report whisker minimum and maximum, `Q1`, median, and `Q3`.
- Include visible outliers only if they are clearly separate markers.
- If notches are present, ignore them unless the user specifically asks about confidence intervals.

## Violin Plots

- Prefer qualitative density summaries unless the user explicitly wants width-at-y extraction.
- If extracting widths, state that width represents density rather than a direct axis value.

## Error Bars

- Report the central mark and the error extent separately.
- State whether the bars appear symmetric or asymmetric.
- Do not guess whether the error bars represent SD, SEM, or CI unless the figure says so.

## Failure Modes

Switch to partial extraction with explicit caveats when:

- The plot area is too small to calibrate reliably
- Tick labels are cropped or unreadable
- Overlapping marks cannot be separated
- Transparency, anti-aliasing, or unusual styling breaks segmentation

Do not fabricate hidden values. Return only defensible readings.
