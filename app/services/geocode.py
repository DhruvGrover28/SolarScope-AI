from __future__ import annotations

from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_address(address: str) -> dict[str, Any] | None:
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "solar-rooftop-analysis/1.0"}
    response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    results = response.json()
    if not results:
        return None

    result = results[0]
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result.get("display_name", address),
    }
