# analysis/solar_estimation.py
DEFAULT_ASSUMPTIONS = {
    "panel_area_m2": 1.7,
    "panel_wattage_w": 400,
    "roof_utilization": 0.75,
    "performance_ratio": 0.8,
    "annual_sun_hours": 1500,
    "dc_ac_ratio": 1.1,
    "cost_per_watt": 0.9,
    "tariff_rate": 0.15,
    "maintenance_rate": 0.01,
    "degradation_rate": 0.005,
    "discount_rate": 0.06,
}


def estimate_system(usable_area_m2: float, assumptions: dict | None = None) -> dict:
    params = DEFAULT_ASSUMPTIONS.copy()
    if assumptions:
        params.update(assumptions)

    panel_area_m2 = params["panel_area_m2"]
    panel_wattage_w = params["panel_wattage_w"]
    performance_ratio = params["performance_ratio"]
    annual_sun_hours = params["annual_sun_hours"]
    dc_ac_ratio = params["dc_ac_ratio"]

    panel_count = max(int(usable_area_m2 // panel_area_m2), 0)
    dc_kw = (panel_count * panel_wattage_w) / 1000
    ac_kw = dc_kw / dc_ac_ratio if dc_ac_ratio else dc_kw
    annual_kwh = ac_kw * annual_sun_hours * performance_ratio

    return {
        "panel_count": panel_count,
        "dc_kw": dc_kw,
        "ac_kw": ac_kw,
        "annual_kwh": annual_kwh,
    }
