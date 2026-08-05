# WoW 3.3.5 Restarter (Ubuntu)

Рестартер для **authserver** и **worldserver** (OrstetCore / AzerothCore) на Ubuntu: запуск без открытого терминала и автоперезапуск при краше.

## Панель + Telegram-бот

Графическая панель (PySide6) с Telegram-ботом (только ваш User ID):

```bash
cd /home/aizen/Server/Restarter/panel
./run-panel.sh
```

Подробности: [panel/README.md](panel/README.md).

## Быстрый старт (без systemd)

1. Убедитесь, что сервер собран и лежит в `env/dist` (или поправьте пути в `config.sh`).
2. Сделайте скрипт исполняемым и запустите:

```bash
cd /home/aizen/Server/Restarter
chmod +x wow-restarter.sh
./wow-restarter.sh start
./wow-restarter.sh status
```

Серверы уходят в фон через `setsid` — терминал можно закрыть.

Авторестарт при падении:

```bash
nohup ./wow-restarter.sh watchdog >> ./logs/watchdog.out 2>&1 &
```

Остановка:

```bash
./wow-restarter.sh stop
```

## Рекомендуемый способ: systemd

После того как бинарники и конфиги на месте:

```bash
cd /home/aizen/Server/Restarter
# при необходимости отредактируйте SERVER_ROOT / пути в config.sh
sudo ./wow-restarter.sh install-systemd
```

Дальше:

| Действие | Команда |
|----------|---------|
| Статус | `systemctl status wow-authserver wow-worldserver` |
| Логи world | `journalctl -u wow-worldserver -f` |
| Рестарт world | `sudo systemctl restart wow-worldserver` |
| Стоп оба | `sudo systemctl stop wow-worldserver wow-authserver` |
| Автозапуск | уже включён (`enable`) |

Удаление сервисов:

```bash
sudo ./wow-restarter.sh uninstall-systemd
```

## Настройка путей

Файл `config.sh`:

- `SERVER_ROOT` — корень установки (по умолчанию `.../OrstetCore/env/dist`)
- `AUTH_BIN` / `WORLD_BIN` — бинарники
- `AUTH_CONF` / `WORLD_CONF` — конфиги
- `RESTART_DELAY` — пауза перед рестартом после краша

Если бинарники в другом месте — правьте `SERVER_ROOT` в `config.sh`.

## Ожидаемая структура OrstetCore

После сборки/установки:

```
OrstetCore/env/dist/
  bin/authserver
  bin/worldserver
  etc/authserver.conf
  etc/worldserver.conf
```

## Важно

- MySQL/MariaDB должны быть запущены до world/auth.
- Не запускайте одновременно `./wow-restarter.sh start` и systemd — конфликт портов.
- Логи рестартера: `Restarter/logs/`.
