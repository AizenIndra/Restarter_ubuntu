#!/usr/bin/env python3
"""WoW Server Panel — entry point."""
from __future__ import annotations

import faulthandler
import sys
from pathlib import Path

PANEL_DIR = Path(__file__).resolve().parent
if str(PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(PANEL_DIR))

# Пишем segfault-трейсы в файл
from app.paths import logs_dir

_fault_log = logs_dir() / "faulthandler.log"
_fault_fp = open(_fault_log, "a", encoding="utf-8")  # noqa: SIM115
faulthandler.enable(file=_fault_fp, all_threads=True)

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WoW Server Panel")
    app.setOrganizationName("OrstetCore")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    # --tray / --minimized: старт сразу в трее (для автозапуска при логине)
    start_in_tray = any(arg in ("--tray", "--minimized") for arg in sys.argv[1:])
    if start_in_tray and window.has_tray():
        window.hide()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
