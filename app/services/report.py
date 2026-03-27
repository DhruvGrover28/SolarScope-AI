from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

PRIMARY = (15, 76, 92)
ACCENT = (244, 184, 96)
INK = (29, 29, 31)
MUTED = (110, 110, 115)
ROW_FILL = (246, 250, 251)


def build_project_report(
    project, output_path: Path, data_dir: Path, user_name: str | None = None
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(12, 20, 12)
    pdf.add_page()

    _draw_header(pdf, project, user_name)
    _draw_summary(pdf, project)
    _draw_financials(pdf, project)
    _draw_assumptions(pdf, project)
    _draw_images(pdf, project, data_dir)

    pdf.output(str(output_path))


def _draw_header(pdf: FPDF, project, user_name: str | None) -> None:
    pdf.set_fill_color(*PRIMARY)
    pdf.rect(0, 0, 210, 26, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(12, 8)
    pdf.cell(0, 8, "SolarScope Rooftop Report")

    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(12, 30)
    pdf.cell(0, 7, f"Project: {project.name}", ln=True)
    if project.address:
        pdf.set_x(12)
        pdf.multi_cell(0, 6, f"Address: {project.address}")
    pdf.set_x(12)
    pdf.cell(0, 6, f"Method: {project.method}")
    pdf.ln(2)
    pdf.set_x(12)
    pdf.set_text_color(*MUTED)
    if user_name:
        pdf.cell(0, 6, f"Prepared for: {user_name}")
        pdf.ln(6)
        pdf.set_x(12)
    pdf.cell(0, 6, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    pdf.ln(8)
    pdf.set_text_color(*INK)


def _draw_summary(pdf: FPDF, project) -> None:
    _section_title(pdf, "System Summary")
    rows = [
        ("Usable area (m2)", f"{project.usable_area_m2:.1f}"),
        ("Panel count", str(project.panel_count)),
        ("System size (kW)", f"{project.power_kw:.1f}"),
        ("Annual kWh", f"{project.annual_kwh:.0f}"),
        ("Confidence", f"{project.confidence * 100:.0f}%"),
    ]
    _key_value_table(pdf, rows)
    pdf.ln(4)


def _draw_financials(pdf: FPDF, project) -> None:
    _section_title(pdf, "Financial Overview")
    currency = "USD"
    if project.source_data:
        currency = project.source_data.get("currency", currency)
    rows = [
        ("Installation cost", _format_currency(project.installation_cost, currency)),
        ("Annual savings", _format_currency(project.annual_savings, currency)),
        ("Payback years", f"{project.payback_years:.1f}"),
        ("25-year savings", _format_currency(project.total_savings_25yrs, currency)),
    ]
    _key_value_table(pdf, rows)
    pdf.ln(4)


def _draw_assumptions(pdf: FPDF, project) -> None:
    assumptions = project.assumptions or {}
    if not assumptions:
        return
    highlights = [
        ("Panel wattage (W)", assumptions.get("panel_wattage_w")),
        ("Panel area (m2)", assumptions.get("panel_area_m2")),
        ("Roof utilization", assumptions.get("roof_utilization")),
        ("Performance ratio", assumptions.get("performance_ratio")),
        ("Annual sun hours", assumptions.get("annual_sun_hours")),
        ("Cost per watt", assumptions.get("cost_per_watt")),
        ("Tariff rate", assumptions.get("tariff_rate")),
    ]
    rows = [(label, str(value)) for label, value in highlights if value is not None]
    if rows:
        _section_title(pdf, "Assumptions Snapshot")
        _key_value_table(pdf, rows)
        pdf.ln(4)


def _draw_images(pdf: FPDF, project, data_dir: Path) -> None:
    image_blocks = []
    if project.image_path:
        image_blocks.append(("Uploaded Image", data_dir / project.image_path))
    if project.mask_path:
        image_blocks.append(("Segmentation Mask", data_dir / project.mask_path))
    overlay_path = None
    if project.source_data:
        overlay_path = project.source_data.get("panel_overlay_path")
    if overlay_path:
        image_blocks.append(("Panel Layout Overlay", data_dir / overlay_path))

    for title, path in image_blocks:
        if not path.exists():
            continue
        _section_title(pdf, title)
        pdf.image(str(path), w=170)
        pdf.ln(6)


def _section_title(pdf: FPDF, title: str) -> None:
    pdf.set_fill_color(*ACCENT)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, title, ln=True, fill=True)
    pdf.set_font("Helvetica", "", 11)


def _key_value_table(pdf: FPDF, rows: list[tuple[str, str]]) -> None:
    label_width = 60
    value_width = 0
    for index, (key, value) in enumerate(rows):
        if index % 2 == 0:
            pdf.set_fill_color(*ROW_FILL)
            fill = True
        else:
            fill = False
        pdf.cell(label_width, 7, key, fill=fill)
        pdf.cell(value_width, 7, value, ln=True, fill=fill)


def _format_currency(amount: float, code: str) -> str:
    return f"{code} {amount:,.0f}"