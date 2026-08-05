"""Telegram bot (aiogram 3) — owner-only access."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand, Message, TelegramObject

from app.gm_catalog import (
    WIKI_URL,
    find_exact,
    format_catalog_intro,
    format_command_card,
    format_search_results,
    needs_target_hint,
    search_commands,
)
from app.mysql_service import MySQLService
from app.restarter_bridge import RestarterBridge
from app.soap_client import SOAPClient
from app.status_report import (
    collect_status,
    format_mysql_html,
    format_online_html,
    format_status_html,
)
logger = logging.getLogger(__name__)


class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_id: int) -> None:
        self.owner_id = int(owner_id)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or int(user.id) != self.owner_id:
            if isinstance(event, Message):
                await event.answer(
                    f"Access denied.\nВаш ID: {getattr(user, 'id', '?')}\n"
                    f"Нужен Owner ID: {self.owner_id}"
                )
            return None
        return await handler(event, data)


class TelegramBotRunner:
    """Runs aiogram polling in a background asyncio loop (for QThread)."""

    def __init__(self, config: dict[str, Any], on_ready: Callable[[str], None] | None = None) -> None:
        self.config = config
        self.on_ready = on_ready
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bot: Optional[Bot] = None
        self._dp: Optional[Dispatcher] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def build_dispatcher(self) -> Dispatcher:
        owner_id = int(self.config["telegram"].get("owner_id") or 0)
        if owner_id <= 0:
            raise ValueError("Owner Telegram User ID is not set")

        token = (self.config["telegram"].get("bot_token") or "").strip()
        if not token:
            raise ValueError("Telegram bot token is empty")

        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.message.middleware(OwnerOnlyMiddleware(owner_id))

        restarter = RestarterBridge(self.config)
        mysql = MySQLService(self.config)
        soap = SOAPClient(self.config)
        config = self.config

        @dp.message(Command("help", "start"))
        async def cmd_help(message: Message) -> None:
            await message.answer(
                "<b>WoW Server Panel</b> — команды:\n"
                "/status — красивый статус сервера\n"
                "/online — игроки онлайн\n"
                "/mysql — проверка MySQL\n"
                "/serverinfo — SOAP .server info\n"
                "/announce &lt;текст&gt; — announce\n"
                "/gmhelp [поиск] — каталог GM-команд\n"
                "/gm &lt;команда&gt; — выполнить GM-команду через SOAP\n"
                "/start_servers — запуск auth+world\n"
                "/stop — остановка\n"
                "/restart — рестарт\n\n"
                f"Список GM: {WIKI_URL}"
            )

        @dp.message(Command("status"))
        async def cmd_status(message: Message) -> None:
            await message.answer("⏳ Собираю статус…")
            data = await asyncio.to_thread(collect_status, config)
            await message.answer(format_status_html(data))

        @dp.message(Command("online"))
        async def cmd_online(message: Message) -> None:
            ok, count, err = await asyncio.to_thread(mysql.online_count_value)
            await message.answer(format_online_html(ok, count, err))

        @dp.message(Command("mysql"))
        async def cmd_mysql(message: Message) -> None:
            ok, out = await asyncio.to_thread(mysql.ping)
            await message.answer(format_mysql_html(ok, out))

        @dp.message(Command("serverinfo"))
        async def cmd_serverinfo(message: Message) -> None:
            ok, out = await asyncio.to_thread(soap.execute, "server info")
            if ok:
                await message.answer(f"<b>SOAP server info</b>\n<pre>{_tg_esc(out[:3500])}</pre>")
            else:
                await message.answer(f"<b>SOAP</b>\n❌ <code>{_tg_esc(out[:500])}</code>")

        @dp.message(Command("announce"))
        async def cmd_announce(message: Message, command: CommandObject) -> None:
            text = (command.args or "").strip()
            if not text:
                await message.answer("Использование: /announce &lt;текст&gt;")
                return
            ok, out = await asyncio.to_thread(soap.execute, f"announce {text}")
            await message.answer(out[:4000] if out else ("OK" if ok else "FAIL"))

        @dp.message(Command("gmhelp", "commands", "gmlist"))
        async def cmd_gmhelp(message: Message, command: CommandObject) -> None:
            query = (command.args or "").strip()
            if not query:
                await message.answer(format_catalog_intro())
                return
            results = await asyncio.to_thread(search_commands, query, 15)
            if len(results) == 1:
                await message.answer(format_command_card(results[0]))
                return
            # точное совпадение имени — карточка
            exact = [r for r in results if r["name"].lower() == query.lower().lstrip(".")]
            if len(exact) == 1 and len(results) <= 3:
                await message.answer(format_command_card(exact[0]))
                return
            await message.answer(format_search_results(query, results))

        @dp.message(Command("gm", "cmd"))
        async def cmd_gm(message: Message, command: CommandObject) -> None:
            raw = (command.args or "").strip()
            if not raw:
                await message.answer(
                    "Использование: <code>/gm команда аргументы</code>\n"
                    "Пример: <code>/gm server info</code>\n"
                    "Поиск: <code>/gmhelp kick</code>"
                )
                return
            # убрать ведущую точку — SOAP принимает без неё
            gm_cmd = raw.lstrip(".")
            known = find_exact(gm_cmd)
            hint = ""
            if known:
                hint = (
                    f"📖 <b>.{_tg_esc(known['name'])}</b> "
                    f"(lvl {known.get('security', '?')})\n"
                    f"<code>{_tg_esc(known.get('syntax') or '')}</code>\n"
                )
                if needs_target_hint(known):
                    hint += (
                        "<i>⚠️ Команда часто требует выбранной цели в клиенте.</i>\n"
                    )
                hint += "\n"
            elif len(gm_cmd.split()) == 1:
                # неизвестная короткая команда — предложить поиск
                suggestions = search_commands(gm_cmd, 5)
                if suggestions:
                    await message.answer(
                        f"Команда <code>{_tg_esc(gm_cmd)}</code> не найдена в каталоге.\n"
                        + format_search_results(gm_cmd, suggestions)
                    )
                    return

            await message.answer(f"{hint}⏳ SOAP: <code>{_tg_esc(gm_cmd)}</code>")
            ok, out = await asyncio.to_thread(soap.execute, gm_cmd)
            if ok:
                body = _tg_esc((out or "OK")[:3500])
                await message.answer(f"✅ <pre>{body}</pre>")
            else:
                await message.answer(f"❌ <code>{_tg_esc((out or 'FAIL')[:800])}</code>")

        @dp.message(Command("start_servers"))
        async def cmd_start_servers(message: Message) -> None:
            await message.answer("🚀 Запускаю auth + world…")
            code, out = await asyncio.to_thread(restarter.start)
            data = await asyncio.to_thread(collect_status, config)
            await message.answer(
                f"Старт: <code>exit={code}</code>\n\n" + format_status_html(data)
            )

        @dp.message(Command("stop"))
        async def cmd_stop(message: Message) -> None:
            await message.answer("⏹ Останавливаю серверы…")
            code, out = await asyncio.to_thread(restarter.stop)
            data = await asyncio.to_thread(collect_status, config)
            await message.answer(
                f"Стоп: <code>exit={code}</code>\n\n" + format_status_html(data)
            )

        @dp.message(Command("restart"))
        async def cmd_restart(message: Message) -> None:
            await message.answer("🔄 Рестартую серверы…")
            code, out = await asyncio.to_thread(restarter.restart)
            data = await asyncio.to_thread(collect_status, config)
            await message.answer(
                f"Рестарт: <code>exit={code}</code>\n\n" + format_status_html(data)
            )

        self._bot = bot
        self._dp = dp
        return dp

    async def _poll(self) -> None:
        assert self._bot is not None and self._dp is not None
        self._running = True
        try:
            # Сброс webhook — иначе polling молчит
            await self._bot.delete_webhook(drop_pending_updates=True)
            me = await self._bot.get_me()
            await self._bot.set_my_commands(
                [
                    BotCommand(command="help", description="Справка"),
                    BotCommand(command="status", description="Статус серверов"),
                    BotCommand(command="online", description="Онлайн"),
                    BotCommand(command="mysql", description="Проверка MySQL"),
                    BotCommand(command="serverinfo", description="SOAP server info"),
                    BotCommand(command="gmhelp", description="Поиск GM-команд"),
                    BotCommand(command="gm", description="Выполнить GM через SOAP"),
                    BotCommand(command="announce", description="Announce в игру"),
                    BotCommand(command="start_servers", description="Запуск серверов"),
                    BotCommand(command="stop", description="Остановить серверы"),
                    BotCommand(command="restart", description="Перезапустить серверы"),
                ]
            )
            ready_msg = f"@{me.username} online (owner={self.config['telegram']['owner_id']})"
            logger.info(ready_msg)
            if self.on_ready:
                self.on_ready(ready_msg)
            await self._dp.start_polling(self._bot, handle_signals=False)
        finally:
            self._running = False
            await self._bot.session.close()

    def start_blocking(self) -> None:
        """Create event loop and run polling until stop()."""
        self.build_dispatcher()
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._poll())
        except Exception:
            logger.exception("Telegram bot crashed")
            self._running = False
            raise
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001
                pass
            self._loop.close()
            self._loop = None

    def stop(self) -> None:
        if self._loop and self._dp and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._dp.stop_polling)


def _tg_esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
