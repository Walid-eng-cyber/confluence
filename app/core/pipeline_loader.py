from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_MODULE_CACHE: ModuleType | None = None


def load_pipeline_module() -> ModuleType:
    """Load scripts/setup_review_poc.py as an importable module, once per process."""
    global _MODULE_CACHE

    if _MODULE_CACHE is not None:
        return _MODULE_CACHE

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "setup_review_poc.py"
    spec = importlib.util.spec_from_file_location("setup_review_poc", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE = module
    return module
