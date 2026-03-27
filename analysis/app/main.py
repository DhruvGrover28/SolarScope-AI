from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
TARGET = ROOT_DIR / "app" / "main.py"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

spec = importlib.util.spec_from_file_location("solar_scope_app", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("Failed to load FastAPI app module")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app
