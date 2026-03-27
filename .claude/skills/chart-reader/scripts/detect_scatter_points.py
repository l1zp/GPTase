#!/usr/bin/env python3
"""Reference OpenCV extractor for scatter points."""

from __future__ import annotations

import argparse
import math

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
import cv2
import numpy as np


def find_points_from_contours(roi, threshold=150, min_area=10, max_area=500):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    points = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if h == 0:
            continue
        aspect_ratio = w / h
        if aspect_ratio < 0.5 or aspect_ratio > 1.8:
            continue
        perimeter = cv2.arcLength(cnt, True)
        circularity = 0.0 if perimeter == 0 else (4 * math.pi * area) / (perimeter
                                                                         * perimeter)
        if circularity < 0.04:
            continue
        moments = cv2.moments(cnt)
        if moments["m00"] == 0:
            continue
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
        points.append((cx, cy, float(area), {
            "source": "contour",
            "circularity": round(circularity, 3),
        }))
    points.sort(key=lambda item: item[0])
    return points


def find_points_from_hough(roi,
                           min_radius=3,
                           max_radius=8,
                           min_distance=18,
                           param1=80,
                           param2=11):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_distance,
        param1=param1,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    points = []
    if circles is not None:
        for circle in circles[0]:
            x, y, radius = [int(round(value)) for value in circle]
            points.append((x, y, float(radius), {
                "source": "hough",
                "radius_px": radius,
            }))
    points.sort(key=lambda item: item[0])
    return points


def dedupe_points(points, distance_px=12):
    deduped = []
    for point in sorted(points, key=lambda item: item[0]):
        if any(
                np.hypot(point[0] - kept[0], point[1] - kept[1]) < distance_px
                for kept in deduped):
            continue
        deduped.append(point)
    return deduped


def find_points(img,
                plot_area,
                threshold=150,
                min_area=10,
                max_area=500,
                exclude_rects=None,
                method="auto"):
    roi = crop_roi(img, plot_area)
    roi = mask_exclude_rects(roi, exclude_rects)

    contour_points = find_points_from_contours(
        roi,
        threshold=threshold,
        min_area=min_area,
        max_area=max_area,
    )
    hough_points = find_points_from_hough(roi)

    if method == "contour":
        return contour_points
    if method == "hough":
        return hough_points

    if exclude_rects and len(hough_points) >= max(4, len(contour_points)):
        return dedupe_points(hough_points)

    combined = dedupe_points(contour_points + hough_points)
    if len(combined) >= len(contour_points):
        return combined
    return contour_points


def main():
    parser = argparse.ArgumentParser(
        description="Extract scatter-point centroids from a chart image.")
    parser.add_argument("image_path")
    parser.add_argument("--x-ticks", required=True, help="pixel:value pairs")
    parser.add_argument("--y-ticks", required=True, help="pixel:value pairs")
    parser.add_argument("--plot-area", default=None, help="x,y,w,h")
    parser.add_argument("--log-x", action="store_true")
    parser.add_argument("--log-y", action="store_true")
    parser.add_argument("--threshold", type=int, default=150)
    parser.add_argument("--min-area", type=float, default=10)
    parser.add_argument("--max-area", type=float, default=500)
    parser.add_argument(
        "--exclude-rects",
        default=None,
        help="plot-area-relative x,y,w,h;x,y,w,h to mask before detection")
    parser.add_argument("--method",
                        choices=["auto", "contour", "hough"],
                        default="auto")
    parser.add_argument("--disable-auto-text-mask", action="store_true")
    parser.add_argument("--debug", default=None)
    args = parser.parse_args()

    img = load_image(args.image_path)
    plot_area = resolve_plot_area(img, parse_plot_area(args.plot_area))
    if plot_area is None:
        raise SystemExit("Could not detect plot area. Pass --plot-area x,y,w,h.")

    x_transform = build_axis_transform(parse_tick_pairs(args.x_ticks),
                                       log_scale=args.log_x)
    y_transform = build_axis_transform(parse_tick_pairs(args.y_ticks),
                                       log_scale=args.log_y)
    roi = crop_roi(img, plot_area)
    exclude_rects = parse_rects(args.exclude_rects)
    auto_exclude_rects = [] if args.disable_auto_text_mask else detect_text_annotation_rects(
        roi, threshold=max(140, args.threshold))
    exclude_rects = merge_overlapping_rects(exclude_rects + auto_exclude_rects, gap=8)
    raw_points = find_points(
        img,
        plot_area,
        threshold=args.threshold,
        min_area=args.min_area,
        max_area=args.max_area,
        exclude_rects=exclude_rects,
        method=args.method,
    )
    points = [{
        "x_pixel": plot_area["x"] + x_px,
        "y_pixel": plot_area["y"] + y_px,
        "feature_size_px": round(size, 2),
        "x_value": round(x_transform(plot_area["x"] + x_px), 4),
        "y_value": round(y_transform(plot_area["y"] + y_px), 4),
        **meta,
    } for x_px, y_px, size, meta in raw_points]

    if args.debug:
        ensure_parent(args.debug)
        overlays = [("rect", (plot_area["x"], plot_area["y"], plot_area["w"],
                              plot_area["h"], (0, 200, 0)))]
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
        for point in points:
            overlays.append(
                ("circle", (point["x_pixel"], point["y_pixel"], 4, (0, 0, 255))))
        write_debug_image(img, args.debug, overlays)

    dump_json({
        "chart_type":
        "scatter",
        "image":
        args.image_path,
        "plot_area":
        plot_area,
        "exclude_rects":
        exclude_rects,
        "auto_exclude_rects":
        auto_exclude_rects,
        "method":
        args.method,
        "points":
        points,
        "notes": [
            "Reference script for isolated scatter markers.",
            "Auto-detects lower-panel text annotations and masks them before point detection.",
            "Pass --exclude-rects to add manual masks or --disable-auto-text-mask to opt out.",
            "Use --method hough when markers overlap with a fitted curve and contour extraction merges them.",
        ],
    })


if __name__ == "__main__":
    main()
