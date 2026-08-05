"""Load / save panel config.json."""
from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.paths import config_path as _config_path
from app.paths import example_config_path as _example_config_path

PANEL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = _config_path()
EXAMPLE_PATH = _example_config_path()

DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "restarter_script": "/home/aizen/Server/Restarter/wow-restarter.sh",
        "server_root": "/home/aizen/Server/OrstetCore/env/dist",
        "auth_bin": "/home/aizen/Server/OrstetCore/env/dist/bin/authserver",
        "world_bin": "/home/aizen/Server/OrstetCore/env/dist/bin/worldserver",
        "auth_conf": "/home/aizen/Server/OrstetCore/env/dist/etc/authserver.conf",
        "world_conf": "/home/aizen/Server/OrstetCore/env/dist/etc/worldserver.conf",
    },
    "telegram": {
        "bot_token": "",
        "owner_id": 0,
    },
    "mysql": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "acore",
        "password": "acore",
        "database": "acore_characters",
    },
    "soap": {
        "host": "127.0.0.1",
        "port": 7878,
        "username": "",
        "password": "",
    },
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or CONFIG_PATH
    if not cfg_path.exists():
        if EXAMPLE_PATH.exists():
            shutil.copy(EXAMPLE_PATH, cfg_path)
            return _deep_merge(DEFAULT_CONFIG, json.loads(cfg_path.read_text(encoding="utf-8")))
        save_config(DEFAULT_CONFIG, cfg_path)
        return deepcopy(DEFAULT_CONFIG)
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _deep_merge(DEFAULT_CONFIG, data)


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    cfg_path = path or CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
