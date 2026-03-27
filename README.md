# SolarScope Rooftop Analyzer

SolarScope is a lightweight, resume-ready solar rooftop analysis tool. Users can log in, create projects, and analyze rooftop potential using image upload, address lookup, manual area input, or map drawing.

## Live Website
https://solarscope-ai.onrender.com/

## Features
- Login/register dashboard with saved projects
- Image upload with segmentation and confidence score
- Address-based analysis using OpenStreetMap footprints
- Map draw tool to trace roof polygons
- Manual area mode for quick estimates
- PDF report export
- Optional TorchScript model support

## Example Use Case
**Input Image**

![Example Input Image](example3.jpg)

**Output Results**

![Example Output Result](Result_project.png)

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

## Roof Detection via Hugging Face (Optional)
For improved roof detection, you can enable a roof detector model on Hugging Face.

Set env vars:

```bash
set HF_TOKEN=your_huggingface_token
set HF_DETECT_MODEL=Yifeng-Liu/rt-detr-finetuned-for-satellite-image-roofs-detection
```

This will detect a roof bounding box, crop it, then refine the mask inside the box.
The detector request automatically resizes large images and retries on transient API failures.

## Project Structure
- app/: FastAPI web app, templates, and static assets
- analysis/: core analysis, segmentation, and ROI logic
- data/: SQLite database and uploaded assets (created at runtime)

## Notes
- Address-based analysis depends on OpenStreetMap data. Some areas may not have footprints.
- Draw mode uses Leaflet and OpenStreetMap tiles.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
