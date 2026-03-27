from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np
from PIL import Image

DEFAULT_PANEL_W_M = 1.7
DEFAULT_PANEL_H_M = 1.0
DEFAULT_PANEL_GAP_M = 0.02
DEFAULT_SETBACK_M = 0.2
DEFAULT_GSD_M = 0.25


@dataclass
class PanelLayoutResult:
    panel_count: int
    usable_area_m2: float
    panel_area_m2: float
    coverage_ratio: float
    overlay: Image.Image | None
    panel_boxes: list[tuple[int, int, int, int]]


def build_panel_layout(
    image: Image.Image,
    mask_img: Image.Image,
    roof_width_m: float | None,
    gsd_meters_per_pixel: float | None,
    panel_w_m: float = DEFAULT_PANEL_W_M,
    panel_h_m: float = DEFAULT_PANEL_H_M,
    panel_gap_m: float = DEFAULT_PANEL_GAP_M,
    setback_m: float = DEFAULT_SETBACK_M,
) -> PanelLayoutResult:
    mask = np.array(mask_img.convert("L"))
    mask = (mask > 0).astype("uint8") * 255

    scale_m_per_px = _derive_scale_m_per_px(roof_width_m, gsd_meters_per_pixel, mask)
    cleaned_mask = _clean_mask(mask, setback_m, scale_m_per_px)
    usable_area_m2 = np.sum(cleaned_mask == 255) * (scale_m_per_px**2)

    panel_boxes = _place_panels(
        cleaned_mask,
        scale_m_per_px,
        panel_w_m,
        panel_h_m,
        panel_gap_m,
    )

    panel_area_m2 = panel_w_m * panel_h_m * len(panel_boxes)
    coverage_ratio = panel_area_m2 / usable_area_m2 if usable_area_m2 else 0.0
    overlay = _render_overlay(image, cleaned_mask, panel_boxes)

    return PanelLayoutResult(
        panel_count=len(panel_boxes),
        usable_area_m2=usable_area_m2,
        panel_area_m2=panel_area_m2,
        coverage_ratio=coverage_ratio,
        overlay=overlay,
        panel_boxes=panel_boxes,
    )


def _derive_scale_m_per_px(
    roof_width_m: float | None,
    gsd_meters_per_pixel: float | None,
    mask: np.ndarray,
) -> float:
    if gsd_meters_per_pixel:
        return gsd_meters_per_pixel
    if roof_width_m:
        return max(roof_width_m / max(mask.shape[1], 1), 0.01)
    return DEFAULT_GSD_M


def _clean_mask(mask: np.ndarray, setback_m: float, scale_m_per_px: float) -> np.ndarray:
    kernel = np.ones((5, 5), np.uint8)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    if num_labels > 1:
        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        cleaned = np.where(labels == largest_label, 255, 0).astype("uint8")

    setback_px = max(int(setback_m / max(scale_m_per_px, 1e-4)), 1)
    setback_kernel = np.ones((setback_px, setback_px), np.uint8)
    cleaned = cv2.erode(cleaned, setback_kernel, iterations=1)
    return cleaned


def _place_panels(
    mask: np.ndarray,
    scale_m_per_px: float,
    panel_w_m: float,
    panel_h_m: float,
    panel_gap_m: float,
) -> list[tuple[int, int, int, int]]:
    panel_w_px = max(int(panel_w_m / scale_m_per_px), 1)
    panel_h_px = max(int(panel_h_m / scale_m_per_px), 1)
    gap_px = max(int(panel_gap_m / scale_m_per_px), 0)

    integral = cv2.integral((mask > 0).astype("uint8"))
    boxes: list[tuple[int, int, int, int]] = []

    height, width = mask.shape
    y = 0
    while y + panel_h_px < height:
        x = 0
        while x + panel_w_px < width:
            if _rect_filled(integral, x, y, panel_w_px, panel_h_px):
                boxes.append((x, y, panel_w_px, panel_h_px))
                x += panel_w_px + gap_px
            else:
                x += max(panel_w_px // 3, 1)
        y += panel_h_px + gap_px

    return boxes


def _rect_filled(integral: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
    x2 = x + w
    y2 = y + h
    total = integral[y2, x2] - integral[y, x2] - integral[y2, x] + integral[y, x]
    return total >= w * h


def _render_overlay(
    image: Image.Image,
    mask: np.ndarray,
    boxes: Iterable[tuple[int, int, int, int]],
) -> Image.Image:
    base = np.array(image.convert("RGB"))
    overlay = base.copy()
    overlay[mask > 0] = (overlay[mask > 0] * 0.4 + np.array([40, 180, 90]) * 0.6).astype(
        "uint8"
    )

    for x, y, w, h in boxes:
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (255, 215, 0), 2)

    blended = cv2.addWeighted(base, 0.55, overlay, 0.45, 0)
    return Image.fromarray(blended)
