"""Красивый отчёт статуса сервера для Telegram."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.mysql_service import MySQLService
from app.restarter_bridge import RestarterBridge
from app.soap_client import SOAPClient


def _parse_restarter_status(out: str) -> dict[str, dict[str, str]]:
    """SERVICE STATUS PID → {authserver: {status, pid}, ...}"""
    result: dict[str, dict[str, str]] = {}
    for line in (out or "").splitlines():
        line = line.strip()
        if not line or line.upper().startswith("SERVICE"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].lower()
        status = parts[1].upper().rstrip("*")
        pid = parts[2] if len(parts) > 2 else "-"
        if name in {"authserver", "worldserver"}:
            result[name] = {"status": status, "pid": pid}
    return result


def _badge(up: bool) -> str:
    return "🟢 ONLINE" if up else "🔴 OFFLINE"


def _is_up(status: str) -> bool:
    return status.upper().startswith("UP")


def _clean_soap(text: str) -> str:
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text or "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    # убираем слишком шумные строки
    skip_prefixes = (">> Loaded", "Loading ", "Spell ", "Item (")
    useful: list[str] = []
    for ln in lines:
        if any(ln.startswith(p) for p in skip_prefixes):
            continue
        useful.append(ln)
        if len(useful) >= 12:
            break
    return "\n".join(useful) if useful else cleaned.strip()[:500]


def collect_status(config: dict[str, Any]) -> dict[str, Any]:
    restarter = RestarterBridge(config)
    mysql = MySQLService(config)
    soap = SOAPClient(config)

    _code, status_out = restarter.status()
    procs = _parse_restarter_status(status_out)

    mysql_ok, mysql_msg = mysql.ping()
    online_ok, online_count, _online_err = mysql.online_count_value()

    auth = procs.get("authserver", {"status": "DOWN", "pid": "-"})
    world = procs.get("worldserver", {"status": "DOWN", "pid": "-"})
    auth_up = _is_up(auth["status"])
    world_up = _is_up(world["status"])

    soap_ok, soap_out = False, ""
    if world_up:
        soap_ok, soap_out = soap.execute("server info")

    return {
        "auth": auth,
        "world": world,
        "auth_up": auth_up,
        "world_up": world_up,
        "mysql_ok": mysql_ok,
        "mysql_msg": mysql_msg,
        "online_ok": online_ok,
        "online": online_count,
        "soap_ok": soap_ok,
        "soap_out": soap_out,
        "raw_status": status_out,
        "ts": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
    }


def format_status_html(data: dict[str, Any]) -> str:
    auth_up = bool(data["auth_up"])
    world_up = bool(data["world_up"])
    both = auth_up and world_up
    header = "🏰 <b>WoW 3.3.5 — OrstetCore</b>"
    overall = "✅ Сервер работает" if both else ("⚠️ Частично онлайн" if (auth_up or world_up) else "⛔ Сервер оффлайн")

    auth = data["auth"]
    world = data["world"]
    lines = [
        header,
        overall,
        f"<i>{data['ts']}</i>",
        "",
        "<b>Процессы</b>",
        f"• Authserver — <b>{_badge(auth_up)}</b>  <code>pid {auth.get('pid', '-')}</code>",
        f"• Worldserver — <b>{_badge(world_up)}</b>  <code>pid {world.get('pid', '-')}</code>",
        "",
        "<b>База / игроки</b>",
    ]

    if data["mysql_ok"]:
        # вытащим ms если есть
        ms = ""
        m = re.search(r"\((\d+)\s*ms\)", data.get("mysql_msg") or "")
        if m:
            ms = f" · {m.group(1)} ms"
        lines.append(f"• MySQL — <b>🟢 OK</b>{ms}")
    else:
        lines.append("• MySQL — <b>🔴 FAIL</b>")
        err = (data.get("mysql_msg") or "")[:120]
        if err:
            lines.append(f"  <code>{_escape(err)}</code>")

    if data["online_ok"]:
        lines.append(f"• Онлайн — <b>{int(data['online'])}</b> игрок(ов)")
    else:
        lines.append("• Онлайн — <i>н/д</i>")

    if data.get("soap_ok") and data.get("soap_out"):
        soap_clean = _clean_soap(data["soap_out"])
        lines.append("")
        lines.append("<b>World info (SOAP)</b>")
        lines.append(f"<pre>{_escape(soap_clean)[:900]}</pre>")
    elif world_up and not data.get("soap_ok"):
        lines.append("")
        lines.append("• SOAP — <b>🔴 недоступен</b>")
        hint = (data.get("soap_out") or "")[:150]
        if hint:
            lines.append(f"  <code>{_escape(hint)}</code>")

    lines.append("")
    lines.append("<i>/start_servers · /restart · /stop</i>")
    return "\n".join(lines)


def format_online_html(ok: bool, count: int, err: str = "") -> str:
    if ok:
        return (
            "👥 <b>Онлайн</b>\n"
            f"Сейчас в мире: <b>{count}</b> игрок(ов)"
        )
    return f"👥 <b>Онлайн</b>\n❌ Не удалось получить данные\n<code>{_escape(err[:200])}</code>"


def format_mysql_html(ok: bool, msg: str) -> str:
    if ok:
        return f"🗄 <b>MySQL</b>\n🟢 {_escape(msg)}"
    return f"🗄 <b>MySQL</b>\n🔴 {_escape(msg[:300])}"


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
