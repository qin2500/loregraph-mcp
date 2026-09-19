from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_PORT = 58632


def config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ceb-mcp" / "config.json"


def load_config() -> dict | None:
    path = config_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_config(config: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    if sys.platform != "win32":
        path.chmod(0o600)
