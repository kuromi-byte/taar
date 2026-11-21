"""Shared config loader — reads contracts/config.json.
All tunables come from here. Never hard-code coordinates.
"""
from __future__ import annotations
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # pipeline/model → pipeline → taar
CONFIG_PATH = _REPO_ROOT / "contracts" / "config.json"


def load_config() -> dict:
    """Return parsed config dict. Exits with a clear message if file missing."""
    import sys
    if not CONFIG_PATH.exists():
        sys.exit(f"STOP: {CONFIG_PATH} missing — cannot proceed without pilot config.")
    return json.loads(CONFIG_PATH.read_text())


def get_repo_root() -> Path:
    return _REPO_ROOT
