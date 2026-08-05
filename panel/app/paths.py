"""Расположение изменяемых данных панели (config.json, logs).

Логика:
- Если задан WOW_PANEL_HOME — конфиг и логи хранятся там (используется в .deb,
  где код лежит в /opt и доступен только на чтение).
- Иначе всё лежит рядом с кодом (dev-режим, запуск из репозитория).
"""
from __future__ import annotations

import os
from pathlib import Path

# Каталог с кодом (panel/) — только для чтения в случае системной установки.
INSTALL_DIR = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    env = os.environ.get("WOW_PANEL_HOME")
    base = Path(env).expanduser() if env else INSTALL_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return data_dir() / "config.json"


def example_config_path() -> Path:
    return INSTALL_DIR / "config.example.json"


def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d
