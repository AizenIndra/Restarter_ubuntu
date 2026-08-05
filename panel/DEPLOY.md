# WoW Server Panel — установка, автозапуск, перенос и релиз (.deb)

Этот документ описывает три сценария:

1. **Автозапуск** панели при старте системы (уже настраивается одним скриптом).
2. **Перенос** панели на другой компьютер вручную.
3. **Сборка релиза `.deb`** — «установил и забыл».

---

## 1. Автозапуск при входе в систему

Панель — это графическое приложение, поэтому она запускается **после входа в
систему** (login), а не как фоновый демон. Для этого используется стандартный
механизм автозапуска рабочего стола (XDG autostart).

### Включить автозапуск

```bash
cd /home/aizen/Server/Restarter/panel
./install-autostart.sh install
```

Что делает скрипт:

- создаёт файл `~/.config/autostart/wow-server-panel.desktop`;
- панель стартует автоматически при следующем входе в систему **свёрнутой в трей**
  (флаг `--tray`), чтобы не мешать окном;
- если в `config.json` заданы `bot_token` и `owner_id`, Telegram-бот поднимается
  автоматически вместе с панелью.

### Проверить / отключить

```bash
./install-autostart.sh status    # показать состояние
./install-autostart.sh remove    # отключить автозапуск
```

### Автозапуск самих серверов (auth/world)

Панель управляет процессами, но её автозапуск открывает только **окно панели**.
Чтобы **сами игровые процессы** поднимались при загрузке ОС (даже без входа в
графику), поставьте их отдельно через systemd:

```bash
sudo /home/aizen/Server/Restarter/wow-restarter.sh install-systemd
```

> Итог: systemd поднимает auth/world при загрузке сервера, а автозапуск панели
> открывает управление/бот после вашего логина.

---

## 2. Перенос на другую систему (вручную, без .deb)

Подходит для быстрого переноса «как есть».

### 2.1. Требования на новой машине

Ubuntu/Debian с графикой. Установите системные пакеты:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1
```

### 2.2. Скопировать панель

Скопируйте папку `panel/` **без** `venv/`, `logs/` и `config.json`
(они пересоздадутся):

```bash
rsync -a --exclude venv --exclude logs --exclude config.json \
  /home/aizen/Server/Restarter/panel/  user@new-host:/home/user/Server/Restarter/panel/
```

Также перенесите скрипт рестартера и его конфиг, если используете его:

```
wow-restarter.sh
config.sh
```

### 2.3. Первый запуск

```bash
cd ~/Server/Restarter/panel
./run-panel.sh
```

При первом запуске скрипт сам создаст `venv` и установит зависимости из
`requirements.txt`. Панель создаст `config.json` из `config.example.json`.

### 2.4. Настроить пути и доступы

Откройте вкладку **Настройки** в панели (или отредактируйте `config.json`) и
проверьте:

- `paths.*` — пути к `authserver`, `worldserver`, конфигам и `wow-restarter.sh`
  на **новой** машине;
- `telegram.bot_token`, `telegram.owner_id` — токен бота и ваш Telegram ID;
- `mysql.*` — доступ к БД AzerothCore;
- `soap.*` — доступ к SOAP (если включён в `worldserver.conf`).

### 2.5. Автозапуск на новой машине

```bash
./install-autostart.sh install
```

---

## 3. Сборка релиза `.deb` («установил и забыл»)

### 3.1. Собрать пакет

На машине-сборщике (нужен только `dpkg-deb`, он есть в Ubuntu по умолчанию):

```bash
cd /home/aizen/Server/Restarter/panel
./packaging/build-deb.sh 1.0.0
```

Готовый файл появится в:

```
panel/dist/wow-server-panel_1.0.0_all.deb
```

Что попадает в пакет:

| Что | Куда ставится |
|-----|----------------|
| Код панели | `/opt/wow-server-panel` (только чтение) |
| Команда запуска | `/usr/bin/wow-server-panel` |
| Ярлык в меню | `/usr/share/applications/wow-server-panel.desktop` |
| Иконка | `/usr/share/icons/hicolor/256x256/apps/` |
| Автозапуск при логине | `/etc/xdg/autostart/wow-server-panel.desktop` |

> **Конфиг и логи пользователя** НЕ входят в пакет и хранятся отдельно в
> `~/.local/share/wow-server-panel/` (переменная `WOW_PANEL_HOME`). Так обновление
> пакета не затирает ваши настройки.

### 3.2. Установить пакет

```bash
sudo apt install ./wow-server-panel_1.0.0_all.deb
```

`apt` сам подтянет зависимости (`python3-venv`, `libxcb-cursor0` и т.д.).
На этапе установки (`postinst`) автоматически создаётся `venv` в
`/opt/wow-server-panel/venv` и ставятся Python-пакеты из `requirements.txt`
(нужен интернет при установке).

Альтернатива без apt:

```bash
sudo dpkg -i wow-server-panel_1.0.0_all.deb
sudo apt -f install    # доустановит зависимости
```

### 3.3. После установки

- В меню приложений появится **WoW Server Panel** (можно закрепить в панель задач).
- Панель будет **автозапускаться при входе** в систему (в трее).
- При первом запуске откройте вкладку **Настройки** и заполните пути, Telegram,
  MySQL, SOAP. Файл сохранится в `~/.local/share/wow-server-panel/config.json`.

### 3.4. Обновление / удаление

```bash
# обновление — просто поставить новый .deb (настройки сохранятся)
sudo apt install ./wow-server-panel_1.1.0_all.deb

# удаление (настройки в ~/.local/share остаются)
sudo apt remove wow-server-panel

# полное удаление
sudo apt purge wow-server-panel
```

---

## 4. Где что лежит (шпаргалка)

| Режим | Код | Конфиг | Логи |
|-------|-----|--------|------|
| Из репозитория (dev) | `panel/` | `panel/config.json` | `panel/logs/` |
| Установка `.deb` | `/opt/wow-server-panel` | `~/.local/share/wow-server-panel/config.json` | `~/.local/share/wow-server-panel/logs/` |

Переключение режима задаётся переменной `WOW_PANEL_HOME`:
если она задана — конфиг и логи берутся оттуда; если нет — из папки с кодом.

---

## 5. Частые проблемы

- **`Could not load the Qt platform plugin "xcb"`** — не хватает системной
  библиотеки. Установите:
  `sudo apt-get install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1`.
- **Панель не стартует при загрузке** — проверьте `./install-autostart.sh status`
  (ручной режим) или наличие `/etc/xdg/autostart/wow-server-panel.desktop` (для .deb).
  Автозапуск срабатывает только после **входа** в графическую сессию.
- **Бот молчит** — заполните `telegram.bot_token` и `telegram.owner_id`
  в `config.json`; писать боту может только владелец с этим ID.
- **`.server info` / SOAP недоступен** — включите SOAP в `worldserver.conf`
  (`SOAP.Enabled = 1`) и укажите логин/пароль GM-аккаунта в `config.json`.
