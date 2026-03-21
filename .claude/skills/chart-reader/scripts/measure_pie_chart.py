#!/usr/bin/env python3
"""Reference OpenCV extractor for pie or donut charts."""

from __future__ import annotations

import argparse

import cv2
import numpy as np

from chart_utils import dump_json
from chart_utils import ensure_parent
from chart_utils import load_image
from chart_utils import write_debug_image


def detect_circle(img_gray):
    circles = cv2.HoughCircles(
        img_gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=50,
        param1=60,
        param2=30,
        minRadius=max(10, min(img_gray.shape) // 8),
        maxRadius=min(img_gray.shape) // 2,
    )
    if circles is None:
        return None
    x, y, r = circles[0][0]
    return int(x), int(y), int(r)


def cluster_segments(img, center, radius, clusters=5):
    cx, cy = center
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    cv2.circle(mask, (cx, cy), radius, 255, -1)
    pixels = img[mask > 0].reshape(-1, 3).astype(np.float32)
    compactness, labels, centers = cv2.kmeans(
        pixels,
        clusters,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.2),
        5,
        cv2.KMEANS_PP_CENTERS,
    )
    del compactness
    counts = np.bincount(labels.flatten(), minlength=clusters)
    segments = []
    total = counts.sum()
    for index, count in enumerate(counts):
        if count == 0:
            continue
        color = centers[index].astype(int).tolist()
        segments.append({
            "cluster_index": int(index),
            "rgb": [int(color[2]), int(color[1]), int(color[0])],
            "pixel_fraction": round(float(count / total), 4),
            "percentage": round(float(count / total) * 100, 2),
        })
    segments.sort(key=lambda item: item["percentage"], reverse=True)
    return segments


def main():
    parser = argparse.ArgumentParser(description="Estimate pie-slice percentages by color segmentation.")
    parser.add_argument("image_path")
    parser.add_argument("--clusters", type=int, default=5)
    parser.add_argument("--debug", default=None)
    args = parser.parse_args()

    img = load_image(args.image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    circle = detect_circle(gray)
    if circle is None:
        raise SystemExit("Could not detect pie circle. Crop the image first or adjust Hough parameters.")
    cx, cy, radius = circle
    segments = cluster_segments(img, (cx, cy), radius, clusters=args.clusters)

    if args.debug:
        ensure_parent(args.debug)
        overlays = [("circle", (cx, cy, radius, (0, 255, 0)))]
        write_debug_image(img, args.debug, overlays)

    dump_json({
        "chart_type": "pie",
        "image": args.image_path,
        "center": {"x": cx, "y": cy},
        "radius": radius,
        "segments": segments,
        "notes": [
            "Reference script for pie or donut charts with distinct slice colors.",
            "Map clusters to legend labels manually when text is outside the pie.",
        ],
    })


if __name__ == "__main__":
    main()
