#!/usr/bin/env python3
"""Standalone Telegram bot process (не внутри Qt — без segfault)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PANEL_DIR = Path(__file__).resolve().parent
if str(PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(PANEL_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from app.config_store import load_config
from app.telegram_bot import TelegramBotRunner


def main() -> int:
    cfg = load_config()
    token = (cfg.get("telegram") or {}).get("bot_token") or ""
    owner = int((cfg.get("telegram") or {}).get("owner_id") or 0)
    if not token.strip() or owner <= 0:
        print("ERROR: bot_token / owner_id not set in config.json", flush=True)
        return 2

    def on_ready(msg: str) -> None:
        print(f"READY {msg}", flush=True)

    print(f"Starting bot for owner_id={owner}…", flush=True)
    runner = TelegramBotRunner(cfg, on_ready=on_ready)
    try:
        runner.start_blocking()
    except KeyboardInterrupt:
        print("Stopped by signal", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", flush=True)
        logging.exception("bot crashed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
