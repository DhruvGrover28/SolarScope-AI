from __future__ import annotations

from math import cos, radians, sqrt
from typing import Any

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
EARTH_RADIUS_M = 6371000.0


def fetch_building_footprint(lat: float, lon: float, radius_m: int = 60) -> dict[str, Any] | None:
    query = f"""
    [out:json];
    (
      way(around:{radius_m},{lat},{lon})["building"];
      relation(around:{radius_m},{lat},{lon})["building"];
    );
    out geom;
    """
    response = requests.post(OVERPASS_URL, data=query, timeout=20)
    response.raise_for_status()
    data = response.json()
    elements = data.get("elements", [])
    if not elements:
        return None

    candidates = []
    for element in elements:
        geometry = element.get("geometry")
        if not geometry:
            continue
        coords = [(point["lat"], point["lon"]) for point in geometry]
        center = _centroid(coords)
        distance = _distance_m(lat, lon, center[0], center[1])
        candidates.append((distance, coords))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    chosen = candidates[0][1]

    area_m2 = polygon_area_m2(chosen)
    return {
        "coords": chosen,
        "area_m2": area_m2,
    }


def polygon_area_m2(coords: list[tuple[float, float]]) -> float:
    if len(coords) < 3:
        return 0.0

    lat0 = radians(sum(lat for lat, _ in coords) / len(coords))
    projected = [
        (
            radians(lon) * EARTH_RADIUS_M * cos(lat0),
            radians(lat) * EARTH_RADIUS_M,
        )
        for lat, lon in coords
    ]

    area = 0.0
    for i in range(len(projected)):
        x1, y1 = projected[i]
        x2, y2 = projected[(i + 1) % len(projected)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _centroid(coords: list[tuple[float, float]]) -> tuple[float, float]:
    lat = sum(point[0] for point in coords) / len(coords)
    lon = sum(point[1] for point in coords) / len(coords)
    return lat, lon


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dx = radians(lon2 - lon1) * EARTH_RADIUS_M * cos(radians((lat1 + lat2) / 2))
    dy = radians(lat2 - lat1) * EARTH_RADIUS_M
    return sqrt(dx * dx + dy * dy)
