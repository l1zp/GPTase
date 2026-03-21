# Visual Estimation

Use this path when shell access is unavailable, the image is only embedded in the thread,
or programmatic detection is less reliable than careful interpolation.

## Procedure

1. Record the visible calibration anchors.
2. Determine whether each relevant axis is linear or logarithmic.
3. Estimate the feature's fractional position between the nearest anchors.
4. Convert that fraction into a value.
5. Report uncertainty and the reason for it.

## Linear Interpolation

For a point at fraction `f` between two visible ticks:

```text
value = lower_tick_value + f * (upper_tick_value - lower_tick_value)
```

Example: halfway between `25` and `50` gives `37.5`.

## Logarithmic Interpolation

Never use linear interpolation on a log axis.

```text
log10(value) = log10(lower_tick) + f * (log10(upper_tick) - log10(lower_tick))
value = 10^(log10(value))
```

Example: one-third of the way from `100` to `1000`:

```text
log10(value) = 2 + 0.33 * (3 - 2) = 2.33
value ≈ 214
```

## Log-Scale Clues

Treat an axis as likely logarithmic when one or more of these are visible:

- Tick labels progress by powers of ten such as `0.1, 1, 10, 100`
- The axis label includes `log`
- The plotted range spans multiple orders of magnitude

State the evidence when the scale choice matters to the answer.

## Uncertainty

Attach uncertainty to every reported value. Use tighter bounds only when the figure is
clear enough to support them.

- Clean linear reading: often about `±5-10%`
- Crowded or anti-aliased figure: often about `±10-20%`
- Log axis or faint markers: often about `±15-30%`

If a value is only approximate, say so explicitly rather than implying false precision.
