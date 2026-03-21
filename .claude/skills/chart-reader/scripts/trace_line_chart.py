#!/usr/bin/env python3
"""Reference OpenCV extractor for line or fitted-curve charts."""

from __future__ import annotations

import argparse

import cv2
import numpy as np

from chart_utils import build_axis_transform
from chart_utils import crop_roi
from chart_utils import detect_text_annotation_rects
from chart_utils import dump_json
from chart_utils import ensure_parent
from chart_utils import load_image
from chart_utils import mask_exclude_rects
from chart_utils import merge_overlapping_rects
from chart_utils import parse_plot_area
from chart_utils import parse_rects
from chart_utils import parse_tick_pairs
from chart_utils import resolve_plot_area
from chart_utils import write_debug_image


def trace_dark_line(img, plot_area, min_columns=20, stride=4, threshold=160, exclude_rects=None):
    roi = crop_roi(img, plot_area)
    roi = mask_exclude_rects(roi, exclude_rects)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]

    points = []
    for col in range(0, mask.shape[1], stride):
        ys = np.where(mask[:, col] > 0)[0]
        if len(ys) == 0:
            continue
        y = int(np.median(ys))
        points.append((plot_area["x"] + col, plot_area["y"] + y))

    if len(points) < min_columns:
        return []
    return points


def main():
    parser = argparse.ArgumentParser(description="Trace a line or fitted curve from a chart image.")
    parser.add_argument("image_path")
    parser.add_argument("--x-ticks", required=True, help="pixel:value pairs")
    parser.add_argument("--y-ticks", required=True, help="pixel:value pairs")
    parser.add_argument("--plot-area", default=None, help="x,y,w,h")
    parser.add_argument("--log-x", action="store_true")
    parser.add_argument("--log-y", action="store_true")
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--threshold", type=int, default=160)
    parser.add_argument("--exclude-rects", default=None, help="plot-area-relative x,y,w,h;x,y,w,h to mask before tracing")
    parser.add_argument("--disable-auto-text-mask", action="store_true")
    parser.add_argument("--debug", default=None)
    args = parser.parse_args()

    img = load_image(args.image_path)
    plot_area = resolve_plot_area(img, parse_plot_area(args.plot_area))
    if plot_area is None:
        raise SystemExit("Could not detect plot area. Pass --plot-area x,y,w,h.")

    x_transform = build_axis_transform(parse_tick_pairs(args.x_ticks), log_scale=args.log_x)
    y_transform = build_axis_transform(parse_tick_pairs(args.y_ticks), log_scale=args.log_y)
    roi = crop_roi(img, plot_area)
    exclude_rects = parse_rects(args.exclude_rects)
    auto_exclude_rects = [] if args.disable_auto_text_mask else detect_text_annotation_rects(roi, threshold=max(140, args.threshold))
    exclude_rects = merge_overlapping_rects(exclude_rects + auto_exclude_rects, gap=8)
    raw_points = trace_dark_line(
        img,
        plot_area,
        stride=args.stride,
        threshold=args.threshold,
        exclude_rects=exclude_rects,
    )

    points = [{
        "x_pixel": x_px,
        "y_pixel": y_px,
        "x_value": round(x_transform(x_px), 4),
        "y_value": round(y_transform(y_px), 4),
    } for x_px, y_px in raw_points]

    if args.debug:
        ensure_parent(args.debug)
        overlays = [("rect", (plot_area["x"], plot_area["y"], plot_area["w"], plot_area["h"], (0, 200, 0)))]
        for rect in exclude_rects:
            overlays.append((
                "rect",
                (
                    plot_area["x"] + rect["x"],
                    plot_area["y"] + rect["y"],
                    rect["w"],
                    rect["h"],
                    (255, 140, 0),
                ),
            ))
        for point in raw_points:
            overlays.append(("circle", (point[0], point[1], 2, (0, 0, 255))))
        write_debug_image(img, args.debug, overlays)

    dump_json({
        "chart_type": "line",
        "image": args.image_path,
        "plot_area": plot_area,
        "exclude_rects": exclude_rects,
        "auto_exclude_rects": auto_exclude_rects,
        "points": points,
        "notes": [
            "Reference script for dark lines or fitted curves.",
            "Auto-detects lower-panel text annotations and masks them before tracing.",
            "Pass --exclude-rects to add manual masks or --disable-auto-text-mask to opt out.",
            "Adjust threshold, stride, or add color masking when the target line is not the darkest mark.",
        ],
    })


if __name__ == "__main__":
    main()
