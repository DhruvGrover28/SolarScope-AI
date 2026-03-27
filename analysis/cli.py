from __future__ import annotations

import argparse
from pathlib import Path

from analysis.image_segmentation import segment_rooftop
from analysis.roi_calculator import calculate_roi
from analysis.solar_estimation import DEFAULT_ASSUMPTIONS, estimate_system


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a quick rooftop analysis.")
    parser.add_argument("image", help="Path to a rooftop image")
    parser.add_argument("--roof-width", type=float, default=None)
    args = parser.parse_args()

    image_path = Path(args.image)
    mask, usable_area_m2, confidence = segment_rooftop(
        str(image_path), roof_width_m=args.roof_width
    )
    system = estimate_system(usable_area_m2, DEFAULT_ASSUMPTIONS)
    roi = calculate_roi(system, DEFAULT_ASSUMPTIONS)

    print(f"Usable area: {usable_area_m2:.2f} m2")
    print(f"System size: {system['dc_kw']:.2f} kW")
    print(f"Annual kWh: {system['annual_kwh']:.0f}")
    print(f"Payback years: {roi['payback_years']:.1f}")
    print(f"Confidence: {confidence:.2f}")

    mask_output = image_path.with_suffix(".mask.png")
    mask.save(mask_output)
    print(f"Saved mask to {mask_output}")


if __name__ == "__main__":
    main()
