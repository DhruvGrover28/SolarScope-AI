from __future__ import annotations

from pathlib import Path

from fpdf import FPDF


def build_project_report(project, output_path: Path, data_dir: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "SolarScope Rooftop Report", ln=True)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Project: {project.name}", ln=True)
    if project.address:
        pdf.cell(0, 8, f"Address: {project.address}", ln=True)
    pdf.cell(0, 8, f"Method: {project.method}", ln=True)
    pdf.ln(4)

    _section_title(pdf, "System Summary")
    _key_value(pdf, "Usable area (m2)", f"{project.usable_area_m2:.1f}")
    _key_value(pdf, "Panel count", str(project.panel_count))
    _key_value(pdf, "System size (kW)", f"{project.power_kw:.1f}")
    _key_value(pdf, "Annual kWh", f"{project.annual_kwh:.0f}")
    _key_value(pdf, "Confidence", f"{project.confidence * 100:.0f}%")
    pdf.ln(4)

    _section_title(pdf, "Financials")
    _key_value(pdf, "Installation cost", f"{project.installation_cost:,.0f}")
    _key_value(pdf, "Annual savings", f"{project.annual_savings:,.0f}")
    _key_value(pdf, "Payback years", f"{project.payback_years:.1f}")
    _key_value(pdf, "25-year savings", f"{project.total_savings_25yrs:,.0f}")

    assumptions = project.assumptions or {}
    if assumptions:
        pdf.ln(4)
        _section_title(pdf, "Assumptions")
        for key, value in assumptions.items():
            _key_value(pdf, key.replace("_", " "), str(value))

    if project.image_path:
        image_path = data_dir / project.image_path
        if image_path.exists():
            pdf.ln(4)
            _section_title(pdf, "Uploaded Image")
            pdf.image(str(image_path), w=170)

    if project.mask_path:
        mask_path = data_dir / project.mask_path
        if mask_path.exists():
            pdf.ln(4)
            _section_title(pdf, "Segmentation Mask")
            pdf.image(str(mask_path), w=170)

    overlay_path = None
    if project.source_data:
        overlay_path = project.source_data.get("panel_overlay_path")
    if overlay_path:
        overlay_file = data_dir / overlay_path
        if overlay_file.exists():
            pdf.ln(4)
            _section_title(pdf, "Panel Layout Overlay")
            pdf.image(str(overlay_file), w=170)

    pdf.output(str(output_path))


def _section_title(pdf: FPDF, title: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, title, ln=True)
    pdf.set_font("Helvetica", "", 11)


def _key_value(pdf: FPDF, key: str, value: str) -> None:
    pdf.cell(60, 7, key)
    pdf.cell(0, 7, value, ln=True)