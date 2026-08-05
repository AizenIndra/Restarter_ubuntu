"""Каталог GM-команд AzerothCore (из официальной wiki).

Источник: https://www.azerothcore.org/wiki/gm-commands
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "gm_commands.json"
WIKI_URL = "https://www.azerothcore.org/wiki/gm-commands"

# Команды, которым обычно нужен выбранный игрок/NPC в клиенте —
# через SOAP их часто нельзя использовать «в лоб».
NEEDS_TARGET_HINTS = (
    "appear",
    "aura",
    "cast",
    "die",
    "go creature",
    "go object",
    "gps",
    "modify",
    "morph",
    "npc",
    "possess",
    "summon",
    "tele",
)


@lru_cache(maxsize=1)
def load_commands() -> tuple[dict[str, Any], ...]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return tuple(data)


def search_commands(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Поиск по имени / синтаксису / описанию."""
    q = (query or "").strip().lower().lstrip(".")
    if not q:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for cmd in load_commands():
        name = cmd["name"].lower()
        syntax = (cmd.get("syntax") or "").lower()
        desc = (cmd.get("description") or "").lower()
        score = 0
        if name == q:
            score = 100
        elif name.startswith(q):
            score = 80
        elif q in name:
            score = 60
        elif q in syntax:
            score = 40
        elif q in desc:
            score = 20
        if score:
            scored.append((score, cmd))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    return [c for _, c in scored[:limit]]


def find_exact(command_line: str) -> dict[str, Any] | None:
    """Найти максимально длинное совпадение имени команды в начале строки."""
    text = (command_line or "").strip().lstrip(".")
    if not text:
        return None
    best: dict[str, Any] | None = None
    best_len = -1
    lower = text.lower()
    for cmd in load_commands():
        name = cmd["name"].lower()
        if lower == name or lower.startswith(name + " "):
            if len(name) > best_len:
                best = cmd
                best_len = len(name)
    return best


def needs_target_hint(cmd: dict[str, Any] | None) -> bool:
    if not cmd:
        return False
    name = cmd["name"].lower()
    return any(name == h or name.startswith(h + " ") for h in NEEDS_TARGET_HINTS)


def format_command_card(cmd: dict[str, Any]) -> str:
    name = cmd["name"]
    sec = cmd.get("security", "?")
    syntax = cmd.get("syntax") or f".{name}"
    desc = cmd.get("description") or "—"
    lines = [
        f"<b>.{_esc(name)}</b>  ·  GM level <code>{sec}</code>",
        f"<code>{_esc(syntax)}</code>",
        _esc(desc[:500]),
    ]
    if needs_target_hint(cmd):
        lines.append(
            "<i>⚠️ Часто нужен выбранный игрок/NPC в клиенте — "
            "через SOAP может не сработать.</i>"
        )
    return "\n".join(lines)


def format_search_results(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return (
            f"Ничего не найдено по <code>{_esc(query)}</code>.\n"
            f"Список команд: {WIKI_URL}"
        )
    lines = [
        f"<b>GM-команды</b> · поиск «{_esc(query)}» · найдено {len(results)}",
        "",
    ]
    for cmd in results:
        syn = cmd.get("syntax") or f".{cmd['name']}"
        lines.append(
            f"• <code>{_esc(syn)}</code>  "
            f"<i>lvl {cmd.get('security', '?')}</i>"
        )
        desc = (cmd.get("description") or "").strip()
        if desc:
            lines.append(f"  {_esc(desc[:120])}")
    lines.append("")
    lines.append("Выполнить: <code>/gm команда аргументы</code>")
    lines.append(f"Wiki: {WIKI_URL}")
    return "\n".join(lines)


def format_catalog_intro() -> str:
    total = len(load_commands())
    return (
        f"<b>GM-команды AzerothCore</b> ({total} шт.)\n"
        f"Источник: {WIKI_URL}\n\n"
        "Поиск: <code>/gmhelp ban</code>\n"
        "Справка по команде: <code>/gmhelp announce</code>\n"
        "Выполнить через SOAP: <code>/gm announce Hello</code>\n"
        "или <code>/gm .server info</code>\n\n"
        "Популярные:\n"
        "• <code>/gm server info</code>\n"
        "• <code>/gm announce текст</code>\n"
        "• <code>/gm saveall</code>\n"
        "• <code>/gm kick Имя</code>\n"
        "• <code>/gm ban account логин -1 причина</code>\n"
        "• <code>/gm unban account логин</code>\n"
        "• <code>/gm server shutdown 60</code>\n"
        "• <code>/gm reload table</code>\n"
    )


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
