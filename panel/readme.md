# WoW Server Panel

Графическая панель для управления сервером WoW 3.3.5
(OrstetCore/AzerothCore) на Ubuntu.

Возможности:

- запуск, остановка и перезапуск `authserver` и `worldserver`;
- просмотр состояния процессов и консольных сообщений;
- проверка MySQL и количества игроков онлайн;
- выполнение команд через SOAP;
- управление через Telegram-бота;
- доступ к Telegram-командам только для указанного Owner ID;
- сворачивание в системный трей;
- автоматический запуск после входа в Ubuntu;
- сборка установочного пакета `.deb`.

## 1. Быстрый запуск

Установите системные зависимости:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1
```

Запустите панель:

```bash
cd /home/aizen/Server/Restarter/panel
chmod +x run-panel.sh
./run-panel.sh
```

При первом запуске автоматически создаётся Python-окружение `venv` и
устанавливаются пакеты из `requirements.txt`.

## 2. Настройка панели

Откройте вкладку **Настройки** и заполните:

1. Путь к `wow-restarter.sh`.
2. Путь к папке собранного сервера.
3. Пути к `authserver`, `worldserver` и их `.conf`-файлам.
4. Параметры подключения к MySQL.
5. Параметры SOAP.
6. Telegram Bot Token и Owner User ID.

Нажмите **Сохранить настройки**.

При обычном запуске конфигурация хранится в:

```text
/home/aizen/Server/Restarter/panel/config.json
```

Не публикуйте `config.json`: в нём могут находиться токен Telegram и пароли.

## 3. Telegram-бот

Создайте бота через [@BotFather](https://t.me/BotFather), скопируйте токен и
укажите его в настройках панели.

Узнать свой Telegram User ID можно через
[@userinfobot](https://t.me/userinfobot). Укажите ID в поле Owner ID.
Команды других пользователей будут отклонены.

Основные команды:

- `/help` — помощь;
- `/status` — полный статус сервера;
- `/online` — количество игроков;
- `/mysql` — состояние MySQL;
- `/serverinfo` — информация через SOAP;
- `/announce текст` — объявление в игре;
- `/gmhelp [поиск]` — каталог GM-команд AzerothCore;
- `/gm команда` — выполнить любую GM-команду через SOAP;
- `/start_servers` — запуск серверов;
- `/stop` — остановка;
- `/restart` — перезапуск.

Каталог GM-команд взят из
[официальной wiki AzerothCore](https://www.azerothcore.org/wiki/gm-commands)
(~700 команд). Примеры:

```text
/gmhelp ban
/gmhelp kick
/gm server info
/gm announce Hello players
/gm kick CharacterName
/gm ban account login -1 reason
```

Некоторые команды требуют выбранной цели в игровом клиенте и через SOAP
могут не работать — бот предупредит об этом.

## 4. SOAP

В `worldserver.conf` должны быть включены параметры:

```ini
SOAP.Enabled = 1
SOAP.IP = "127.0.0.1"
SOAP.Port = 7878
```

В панели укажите логин и пароль аккаунта с достаточными GM-правами.

## 5. Автозапуск панели

Включить автозапуск после входа в Ubuntu:

```bash
cd /home/aizen/Server/Restarter/panel
./install-autostart.sh install
```

Панель будет запускаться свёрнутой в системный трей. Если Telegram настроен,
бот также запустится автоматически.

Проверить или отключить автозапуск:

```bash
./install-autostart.sh status
./install-autostart.sh remove
```

Для автоматического запуска самих `authserver` и `worldserver` при загрузке ОС:

```bash
sudo /home/aizen/Server/Restarter/wow-restarter.sh install-systemd
```

## 6. Сборка и установка `.deb`

Собрать пакет:

```bash
cd /home/aizen/Server/Restarter/panel
chmod +x packaging/build-deb.sh
./packaging/build-deb.sh 1.0.0
```

Результат:

```text
dist/wow-server-panel_1.0.0_all.deb
```

Установить:

```bash
sudo apt install ./dist/wow-server-panel_1.0.0_all.deb
```

После установки панель появится в меню приложений и будет автоматически
запускаться в трее после входа в систему.

Конфигурация установленной `.deb`-версии хранится отдельно:

```text
~/.local/share/wow-server-panel/config.json
```

Обновление пакета не удаляет пользовательские настройки.

Удаление:

```bash
sudo apt remove wow-server-panel
```

## 7. Перенос на другую систему

1. Скопируйте каталог проекта без `venv/`, `logs/` и `config.json`.
2. Установите системные зависимости из раздела «Быстрый запуск».
3. Проверьте пути к серверу и конфигурационным файлам.
4. Запустите `./run-panel.sh`.
5. Заполните настройки панели.
6. Выполните `./install-autostart.sh install`.

Подробная инструкция по переносу и созданию релиза находится в
[`DEPLOY.md`](DEPLOY.md).

## 8. Частые проблемы

### Ошибка Qt `xcb`

```bash
sudo apt-get install -y \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1
```

### Панель не запускается автоматически

```bash
./install-autostart.sh status
```

Автозапуск GUI срабатывает после входа пользователя в графическую сессию.

### Telegram-бот не отвечает

Проверьте Bot Token, Owner ID, интернет-соединение и сообщения во вкладке
**Консоль**. Бот намеренно не выполняет команды пользователей с другим ID.

### Сервер сразу завершается

Посмотрите вкладку **Консоль** и файлы журналов `authserver.out` и
`worldserver.out` в каталоге логов рестартера. Частые причины: MySQL недоступен,
ошибка SQL-обновления, неверный путь к библиотекам или конфигурации.

