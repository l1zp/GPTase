#!/usr/bin/env python3
"""Reference OpenCV extractor for heatmap grids."""

from __future__ import annotations

import argparse

from chart_utils import crop_roi
from chart_utils import dump_json
from chart_utils import load_image
from chart_utils import parse_plot_area
import cv2


def sample_grid(img, plot_area, rows, cols):
    roi = crop_roi(img, plot_area)
    cell_h = roi.shape[0] / rows
    cell_w = roi.shape[1] / cols
    cells = []
    for row in range(rows):
        for col in range(cols):
            y0 = int(row * cell_h)
            y1 = int((row + 1) * cell_h)
            x0 = int(col * cell_w)
            x1 = int((col + 1) * cell_w)
            patch = roi[y0:y1, x0:x1]
            bgr = patch.mean(axis=(0, 1))
            cells.append({
                "row":
                row,
                "col":
                col,
                "rgb": [
                    round(float(bgr[2]), 2),
                    round(float(bgr[1]), 2),
                    round(float(bgr[0]), 2)
                ],
            })
    return cells


def main():
    parser = argparse.ArgumentParser(
        description="Sample average cell colors from a heatmap grid.")
    parser.add_argument("image_path")
    parser.add_argument("--plot-area",
                        required=True,
                        help="x,y,w,h for the heatmap body")
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--cols", type=int, required=True)
    args = parser.parse_args()

    img = load_image(args.image_path)
    plot_area = parse_plot_area(args.plot_area)
    cells = sample_grid(img, plot_area, args.rows, args.cols)
    dump_json({
        "chart_type":
        "heatmap",
        "image":
        args.image_path,
        "plot_area":
        plot_area,
        "rows":
        args.rows,
        "cols":
        args.cols,
        "cells":
        cells,
        "notes": [
            "Reference script for evenly spaced heatmap grids.",
            "If you need numeric values, pair this with manual colorbar calibration in the model response or a custom extension.",
        ],
    })


if __name__ == "__main__":
    main()
