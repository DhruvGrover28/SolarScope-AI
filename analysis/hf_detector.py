from __future__ import annotations

import os
from io import BytesIO
from time import sleep
from typing import Any

import requests
from PIL import Image

HF_API_BASE = "https://api-inference.huggingface.co/models"
DEFAULT_MODEL = "Yifeng-Liu/rt-detr-finetuned-for-satellite-image-roofs-detection"
MAX_IMAGE_EDGE = 1024
RETRY_COUNT = 2


def detect_roof_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    token = os.getenv("HF_TOKEN")
    model_id = os.getenv("HF_DETECT_MODEL", DEFAULT_MODEL)
    if not token:
        return None

    url = f"{HF_API_BASE}/{model_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = _encode_image(_resize_image(image))

    data = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            break
        except requests.RequestException:
            if attempt >= RETRY_COUNT:
                return None
            sleep(1.5 * (attempt + 1))
    if isinstance(data, dict) and data.get("error"):
        return None

    if not isinstance(data, list):
        return None

    best = None
    for item in data:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).lower()
        score = float(item.get("score", 0))
        box = item.get("box") or {}
        if "roof" not in label and "building" not in label:
            continue
        if not all(key in box for key in ("xmin", "ymin", "xmax", "ymax")):
            continue
        if best is None or score > best[0]:
            best = (score, box)

    if best is None:
        return None

    _, box = best
    return (int(box["xmin"]), int(box["ymin"]), int(box["xmax"]), int(box["ymax"]))


def _resize_image(image: Image.Image) -> Image.Image:
    width, height = image.size
    max_edge = max(width, height)
    if max_edge <= MAX_IMAGE_EDGE:
        return image
    scale = MAX_IMAGE_EDGE / max_edge
    new_size = (int(width * scale), int(height * scale))
    return image.resize(new_size)


def _encode_image(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
