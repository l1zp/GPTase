#!/usr/bin/env python3
"""Reference OpenCV extractor for simple, grouped, or stacked bar charts."""

from __future__ import annotations

import argparse

import cv2
import numpy as np

from chart_utils import build_axis_transform
from chart_utils import crop_roi
from chart_utils import dump_json
from chart_utils import ensure_parent
from chart_utils import load_image
from chart_utils import parse_plot_area
from chart_utils import parse_tick_pairs
from chart_utils import resolve_plot_area
from chart_utils import write_debug_image


def detect_bars_from_projection(binary, plot_area):
    x0, y0, w, h = plot_area["x"], plot_area["y"], plot_area["w"], plot_area["h"]
    working = binary.copy()
    working[:, :8] = 0
    working[:, w - 3:] = 0

    column_counts = (working > 0).sum(axis=0)
    # Keep very short bars on log-scale charts instead of requiring tall projections.
    active = column_counts > max(4, int(h * 0.02))

    spans = []
    start = None
    for idx, is_active in enumerate(active):
        if is_active and start is None:
            start = idx
        elif not is_active and start is not None:
            spans.append((start, idx))
            start = None
    if start is not None:
        spans.append((start, len(active)))

    bars = []
    for left, right in spans:
        width = right - left
        if width < 6:
            continue
        patch = working[:, left:right]
        ys, xs = np.where(patch > 0)
        if len(ys) == 0:
            continue
        top = int(ys.min())
        bottom = int(ys.max())
        if bottom < h * 0.45:
            continue
        bars.append({
            "x_center_pixel": int(x0 + left + width / 2),
            "top_y_pixel": int(y0 + top),
            "width_px": int(width),
            "height_px": int(bottom - top + 1),
        })

    bars.sort(key=lambda item: item["x_center_pixel"])
    for index, bar in enumerate(bars):
        bar["bar_index"] = index
    return bars


def detect_bars(img, plot_area, strategy="auto", threshold=200):
    roi = crop_roi(img, plot_area)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    masks = []
    if strategy in {"auto", "color"}:
        _, dark_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, np.ones((5, 3), np.uint8))
        masks.append(("color", dark_mask))

    if strategy in {"auto", "edge"}:
        edges = cv2.Canny(gray, 20, 80)
        edges = cv2.dilate(edges, np.ones((5, 3), np.uint8), iterations=1)
        masks.append(("edge", edges))

    best_name = None
    best_bars = []
    best_mask = None
    for name, mask in masks:
        bars = detect_bars_from_projection(mask, plot_area)
        if len(bars) > len(best_bars):
            best_name = name
            best_bars = bars
            best_mask = mask
    return best_name or strategy, best_bars, best_mask


def main():
    parser = argparse.ArgumentParser(description="Extract bar heights from a chart image.")
    parser.add_argument("image_path")
    parser.add_argument("--y-ticks", required=True, help="pixel:value pairs, e.g. 290:0,40:100")
    parser.add_argument("--plot-area", default=None, help="x,y,w,h. Prefer passing this when auto-detection is wrong.")
    parser.add_argument("--log-y", action="store_true")
    parser.add_argument("--threshold", type=int, default=200)
    parser.add_argument("--strategy", choices=["auto", "color", "edge"], default="auto")
    parser.add_argument("--debug", default=None)
    args = parser.parse_args()

    img = load_image(args.image_path)
    plot_area = resolve_plot_area(img, parse_plot_area(args.plot_area))
    if plot_area is None:
        raise SystemExit("Could not detect plot area. Pass --plot-area x,y,w,h.")

    y_transform = build_axis_transform(parse_tick_pairs(args.y_ticks), log_scale=args.log_y)
    strategy_used, bars, _ = detect_bars(img, plot_area, strategy=args.strategy, threshold=args.threshold)
    for bar in bars:
        bar["value"] = round(y_transform(bar["top_y_pixel"]), 4)

    if args.debug:
        ensure_parent(args.debug)
        overlays = [("rect", (plot_area["x"], plot_area["y"], plot_area["w"], plot_area["h"], (0, 200, 0)))]
        for bar in bars:
            overlays.append(("circle", (bar["x_center_pixel"], bar["top_y_pixel"], 5, (0, 0, 255))))
        write_debug_image(img, args.debug, overlays)

    dump_json({
        "chart_type": "bar",
        "image": args.image_path,
        "plot_area": plot_area,
        "strategy_used": strategy_used,
        "bars": bars,
        "notes": [
            "Reference script for single-series, grouped, or stacked bars.",
            "Adjust threshold, plot area, or contour filters for light bars and unusual axes.",
        ],
    })


if __name__ == "__main__":
    main()
