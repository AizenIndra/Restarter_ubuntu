# WoW Server Panel — инструкция для `.deb`

## Что это такое

WoW Server Panel — графическая панель для управления сервером WoW 3.3.5
(OrstetCore/AzerothCore) на Ubuntu и Debian.

Панель позволяет:

- запускать и останавливать `authserver` и `worldserver`;
- видеть состояние процессов и журналы запуска;
- проверять MySQL и количество игроков онлайн;
- отправлять команды через SOAP;
- управлять сервером через Telegram-бота;
- разрешать Telegram-команды только одному указанному User ID;
- работать в системном трее;
- автоматически запускаться после входа в систему.

## 1. Требования

- Ubuntu или Debian с графической оболочкой;
- Python 3.10 или новее;
- готовый сервер AzerothCore/OrstetCore;
- скрипт `wow-restarter.sh`;
- доступ к интернету во время установки Python-зависимостей.

Игровой сервер и база данных в `.deb` не входят.

## 2. Установка

Откройте терминал в каталоге с загруженным пакетом:

```bash
sudo apt install ./wow-server-panel_1.0.0_all.deb
```

Используйте настоящее имя скачанного файла, если версия отличается.

Команда `apt` автоматически установит необходимые системные зависимости.
Во время установки будет создано Python-окружение и установлены библиотеки
панели.

Если пакет устанавливается через `dpkg`:

```bash
sudo dpkg -i wow-server-panel_1.0.0_all.deb
sudo apt-get -f install
```

После установки панель появится в меню приложений под названием
**WoW Server Panel**.

Запустить её также можно командой:

```bash
wow-server-panel
```

## 3. Первая настройка

Запустите панель и откройте вкладку **Настройки**.

Укажите:

### Пути

- путь к `wow-restarter.sh`;
- корневой каталог собранного игрового сервера;
- путь к `authserver`;
- путь к `worldserver`;
- путь к `authserver.conf`;
- путь к `worldserver.conf`.

Пути на каждом компьютере могут отличаться. Не оставляйте примерные пути,
если ваш сервер установлен в другом каталоге.

### MySQL

- адрес сервера, обычно `127.0.0.1`;
- порт, обычно `3306`;
- имя пользователя;
- пароль;
- база персонажей, обычно `acore_characters`.

### SOAP

В `worldserver.conf` включите SOAP:

```ini
SOAP.Enabled = 1
SOAP.IP = "127.0.0.1"
SOAP.Port = 7878
```

В панели укажите адрес, порт, логин и пароль аккаунта с необходимыми
GM-правами.

### Telegram

1. Создайте бота через [@BotFather](https://t.me/BotFather).
2. Скопируйте Bot Token в настройки панели.
3. Узнайте свой User ID через [@userinfobot](https://t.me/userinfobot).
4. Укажите его в поле Owner ID.
5. Сохраните настройки.

Бот выполняет административные команды только для указанного Owner ID.
Не передавайте Bot Token другим людям.

Пользовательская конфигурация хранится в:

```text
~/.local/share/wow-server-panel/config.json
```

Этот файл содержит секреты. Не публикуйте и не отправляйте его посторонним.

## 4. Автозапуск панели

Пакет автоматически устанавливает файл:

```text
/etc/xdg/autostart/wow-server-panel.desktop
```

Дополнительные команды не требуются. После следующего входа в графическую
сессию панель запустится свёрнутой в системный трей. Настроенный Telegram-бот
также запустится вместе с панелью.

Важно: это автозапуск **после входа пользователя в Ubuntu**, потому что панель
является графическим приложением.

### Отключить автозапуск только для текущего пользователя

```bash
mkdir -p ~/.config/autostart
cp /etc/xdg/autostart/wow-server-panel.desktop \
  ~/.config/autostart/wow-server-panel.desktop
printf '\nHidden=true\n' >> ~/.config/autostart/wow-server-panel.desktop
```

Чтобы снова включить его, удалите пользовательский файл:

```bash
rm ~/.config/autostart/wow-server-panel.desktop
```

## 5. Автозапуск authserver и worldserver вместе с ОС

Автозапуск панели не означает автоматический запуск игровых процессов.

Чтобы `authserver` и `worldserver` запускались при загрузке ОС даже без входа
в графическую оболочку, используйте systemd-команду рестартера:

```bash
sudo /полный/путь/к/wow-restarter.sh install-systemd
```

Пример:

```bash
sudo /home/user/Server/Restarter/wow-restarter.sh install-systemd
```

Перед установкой systemd-служб проверьте пути в `config.sh`.

Проверка служб:

```bash
systemctl status wow-authserver.service
systemctl status wow-worldserver.service
```

Отключение служб:

```bash
sudo /полный/путь/к/wow-restarter.sh uninstall-systemd
```

## 6. Telegram-команды

- `/help` — список команд;
- `/status` — полный статус сервера;
- `/online` — количество игроков;
- `/mysql` — проверка MySQL;
- `/serverinfo` — информация через SOAP;
- `/gmhelp [поиск]` — каталог GM-команд AzerothCore (~700);
- `/gm команда` — выполнить GM-команду через SOAP;
- `/announce текст` — объявление в игре;
- `/start_servers` — запуск серверов;
- `/stop` — остановка;
- `/restart` — перезапуск.

Примеры GM:

```text
/gmhelp ban
/gm server info
/gm announce Hello
/gm kick CharacterName
```

Полный список: https://www.azerothcore.org/wiki/gm-commands

## 7. Обновление

Установите новую версию поверх старой:

```bash
sudo apt install ./wow-server-panel_1.1.0_all.deb
```

Конфигурация в `~/.local/share/wow-server-panel/` сохранится.

## 8. Удаление

Удалить программу:

```bash
sudo apt remove wow-server-panel
```

Удалить оставшиеся пользовательские настройки и журналы:

```bash
rm -rf ~/.local/share/wow-server-panel
```

Вторая команда необязательна и безвозвратно удаляет конфигурацию, Telegram
Token и журналы панели.

## 9. Решение проблем

### Панель не открывается

Запустите её из терминала и посмотрите ошибку:

```bash
wow-server-panel
```

### Ошибка Qt или `xcb`

```bash
sudo apt-get install -y \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1
```

### Панель не появилась в трее

Некоторым версиям GNOME требуется расширение AppIndicator. При этом панель
можно открыть повторно через меню приложений.

### Бот не отвечает

Проверьте Bot Token, Owner ID, доступ к интернету и вкладку **Консоль**.

### Сервер не запускается

Проверьте пути в настройках, доступность MySQL и журналы `authserver.out` и
`worldserver.out`. Панель не устанавливает сам игровой сервер.

## 10. Расположение файлов

- программа: `/opt/wow-server-panel`;
- команда запуска: `/usr/bin/wow-server-panel`;
- ярлык меню: `/usr/share/applications/wow-server-panel.desktop`;
- системный автозапуск: `/etc/xdg/autostart/wow-server-panel.desktop`;
- конфигурация: `~/.local/share/wow-server-panel/config.json`;
- журналы панели: `~/.local/share/wow-server-panel/logs/`;
- эта инструкция: `/usr/share/doc/wow-server-panel/README.md`.
