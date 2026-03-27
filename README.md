# SolarScope Rooftop Analyzer

SolarScope is a lightweight, resume-ready solar rooftop analysis tool. Users can log in, create projects, and analyze rooftop potential using image upload, address lookup, manual area input, or map drawing.

## Features
- Login/register dashboard with saved projects
- Image upload with segmentation and confidence score
- Address-based analysis using OpenStreetMap footprints
- Map draw tool to trace roof polygons
- Manual area mode for quick estimates
- PDF report export
- Optional TorchScript model support

## Quick Start
1) Install dependencies:

```bash
pip install -r requirements.txt
```

2) Run the app:

```bash
uvicorn app.main:app --reload
```

3) Open `http://localhost:8000` in your browser.

## Segmentation Model (Optional)
Set an environment variable to use a TorchScript model:

```bash
set SOLAR_MODEL_PATH=C:\path\to\model.pt
```

If not set, SolarScope uses the heuristic pipeline.

## Project Structure
- app/: FastAPI web app, templates, and static assets
- analysis/: core analysis, segmentation, and ROI logic
- data/: SQLite database and uploaded assets (created at runtime)

## Notes
- Address-based analysis depends on OpenStreetMap data. Some areas may not have footprints.
- Draw mode uses Leaflet and OpenStreetMap tiles.
