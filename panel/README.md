# WoW Server Panel + Telegram-бот

Десктоп-панель (PySide6) для OrstetCore / AzerothCore 3.3.5:
настройка путей, MySQL, SOAP, управление auth/world и Telegram-бот **только для вашего User ID**.

## Быстрый старт

На Ubuntu 24.04 для окна Qt нужен пакет `libxcb-cursor0` (иначе падает xcb plugin):

```bash
sudo apt-get update
sudo apt-get install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
```

Затем:

```bash
cd /home/aizen/Server/Restarter/panel
chmod +x run-panel.sh
./run-panel.sh
```

При первом запуске создаётся `venv` и ставятся зависимости из `requirements.txt`.

Ярлык на рабочем столе: **WoW Server Panel** (`~/Рабочий стол/WoW Server Panel.desktop`).  
Если Ubuntu спросит — выбери «Разрешить запуск» / Allow Launching.

### Системный трей

- Кнопка **В трей**, сворачивание (−) и закрытие (×) прячут окно в трей (галочка «Сворачивать в трей»).
- Клик / двойной клик по иконке — показать или скрыть окно.
- ПКМ по иконке: Показать / Скрыть / Статус / **Выход** (полный выход только отсюда).
- Нужен работающий system tray (на GNOME может понадобиться расширение AppIndicator).

## Настройка в окне

1. **Пути** — `wow-restarter.sh`, бинарники `authserver` / `worldserver`, conf-файлы  
2. **Telegram** — token от [@BotFather](https://t.me/BotFather), Owner User ID от [@userinfobot](https://t.me/userinfobot)  
3. **MySQL / SOAP** — доступ к `acore_characters` и GM-логин для SOAP  
4. Нажмите **Сохранить настройки** → `config.json` (не коммитится)  
5. Вкладка **Управление** — Start / Stop / Restart / Status  
6. Вкладка **Telegram** — **Запустить бота**

## Telegram-команды (только Owner ID)

| Команда | Действие |
|---------|----------|
| `/help` | Справка |
| `/status` | Статус процессов + SOAP info |
| `/online` | Игроки онлайн |
| `/mysql` | Ping MySQL |
| `/serverinfo` | SOAP `.server info` |
| `/announce текст` | Игровой announce |
| `/start_servers` | Запуск auth+world |
| `/stop` | Остановка |
| `/restart` | Рестарт |

Чужие аккаунты получают `Access denied.`

> `/start` зарезервирован Telegram как «старт диалога» и показывает справку. Для запуска серверов используйте `/start_servers`.

## SOAP (AzerothCore)

В `worldserver.conf`:

```ini
SOAP.Enabled = 1
SOAP.IP = "127.0.0.1"
SOAP.Port = 7878
```

Аккаунт GM должен иметь права на нужные команды. Логин/пароль SOAP — это данные аккаунта (как в игре).

## Зависимости

- Python 3.10+
- Уже существующий [`../wow-restarter.sh`](../wow-restarter.sh)
- MySQL/MariaDB для онлайна
- Собранный сервер в `OrstetCore/env/dist` (или свои пути)

## Файлы

```
panel/
  main.py
  run-panel.sh
  config.example.json
  config.json          # создаётся локально, секреты
  app/
    config_store.py
    restarter_bridge.py
    mysql_service.py
    soap_client.py
    telegram_bot.py
    ui/main_window.py
```
