from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def icon_path(name: str) -> Path:
    return project_root() / "icons" / name

