"""Persistent first-run and background-behaviour preferences."""

import json
import os
from pathlib import Path


SETTINGS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenShark" / "preferences.json"
DEFAULTS = {
    "onboarding_complete": False,
    "start_with_windows": False,
    "battery_in_taskbar": False,
}


def load():
    try:
        saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return {**DEFAULTS, **{key: saved[key] for key in DEFAULTS if key in saved}}


def save(values):
    result = {**DEFAULTS, **values}
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
