# analysis/roi_calculator.py
def calculate_roi(system: dict, assumptions: dict) -> dict:
    dc_kw = system["dc_kw"]
    annual_kwh = system["annual_kwh"]

    cost_per_watt = assumptions["cost_per_watt"]
    tariff_rate = assumptions["tariff_rate"]
    maintenance_rate = assumptions["maintenance_rate"]
    degradation_rate = assumptions["degradation_rate"]

    installation_cost = dc_kw * 1000 * cost_per_watt
    annual_savings = annual_kwh * tariff_rate
    annual_maintenance = installation_cost * maintenance_rate
    annual_net = max(annual_savings - annual_maintenance, 0)

    payback_years = installation_cost / annual_net if annual_net else 0
    total_savings_25yrs = 0.0
    for year in range(25):
        total_savings_25yrs += annual_net * ((1 - degradation_rate) ** year)

    return {
        "installation_cost": float(installation_cost),
        "annual_savings": float(annual_net),
        "payback_years": float(payback_years),
        "total_savings_25yrs": float(total_savings_25yrs),
    }