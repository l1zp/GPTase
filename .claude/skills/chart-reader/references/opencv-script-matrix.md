# OpenCV Script Matrix

Choose a reference script after you identify the chart class and the exact reading target.

## Selection Order

1. Decide the chart class from vision.
2. Decide the reading target within that class.
3. Choose the closest script below.
4. Adjust parameters or patch the script when the chart styling does not match the baseline assumptions.

## Reference Scripts

### Bar charts

- Script: [`scripts/measure_bar_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_bar_chart.py)
- Use for: simple bars, grouped bars, stacked bars when the segment boundaries are visible
- Inputs:
  - `--y-ticks`
  - optional `--plot-area`
  - optional `--log-y`
  - threshold and strategy flags
- Typical adjustments:
  - tighten contour filters for thin bars
  - provide explicit `--plot-area`
  - switch between `color` and `edge`

### Line charts and fitted curves

- Script: [`scripts/trace_line_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/trace_line_chart.py)
- Use for: dark line charts, fitted curves, saturation curves
- Inputs:
  - `--x-ticks`
  - `--y-ticks`
  - optional `--plot-area`
  - optional `--exclude-rects`
  - optional `--disable-auto-text-mask`
  - optional `--log-x`, `--log-y`
- Typical adjustments:
  - rely on default auto text masking first for in-plot annotations
  - add `--exclude-rects` when the default auto mask does not cover all annotation text
  - use `--disable-auto-text-mask` if the auto mask overlaps the target curve
  - change threshold when the target line is not the darkest feature
  - mask by color if multiple lines overlap
  - increase `--stride` for faster coarse tracing

### Scatter plots

- Script: [`scripts/detect_scatter_points.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/detect_scatter_points.py)
- Use for: isolated markers where centroid extraction is possible
- Inputs:
  - `--x-ticks`
  - `--y-ticks`
  - optional `--plot-area`
  - optional `--exclude-rects`
  - optional `--disable-auto-text-mask`
  - optional `--method hough`
  - contour area limits
- Typical adjustments:
  - rely on default auto text masking first for in-plot annotations
  - add `--exclude-rects` when the default auto mask does not cover all annotation text
  - use `--disable-auto-text-mask` if the auto mask overlaps true markers
  - switch to `--method hough` when markers overlap a fitted curve
  - restrict contour area when points are noisy
  - add color masking when the fitted curve interferes
  - run separately per series if markers differ by color

### Pie and donut charts

- Script: [`scripts/measure_pie_chart.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/measure_pie_chart.py)
- Use for: distinct-color slices where legend mapping can be done separately
- Inputs:
  - optional `--clusters`
- Typical adjustments:
  - crop tightly around the pie before running
  - adjust cluster count to match visible slices
  - map clusters to labels using the legend in the image

### Heatmaps

- Script: [`scripts/sample_heatmap.py`](/Users/ryanxu/CodeBase/GPTase/.claude/skills/chart-reader/scripts/sample_heatmap.py)
- Use for: regular heatmap grids with known row and column counts
- Inputs:
  - `--plot-area`
  - `--rows`
  - `--cols`
- Typical adjustments:
  - crop out dendrograms or labels
  - extend the script if colorbar-to-value mapping is required

## Adaptation Rule

These are reference scripts, not rigid pipelines. When the baseline script is close but not
correct, patch or parameterize it for the current image instead of forcing a bad extraction.

Common safe modifications:

- pass a manual `--plot-area`
- change threshold values
- add a color mask in HSV space
- tighten contour size filters
- sample fewer or more x-columns
- save a debug image and inspect misdetections before trusting values
