import os
import sys
from pathlib import Path

import yaml

VALID_STORAGE_MODES = ("repo", "folder")
VALID_SINGLE_COMMAND = ("ignore", "run")

DEFAULT_SETTINGS = {"storage_mode": "repo", "single_command": "ignore"}


def base_config_dir() -> Path:
    """Return the platform-aware base config directory for runit."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    config_dir = base / "runit"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def settings_path() -> Path:
    return base_config_dir() / "settings.yaml"


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            return dict(DEFAULT_SETTINGS)
        return {**DEFAULT_SETTINGS, **raw}
    except yaml.YAMLError:
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    path = settings_path()
    path.write_text(yaml.dump(settings, default_flow_style=False, sort_keys=False))


def get_storage_mode() -> str:
    return load_settings().get("storage_mode", "repo")
