"""MySQL helpers: ping and online player count."""
from __future__ import annotations

import time
from typing import Any

import pymysql


class MySQLService:
    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = config["mysql"]

    def _connect(self, timeout: float = 2.0):
        return pymysql.connect(
            host=self.cfg["host"],
            port=int(self.cfg["port"]),
            user=self.cfg["user"],
            password=self.cfg["password"],
            database=self.cfg["database"],
            connect_timeout=timeout,
            read_timeout=timeout,
            write_timeout=timeout,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    def ping(self) -> tuple[bool, str]:
        started = time.perf_counter()
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS ok")
                    cur.fetchone()
            finally:
                conn.close()
            ms = (time.perf_counter() - started) * 1000
            return True, f"MySQL OK ({ms:.0f} ms) — {self.cfg['host']}:{self.cfg['port']}/{self.cfg['database']}"
        except Exception as exc:  # noqa: BLE001
            return False, f"MySQL FAIL: {exc}"

    def online_count(self) -> tuple[bool, str]:
        ok, count, err = self.online_count_value()
        if ok:
            return True, f"Online players: {count}"
        return False, f"Online query failed: {err}"

    def online_count_value(self) -> tuple[bool, int, str]:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM characters WHERE online = 1")
                    row = cur.fetchone() or {}
                    count = int(row.get("cnt", 0))
            finally:
                conn.close()
            return True, count, ""
        except Exception as exc:  # noqa: BLE001
            return False, 0, str(exc)
