# analysis/image_segmentation.py
from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from analysis.hf_detector import detect_roof_bbox
try:
    import torch
except ImportError:  # Optional dependency
    torch = None

try:
    from segment_anything import SamAutomaticMaskGenerator, sam_model_registry
except ImportError:  # Optional dependency
    SamAutomaticMaskGenerator = None
    sam_model_registry = None

DEFAULT_GSD_M = 0.25


def segment_rooftop(
    image_input: Image.Image | str | "Path",
    gsd_meters_per_pixel: float | None = None,
    roof_width_m: float | None = None,
    use_model: bool = True,
):
    image = _load_image(image_input)
    model_mask = _try_model_segmentation(image) if use_model else None
    if model_mask is not None:
        usable_area_m2, confidence = _area_and_confidence_from_mask(
            model_mask,
            image,
            gsd_meters_per_pixel,
            roof_width_m,
        )
        return model_mask, usable_area_m2, confidence

    try:
        bbox = detect_roof_bbox(image)
    except Exception:
        bbox = None
    if bbox:
        cropped = image.crop(bbox)
        mask_np, _ = _heuristic_mask(cropped)
        full_mask = np.zeros((image.size[1], image.size[0]), dtype="uint8")
        x1, y1, x2, y2 = bbox
        full_mask[y1:y2, x1:x2] = mask_np
        mask_img = Image.fromarray(full_mask).convert("RGB")
        usable_area_m2, confidence = _area_and_confidence_from_mask(
            mask_img,
            image,
            gsd_meters_per_pixel,
            roof_width_m,
        )
        return mask_img, usable_area_m2, confidence

    mask_np, confidence = _heuristic_mask(image)
    mask_img = Image.fromarray(mask_np).convert("RGB")
    usable_area_m2, _ = _area_and_confidence_from_mask(
        mask_img,
        image,
        gsd_meters_per_pixel,
        roof_width_m,
    )
    return mask_img, usable_area_m2, confidence


def _heuristic_mask(image: Image.Image) -> tuple[np.ndarray, float]:
    img_np = np.array(image.convert("RGB"))
    original_height, original_width, _ = img_np.shape

    processed_size = (640, 640)
    img_resized = cv2.resize(img_np, processed_size, interpolation=cv2.INTER_AREA)

    hsv_img = cv2.cvtColor(img_resized, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(img_resized, cv2.COLOR_RGB2GRAY)

    sat = hsv_img[:, :, 1]
    val = hsv_img[:, :, 2]
    mask_color = cv2.inRange(sat, 0, 80)
    mask_bright = cv2.inRange(val, 60, 210)
    color_candidate = cv2.bitwise_and(mask_color, mask_bright)

    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        21,
        7,
    )

    mask = cv2.bitwise_or(color_candidate, adaptive)
    mask = cv2.medianBlur(mask, 5)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    mask = _refine_with_grabcut(img_resized, mask)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    largest_cc_mask = np.zeros_like(mask)

    if num_labels > 1:
        largest_label_idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        largest_cc_mask[labels == largest_label_idx] = 255

    resized_mask = cv2.resize(
        largest_cc_mask, (original_width, original_height), interpolation=cv2.INTER_NEAREST
    )

    confidence = _estimate_confidence(resized_mask, has_scale=False)
    return resized_mask, confidence


def _load_image(image_input: Image.Image | str | "Path") -> Image.Image:
    if isinstance(image_input, Image.Image):
        return image_input
    return Image.open(str(image_input))


def _derive_scale_m_per_px(
    gsd_meters_per_pixel: float | None,
    roof_width_m: float | None,
    image_width_px: int,
) -> float:
    if gsd_meters_per_pixel:
        return gsd_meters_per_pixel
    if roof_width_m and image_width_px > 0:
        return roof_width_m / image_width_px
    return DEFAULT_GSD_M


def _refine_with_grabcut(img_resized: np.ndarray, mask: np.ndarray) -> np.ndarray:
    grabcut_mask = np.where(mask > 0, cv2.GC_PR_FGD, cv2.GC_BGD).astype("uint8")
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(
        img_resized,
        grabcut_mask,
        None,
        bgd_model,
        fgd_model,
        3,
        cv2.GC_INIT_WITH_MASK,
    )
    refined = np.where(
        (grabcut_mask == cv2.GC_FGD) | (grabcut_mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype("uint8")
    return refined


def _estimate_confidence(mask: np.ndarray, has_scale: bool) -> float:
    total_mask_pixels = np.sum(mask == 255)
    if total_mask_pixels == 0:
        return 0.0

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return 0.0
    largest_label_idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    largest_cc_pixels = np.sum(labels == largest_label_idx)

    connected_component_ratio = largest_cc_pixels / total_mask_pixels
    edges = cv2.Canny(mask, 40, 120)
    edge_pixel_count = np.sum(edges > 0)
    ideal_perimeter_approx = 4 * np.sqrt(max(largest_cc_pixels, 1))
    edge_quality_score = min(edge_pixel_count / ideal_perimeter_approx, 1.0)
    scale_confidence = 1.0 if has_scale else 0.6

    confidence = (
        (connected_component_ratio * 0.5)
        + (edge_quality_score * 0.3)
        + (scale_confidence * 0.2)
    )
    return float(np.clip(confidence, 0.0, 1.0))


def _try_model_segmentation(image: Image.Image) -> Image.Image | None:
    sam_mask = _try_sam_segmentation(image)
    if sam_mask is not None:
        return sam_mask

    model_path = os.getenv("SOLAR_MODEL_PATH")
    if not model_path or torch is None:
        return None

    model_path = os.path.expanduser(model_path)
    if not os.path.exists(model_path):
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = torch.jit.load(model_path, map_location=device)
    model.eval()

    img = image.convert("RGB").resize((512, 512))
    img_tensor = torch.from_numpy(np.array(img)).permute(2, 0, 1).float() / 255.0
    img_tensor = img_tensor.unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(img_tensor)
    if isinstance(output, (list, tuple)):
        output = output[0]
    mask = output.squeeze().detach().cpu().numpy()
    if mask.ndim == 3:
        mask = mask[0]
    mask = 1 / (1 + np.exp(-mask))
    mask = (mask > 0.5).astype("uint8") * 255
    mask_img = Image.fromarray(mask).resize(image.size)
    return mask_img.convert("RGB")


def _try_sam_segmentation(image: Image.Image) -> Image.Image | None:
    checkpoint_path = os.getenv("SAM_CHECKPOINT_PATH")
    model_type = os.getenv("SAM_MODEL_TYPE", "vit_b")
    if not checkpoint_path or torch is None:
        return None
    if sam_model_registry is None or SamAutomaticMaskGenerator is None:
        return None

    checkpoint_path = os.path.expanduser(checkpoint_path)
    if not os.path.exists(checkpoint_path):
        return None

    if model_type not in sam_model_registry:
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam = sam_model_registry[model_type](checkpoint=checkpoint_path)
    sam.to(device=device)
    generator = SamAutomaticMaskGenerator(sam)

    img_np = np.array(image.convert("RGB"))
    masks = generator.generate(img_np)
    if not masks:
        return None

    best_mask = max(masks, key=lambda item: item.get("area", 0))
    mask = best_mask["segmentation"].astype("uint8") * 255
    mask_img = Image.fromarray(mask)
    return mask_img.convert("RGB")


def _area_and_confidence_from_mask(
    mask_img: Image.Image,
    image: Image.Image,
    gsd_meters_per_pixel: float | None,
    roof_width_m: float | None,
) -> tuple[float, float]:
    mask_np = np.array(mask_img.convert("L"))
    mask_np = (mask_np > 0).astype("uint8") * 255
    scale_m_per_px = _derive_scale_m_per_px(
        gsd_meters_per_pixel, roof_width_m, image.size[0]
    )
    pixel_area_m2 = scale_m_per_px * scale_m_per_px
    usable_area_m2 = np.sum(mask_np == 255) * pixel_area_m2
    confidence = _estimate_confidence(mask_np, gsd_meters_per_pixel is not None)
    return usable_area_m2, confidence