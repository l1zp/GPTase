#!/usr/bin/env python3
"""Shared helpers for chart-reader OpenCV reference scripts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


def load_image(path: str):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path}")
    return img


def parse_plot_area(text: str | None):
    if not text:
        return None
    parts = [int(part.strip()) for part in text.split(",")]
    if len(parts) != 4:
        raise ValueError("--plot-area must be x,y,w,h")
    x, y, w, h = parts
    return {"x": x, "y": y, "w": w, "h": h}


def parse_tick_pairs(text: str):
    pairs = []
    for chunk in text.split(","):
        pixel, value = chunk.split(":")
        pairs.append((float(pixel.strip()), float(value.strip())))
    if len(pairs) < 2:
        raise ValueError("Need at least two tick pairs")
    return pairs


def parse_rects(text: str | None):
    if not text:
        return []
    rects = []
    for chunk in text.split(";"):
        parts = [int(part.strip()) for part in chunk.split(",")]
        if len(parts) != 4:
            raise ValueError("--exclude-rects must be x,y,w,h;x,y,w,h")
        x, y, w, h = parts
        rects.append({"x": x, "y": y, "w": w, "h": h})
    return rects


def mask_exclude_rects(roi, rects, fill_value=255):
    if not rects:
        return roi
    masked = roi.copy()
    for rect in rects:
        x0 = max(0, rect["x"])
        y0 = max(0, rect["y"])
        x1 = min(masked.shape[1], rect["x"] + rect["w"])
        y1 = min(masked.shape[0], rect["y"] + rect["h"])
        if x1 <= x0 or y1 <= y0:
            continue
        if masked.ndim == 2:
            masked[y0:y1, x0:x1] = fill_value
        else:
            masked[y0:y1, x0:x1] = (fill_value, fill_value, fill_value)
    return masked


def expand_rect(rect, pad_x, pad_y, bounds):
    x0 = max(0, rect["x"] - pad_x)
    y0 = max(0, rect["y"] - pad_y)
    x1 = min(bounds[0], rect["x"] + rect["w"] + pad_x)
    y1 = min(bounds[1], rect["y"] + rect["h"] + pad_y)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def merge_overlapping_rects(rects, gap=8):
    if not rects:
        return []
    merged = []
    for rect in sorted(rects, key=lambda item: (item["x"], item["y"])):
        current = rect.copy()
        changed = True
        while changed:
            changed = False
            next_merged = []
            for other in merged:
                if (current["x"] <= other["x"] + other["w"] + gap
                        and other["x"] <= current["x"] + current["w"] + gap
                        and current["y"] <= other["y"] + other["h"] + gap
                        and other["y"] <= current["y"] + current["h"] + gap):
                    x0 = min(current["x"], other["x"])
                    y0 = min(current["y"], other["y"])
                    x1 = max(current["x"] + current["w"], other["x"] + other["w"])
                    y1 = max(current["y"] + current["h"], other["y"] + other["h"])
                    current = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
                    changed = True
                else:
                    next_merged.append(other)
            merged = next_merged
        merged.append(current)
    return merged


def detect_text_annotation_rects(roi, threshold=160):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = roi.shape[:2]
    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 3 or area > 120:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if x < width * 0.2 or y < height * 0.5:
            continue
        perimeter = cv2.arcLength(cnt, True)
        circularity = 0.0 if perimeter == 0 else (4 * math.pi * area) / (perimeter
                                                                         * perimeter)
        aspect_ratio = w / max(h, 1)
        if not (circularity < 0.35 or aspect_ratio > 1.4 or aspect_ratio < 0.75):
            continue
        candidates.append({"x": x, "y": y, "w": w, "h": h})

    if len(candidates) < 8:
        return []

    xs = [rect["x"] for rect in candidates]
    ys = [rect["y"] for rect in candidates]
    x2 = [rect["x"] + rect["w"] for rect in candidates]
    y2 = [rect["y"] + rect["h"] for rect in candidates]
    union = {
        "x": min(xs),
        "y": min(ys),
        "w": max(x2) - min(xs),
        "h": max(y2) - min(ys),
    }
    if union["w"] < width * 0.22 or union["h"] < height * 0.08:
        return []

    padded = expand_rect(union, pad_x=14, pad_y=12, bounds=(width, height))
    return merge_overlapping_rects([padded], gap=8)


def detect_plot_area_from_axes(img_gray):
    edges = cv2.Canny(img_gray, 30, 120)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=img_gray.shape[1] * 0.25,
        maxLineGap=15,
    )
    if lines is None:
        return None

    height, width = img_gray.shape
    normalized = []
    for raw in lines[:, 0]:
        x1, y1, x2, y2 = [int(value) for value in raw]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        length = float(np.hypot(x2 - x1, y2 - y1))
        if dx < 8:
            normalized.append({
                "kind": "v",
                "x": int(round((x1 + x2) / 2)),
                "top": min(y1, y2),
                "bottom": max(y1, y2),
                "length": length,
            })
        elif dy < 8:
            normalized.append({
                "kind": "h",
                "y": int(round((y1 + y2) / 2)),
                "left": min(x1, x2),
                "right": max(x1, x2),
                "length": length,
            })

    v_lines = [
        line for line in normalized if line["kind"] == "v" and line["x"] < width
        * 0.35 and line["bottom"] > height * 0.7 and line["length"] > height * 0.35
    ]
    h_lines = [
        line for line in normalized if line["kind"] == "h" and line["y"] > height
        * 0.7 and line["left"] < width * 0.4 and line["length"] > width * 0.35
    ]
    if not h_lines or not v_lines:
        return None

    v_lines.sort(key=lambda line: (-line["length"], line["x"]))
    h_lines.sort(key=lambda line: (-line["length"], -line["y"]))

    best_v = v_lines[0]
    best_h = h_lines[0]
    plot_left = best_v["x"]
    plot_top = best_v["top"]
    plot_bottom = best_h["y"]
    plot_right = best_h["right"]
    if plot_right <= plot_left or plot_bottom <= plot_top:
        return None
    return {
        "x": int(plot_left),
        "y": int(plot_top),
        "w": int(plot_right - plot_left),
        "h": int(plot_bottom - plot_top),
    }


def build_axis_transform(tick_pairs, log_scale=False):
    pixels = np.array([pair[0] for pair in tick_pairs], dtype=float)
    values = np.array([pair[1] for pair in tick_pairs], dtype=float)
    if log_scale:
        coeffs = np.polyfit(pixels, np.log10(values), 1)
        return lambda px: float(10**np.polyval(coeffs, px))
    coeffs = np.polyfit(pixels, values, 1)
    return lambda px: float(np.polyval(coeffs, px))


def crop_roi(img, plot_area):
    x0, y0, w, h = plot_area["x"], plot_area["y"], plot_area["w"], plot_area["h"]
    return img[y0:y0 + h, x0:x0 + w]


def resolve_plot_area(img, explicit_plot_area=None):
    if explicit_plot_area:
        return explicit_plot_area
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return detect_plot_area_from_axes(gray)


def write_debug_image(img, output_path: str, overlays: Iterable[tuple]):
    debug = img.copy()
    for kind, payload in overlays:
        if kind == "rect":
            x, y, w, h, color = payload
            cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)
        elif kind == "circle":
            x, y, r, color = payload
            cv2.circle(debug, (x, y), r, color, -1)
        elif kind == "line":
            x1, y1, x2, y2, color = payload
            cv2.line(debug, (x1, y1), (x2, y2), color, 2)
    cv2.imwrite(output_path, debug)


def dump_json(payload):
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def ensure_parent(path: str | None):
    if not path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
