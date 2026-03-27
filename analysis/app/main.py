from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "app"
TARGET = APP_DIR / "main.py"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

package_spec = importlib.util.spec_from_file_location(
    "app",
    APP_DIR / "__init__.py",
    submodule_search_locations=[str(APP_DIR)],
)
if package_spec is None or package_spec.loader is None:
    raise RuntimeError("Failed to load FastAPI app package")

package_module = importlib.util.module_from_spec(package_spec)
sys.modules["app"] = package_module
package_spec.loader.exec_module(package_module)

spec = importlib.util.spec_from_file_location("app.main", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("Failed to load FastAPI app module")

module = importlib.util.module_from_spec(spec)
sys.modules["app.main"] = module
spec.loader.exec_module(module)

app = module.app
