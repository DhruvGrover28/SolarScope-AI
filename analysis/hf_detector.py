from __future__ import annotations

import os
from io import BytesIO
from typing import Any

import requests
from PIL import Image

HF_API_BASE = "https://api-inference.huggingface.co/models"
DEFAULT_MODEL = "Yifeng-Liu/rt-detr-finetuned-for-satellite-image-roofs-detection"


def detect_roof_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    token = os.getenv("HF_TOKEN")
    model_id = os.getenv("HF_DETECT_MODEL", DEFAULT_MODEL)
    if not token:
        return None

    url = f"{HF_API_BASE}/{model_id}"
    headers = {"Authorization": f"Bearer {token}"}
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = requests.post(url, headers=headers, data=buffer.getvalue(), timeout=30)
    response.raise_for_status()
    data: Any = response.json()
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
