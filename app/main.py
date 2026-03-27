from __future__ import annotations

import json
from pathlib import Path
from typing import Generator
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from analysis.image_segmentation import segment_rooftop
from analysis.roi_calculator import calculate_roi
from analysis.panel_layout import build_panel_layout
from analysis.solar_estimation import DEFAULT_ASSUMPTIONS, estimate_system
from app.auth import create_session, hash_password, read_session, verify_password
from app.db import Base, DATA_DIR, SessionLocal, engine, ensure_columns
from app.models import Project, User
from app.services.geocode import geocode_address
from app.services.osm import fetch_building_footprint, polygon_area_m2
from app.services.report import build_project_report

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
REPORT_DIR = DATA_DIR / "reports"
EVAL_DIR = OUTPUT_DIR / "eval"
AVATAR_DIR = DATA_DIR / "avatars"

app = FastAPI(title="Solar Rooftop Analyzer")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_columns(
        engine,
        "users",
        {"name": "TEXT", "preferences": "TEXT", "avatar_path": "TEXT"},
    )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get("session")
    if not token:
        return None
    user_id = read_session(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_preferences(user: User | None) -> dict:
    defaults = {
        "units": "m",
        "currency": "USD",
        "panel_type": "standard",
        "goal": "max_savings",
        "budget": None,
        "sunlight_factor": 1.0,
    }
    if not user or not user.preferences:
        return defaults
    return {**defaults, **user.preferences}


def currency_symbol(code: str) -> str:
    return {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(code, "$")


def list_avatar_urls() -> list[str]:
    avatar_dir = STATIC_DIR / "avatars"
    if not avatar_dir.exists():
        return []
    avatars = sorted(
        [
            f"/static/avatars/{path.name}"
            for path in avatar_dir.iterdir()
            if path.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg"}
        ]
    )
    return avatars


def resolve_user_avatar(user: User | None) -> str | None:
    if user and user.avatar_path:
        return user.avatar_path
    avatars = list_avatar_urls()
    return avatars[0] if avatars else None


def save_avatar_upload(upload: UploadFile, user_id: int) -> str:
    extension = Path(upload.filename or "avatar.png").suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported avatar format")
    file_id = f"avatar_{uuid4().hex}{extension}"
    user_dir = AVATAR_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / file_id
    try:
        upload.file.seek(0)
        image = Image.open(upload.file)
        image = ImageOps.exif_transpose(image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid image file") from exc

    max_size = 512
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size))

    if extension in {".jpg", ".jpeg"}:
        image = image.convert("RGB")

    save_kwargs = {"optimize": True}
    if extension in {".jpg", ".jpeg", ".webp"}:
        save_kwargs["quality"] = 90

    image.save(file_path, **save_kwargs)
    return f"/data/avatars/{user_id}/{file_id}"


def select_avatar_from_choice(choice: str | None, avatars: list[str]) -> str | None:
    if not choice:
        return None
    if choice in avatars:
        return choice
    return None


def pick_sunlight_factor(address: str | None) -> float:
    if not address:
        return 1.0
    text = address.lower()
    if any(key in text for key in ["india", "uae", "saudi", "mexico", "australia"]):
        return 1.2
    if any(key in text for key in ["uk", "germany", "norway", "sweden", "canada"]):
        return 0.85
    return 1.0


def resolve_panel_profile(panel_type: str) -> dict:
    if panel_type == "premium":
        return {"panel_wattage_w": 450, "cost_per_watt": 1.2}
    return {"panel_wattage_w": 400, "cost_per_watt": 0.9}


def require_user(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def fetch_user_projects(db: Session, user_id: int) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.user_id == user_id)
        .order_by(Project.created_at.desc())
        .all()
    )


@app.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_email = email.lower().strip()
    normalized_password = password.strip()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not normalized_password:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Password cannot be empty"},
            status_code=400,
        )
    if not user or not verify_password(normalized_password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Invalid credentials"},
            status_code=400,
        )

    session_token = create_session(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie("session", session_token, httponly=True, samesite="lax")
    return response


@app.get("/register")
def register_page(request: Request):
    avatars = list_avatar_urls()
    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "request": request,
            "avatars": avatars,
            "avatar_url": resolve_user_avatar(None),
        },
    )


@app.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(""),
    avatar_choice: str | None = Form(None),
    avatar_upload: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    normalized_email = email.lower().strip()
    normalized_password = password.strip()
    if db.query(User).filter(User.email == normalized_email).first():
        avatars = list_avatar_urls()
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "error": "Account already exists",
                "avatars": avatars,
                "avatar_url": resolve_user_avatar(None),
            },
            status_code=400,
        )

    avatars = list_avatar_urls()
    avatar_path = select_avatar_from_choice(avatar_choice, avatars)

    user = User(
        email=normalized_email,
        name=name.strip() or None,
        password_hash=hash_password(normalized_password),
        avatar_path=avatar_path,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if avatar_upload and avatar_upload.filename:
        user.avatar_path = save_avatar_upload(avatar_upload, user.id)
        db.add(user)
        db.commit()

    session_token = create_session(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie("session", session_token, httponly=True, samesite="lax")
    return response


@app.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    projects = fetch_user_projects(db, user.id)
    preferences = get_preferences(user)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "projects": projects,
            "assumptions": DEFAULT_ASSUMPTIONS,
            "preferences": preferences,
            "currency_symbol": currency_symbol(preferences["currency"]),
            "user_name": user.name or "there",
            "avatar_url": resolve_user_avatar(user),
        },
    )


@app.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    preferences = get_preferences(user)
    avatars = list_avatar_urls()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "preferences": preferences,
            "user": user,
            "avatars": avatars,
            "avatar_url": resolve_user_avatar(user),
        },
    )


@app.post("/settings")
def update_settings(
    request: Request,
    name: str = Form(""),
    units: str = Form("m"),
    currency: str = Form("USD"),
    panel_type: str = Form("standard"),
    goal: str = Form("max_savings"),
    budget: float | None = Form(None),
    sunlight_factor: float | None = Form(None),
    avatar_choice: str | None = Form(None),
    avatar_upload: UploadFile | None = File(None),
    remove_avatar: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    avatars = list_avatar_urls()
    avatar_path = None
    if avatar_upload and avatar_upload.filename:
        avatar_path = save_avatar_upload(avatar_upload, user.id)
    elif avatar_choice:
        avatar_path = select_avatar_from_choice(avatar_choice, avatars)
    elif remove_avatar:
        avatar_path = None
    prefs = get_preferences(user)
    prefs.update(
        {
            "units": units,
            "currency": currency,
            "panel_type": panel_type,
            "goal": goal,
            "budget": budget,
            "sunlight_factor": sunlight_factor or prefs["sunlight_factor"],
        }
    )
    user.name = name.strip() or user.name
    user.preferences = prefs
    if avatar_path is not None:
        user.avatar_path = avatar_path
    db.add(user)
    db.commit()
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/projects/upload")
def create_project_from_upload(
    request: Request,
    name: str = Form(...),
    roof_width_m: float | None = Form(None),
    panel_wattage: int | None = Form(None),
    cost_per_watt: float | None = Form(None),
    tariff_rate: float | None = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    preferences = get_preferences(user)
    profile = resolve_panel_profile(preferences["panel_type"])

    extension = Path(image.filename or "upload.jpg").suffix
    file_id = f"{uuid4().hex}{extension}"
    user_dir = UPLOAD_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / file_id
    with file_path.open("wb") as buffer:
        buffer.write(image.file.read())

    mask_path = None
    overlay_path = None
    layout_summary = {}
    try:
        mask_img, usable_area_m2, confidence = segment_rooftop(
            file_path, roof_width_m=roof_width_m
        )
        layout = build_panel_layout(
            Image.open(file_path),
            mask_img,
            roof_width_m=roof_width_m,
            gsd_meters_per_pixel=None,
            panel_w_m=DEFAULT_ASSUMPTIONS["panel_area_m2"],
            panel_h_m=1.0,
        )
        usable_area_m2 = layout.usable_area_m2
        mask_name = f"mask_{file_id}.png"
        mask_path = OUTPUT_DIR / str(user.id)
        mask_path.mkdir(parents=True, exist_ok=True)
        mask_file_path = mask_path / mask_name
        mask_img.save(mask_file_path)
        mask_path = str(mask_file_path.relative_to(DATA_DIR))

        overlay_name = f"overlay_{file_id}.png"
        overlay_dir = OUTPUT_DIR / str(user.id)
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_file_path = overlay_dir / overlay_name
        if layout.overlay is not None:
            layout.overlay.save(overlay_file_path)
            overlay_path = str(overlay_file_path.relative_to(DATA_DIR))

        layout_summary = {
            "panel_count": layout.panel_count,
            "panel_area_m2": layout.panel_area_m2,
            "coverage_ratio": layout.coverage_ratio,
            "overlay_path": overlay_path,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Segmentation failed: {exc}") from exc

    assumptions = {
        **DEFAULT_ASSUMPTIONS,
        "panel_wattage_w": panel_wattage or profile["panel_wattage_w"],
        "cost_per_watt": cost_per_watt or profile["cost_per_watt"],
        "tariff_rate": tariff_rate or DEFAULT_ASSUMPTIONS["tariff_rate"],
    }
    assumptions["annual_sun_hours"] *= preferences["sunlight_factor"]
    system = estimate_system(usable_area_m2, assumptions)
    if layout_summary.get("panel_count"):
        system["panel_count"] = layout_summary["panel_count"]
        system["dc_kw"] = (layout_summary["panel_count"] * assumptions["panel_wattage_w"]) / 1000
    scenario = _build_scenarios(assumptions, usable_area_m2, preferences)
    roi = calculate_roi(system, assumptions)

    project = Project(
        user_id=user.id,
        name=name,
        method="upload",
        image_path=str(file_path.relative_to(DATA_DIR)),
        mask_path=mask_path,
        usable_area_m2=usable_area_m2,
        panel_count=system["panel_count"],
        power_kw=system["dc_kw"],
        annual_kwh=system["annual_kwh"],
        installation_cost=roi["installation_cost"],
        annual_savings=roi["annual_savings"],
        payback_years=roi["payback_years"],
        total_savings_25yrs=roi["total_savings_25yrs"],
        confidence=confidence,
        assumptions=assumptions,
        source_data={
            "roof_width_m": roof_width_m,
            "panel_overlay_path": overlay_path,
            "panel_coverage_ratio": layout_summary.get("coverage_ratio"),
            "currency": preferences["currency"],
            "units": preferences["units"],
            "scenario": scenario,
        },
    )
    db.add(project)
    db.commit()

    return RedirectResponse(url=f"/projects/{project.id}", status_code=302)


@app.get("/evaluate")
def evaluation_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    return templates.TemplateResponse(
        request,
        "evaluate.html",
        {"request": request, "avatar_url": resolve_user_avatar(user)},
    )


@app.post("/evaluate")
def evaluate_segmentation(
    request: Request,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    extension = Path(image.filename or "upload.jpg").suffix
    file_id = f"eval_{uuid4().hex}{extension}"
    user_dir = EVAL_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / file_id
    with file_path.open("wb") as buffer:
        buffer.write(image.file.read())

    model_mask, _, model_conf = segment_rooftop(file_path, use_model=True)
    heuristic_mask, _, heuristic_conf = segment_rooftop(file_path, use_model=False)

    model_path = user_dir / f"model_{file_id}.png"
    heuristic_path = user_dir / f"heuristic_{file_id}.png"
    model_mask.save(model_path)
    heuristic_mask.save(heuristic_path)

    return templates.TemplateResponse(
        request,
        "evaluate.html",
        {
            "request": request,
            "avatar_url": resolve_user_avatar(user),
            "model_mask": str(model_path.relative_to(DATA_DIR)),
            "heuristic_mask": str(heuristic_path.relative_to(DATA_DIR)),
            "image_path": str(file_path.relative_to(DATA_DIR)),
            "model_conf": model_conf,
            "heuristic_conf": heuristic_conf,
        },
    )


@app.post("/projects/polygon")
def create_project_from_polygon(
    request: Request,
    name: str = Form(...),
    polygon_coords: str = Form(...),
    panel_wattage: int = Form(DEFAULT_ASSUMPTIONS["panel_wattage_w"]),
    cost_per_watt: float = Form(DEFAULT_ASSUMPTIONS["cost_per_watt"]),
    tariff_rate: float = Form(DEFAULT_ASSUMPTIONS["tariff_rate"]),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    projects = fetch_user_projects(db, user.id)

    try:
        coords = json.loads(polygon_coords)
        polygon = [(float(point[0]), float(point[1])) for point in coords]
    except (ValueError, TypeError, json.JSONDecodeError):
        polygon = []

    if len(polygon) < 3:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "projects": projects,
                "assumptions": DEFAULT_ASSUMPTIONS,
                "error": "Draw a valid polygon on the map first.",
            },
            status_code=400,
        )

    usable_area_m2 = polygon_area_m2(polygon) * DEFAULT_ASSUMPTIONS["roof_utilization"]
    assumptions = {
        **DEFAULT_ASSUMPTIONS,
        "panel_wattage_w": panel_wattage,
        "cost_per_watt": cost_per_watt,
        "tariff_rate": tariff_rate,
    }
    system = estimate_system(usable_area_m2, assumptions)
    roi = calculate_roi(system, assumptions)

    project = Project(
        user_id=user.id,
        name=name,
        method="polygon",
        usable_area_m2=usable_area_m2,
        panel_count=system["panel_count"],
        power_kw=system["dc_kw"],
        annual_kwh=system["annual_kwh"],
        installation_cost=roi["installation_cost"],
        annual_savings=roi["annual_savings"],
        payback_years=roi["payback_years"],
        total_savings_25yrs=roi["total_savings_25yrs"],
        confidence=0.7,
        assumptions=assumptions,
        source_data={"polygon": polygon},
    )
    db.add(project)
    db.commit()

    return RedirectResponse(url=f"/projects/{project.id}", status_code=302)


@app.post("/projects/address")
def create_project_from_address(
    request: Request,
    name: str = Form(...),
    address: str = Form(...),
    panel_wattage: int | None = Form(None),
    cost_per_watt: float | None = Form(None),
    tariff_rate: float | None = Form(None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    projects = fetch_user_projects(db, user.id)
    preferences = get_preferences(user)
    profile = resolve_panel_profile(preferences["panel_type"])

    try:
        location = geocode_address(address)
    except Exception:
        location = None
    if not location:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "projects": projects,
                "assumptions": DEFAULT_ASSUMPTIONS,
                "error": "Address lookup failed. Try a nearby landmark.",
            },
            status_code=400,
        )

    try:
        footprint = fetch_building_footprint(location["lat"], location["lon"])
    except Exception:
        footprint = None
    if not footprint:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "projects": projects,
                "assumptions": DEFAULT_ASSUMPTIONS,
                "error": "No building footprint found near this address.",
            },
            status_code=400,
        )

    usable_area_m2 = footprint["area_m2"] * DEFAULT_ASSUMPTIONS["roof_utilization"]
    sunlight_factor = pick_sunlight_factor(location["display_name"])
    assumptions = {
        **DEFAULT_ASSUMPTIONS,
        "panel_wattage_w": panel_wattage or profile["panel_wattage_w"],
        "cost_per_watt": cost_per_watt or profile["cost_per_watt"],
        "tariff_rate": tariff_rate or DEFAULT_ASSUMPTIONS["tariff_rate"],
    }
    assumptions["annual_sun_hours"] *= sunlight_factor
    system = estimate_system(usable_area_m2, assumptions)
    scenario = _build_scenarios(assumptions, usable_area_m2, preferences)
    roi = calculate_roi(system, assumptions)

    project = Project(
        user_id=user.id,
        name=name,
        address=location["display_name"],
        latitude=location["lat"],
        longitude=location["lon"],
        method="address",
        usable_area_m2=usable_area_m2,
        panel_count=system["panel_count"],
        power_kw=system["dc_kw"],
        annual_kwh=system["annual_kwh"],
        installation_cost=roi["installation_cost"],
        annual_savings=roi["annual_savings"],
        payback_years=roi["payback_years"],
        total_savings_25yrs=roi["total_savings_25yrs"],
        confidence=0.8,
        assumptions=assumptions,
        source_data={
            "footprint_area_m2": footprint["area_m2"],
            "currency": preferences["currency"],
            "units": preferences["units"],
            "scenario": scenario,
        },
    )
    db.add(project)
    db.commit()

    return RedirectResponse(url=f"/projects/{project.id}", status_code=302)


@app.post("/projects/manual")
def create_project_manual_area(
    request: Request,
    name: str = Form(...),
    usable_area_m2: float = Form(...),
    panel_wattage: int | None = Form(None),
    cost_per_watt: float | None = Form(None),
    tariff_rate: float | None = Form(None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    preferences = get_preferences(user)
    profile = resolve_panel_profile(preferences["panel_type"])
    if usable_area_m2 <= 0:
        projects = fetch_user_projects(db, user.id)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "projects": projects,
                "assumptions": DEFAULT_ASSUMPTIONS,
                "error": "Usable area must be greater than zero.",
            },
            status_code=400,
        )

    assumptions = {
        **DEFAULT_ASSUMPTIONS,
        "panel_wattage_w": panel_wattage or profile["panel_wattage_w"],
        "cost_per_watt": cost_per_watt or profile["cost_per_watt"],
        "tariff_rate": tariff_rate or DEFAULT_ASSUMPTIONS["tariff_rate"],
    }
    system = estimate_system(usable_area_m2, assumptions)
    scenario = _build_scenarios(assumptions, usable_area_m2, preferences)
    roi = calculate_roi(system, assumptions)

    project = Project(
        user_id=user.id,
        name=name,
        method="manual",
        usable_area_m2=usable_area_m2,
        panel_count=system["panel_count"],
        power_kw=system["dc_kw"],
        annual_kwh=system["annual_kwh"],
        installation_cost=roi["installation_cost"],
        annual_savings=roi["annual_savings"],
        payback_years=roi["payback_years"],
        total_savings_25yrs=roi["total_savings_25yrs"],
        confidence=0.6,
        assumptions=assumptions,
        source_data={
            "entry": "manual",
            "currency": preferences["currency"],
            "units": preferences["units"],
            "scenario": scenario,
        },
    )
    db.add(project)
    db.commit()

    return RedirectResponse(url=f"/projects/{project.id}", status_code=302)


@app.get("/projects/{project_id}")
def project_detail(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    preferences = get_preferences(user)
    return templates.TemplateResponse(
        request,
        "project.html",
        {
            "request": request,
            "project": project,
            "currency_symbol": currency_symbol(preferences["currency"]),
            "units": preferences["units"],
            "avatar_url": resolve_user_avatar(user),
        },
    )


def _build_scenarios(assumptions: dict, area_m2: float, preferences: dict) -> dict:
    standard = {**assumptions, "panel_wattage_w": 400, "cost_per_watt": 0.9}
    premium = {**assumptions, "panel_wattage_w": 450, "cost_per_watt": 1.2}
    standard_system = estimate_system(area_m2, standard)
    premium_system = estimate_system(area_m2, premium)

    budget = preferences.get("budget")
    if budget:
        standard_cap = int(budget / (standard["panel_wattage_w"] * standard["cost_per_watt"]))
        premium_cap = int(budget / (premium["panel_wattage_w"] * premium["cost_per_watt"]))
    else:
        standard_cap = None
        premium_cap = None

    return {
        "standard": {
            "panels": standard_system["panel_count"],
            "dc_kw": standard_system["dc_kw"],
            "cost_per_watt": standard["cost_per_watt"],
            "budget_cap": standard_cap,
        },
        "premium": {
            "panels": premium_system["panel_count"],
            "dc_kw": premium_system["dc_kw"],
            "cost_per_watt": premium["cost_per_watt"],
            "budget_cap": premium_cap,
        },
    }


@app.get("/projects/{project_id}/report")
def download_report(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    report_path = REPORT_DIR / f"project_{project.id}.pdf"
    build_project_report(project, report_path, data_dir=DATA_DIR, user_name=user.name)
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"{project.name.replace(' ', '_')}_report.pdf",
    )
