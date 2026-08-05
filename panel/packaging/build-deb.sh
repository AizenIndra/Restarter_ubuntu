#!/usr/bin/env bash
# Сборка .deb-пакета WoW Server Panel.
#
# Что получится:
#   - код панели устанавливается в /opt/wow-server-panel (только чтение)
#   - команда `wow-server-panel` в меню и в терминале
#   - конфиг и логи пользователя лежат в ~/.local/share/wow-server-panel
#   - автозапуск при входе в систему (/etc/xdg/autostart)
#   - на этапе установки создаётся venv и ставятся Python-зависимости
#
# Использование:
#   ./packaging/build-deb.sh [версия]
# Пример:
#   ./packaging/build-deb.sh 1.0.0
set -euo pipefail

PKG="wow-server-panel"
PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-1.0.0}"
ARCH="all"
OUT_DIR="$PANEL_DIR/dist"
STAGE="$(mktemp -d)"
INSTALL_ROOT="opt/$PKG"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "==> Сборка $PKG $VERSION"
echo "    Источник: $PANEL_DIR"

# --- 1. Копируем код панели в /opt (без venv, логов, локального конфига) ---
mkdir -p "$STAGE/$INSTALL_ROOT"
tar \
  --exclude='./venv' \
  --exclude='./logs' \
  --exclude='./dist' \
  --exclude='./__pycache__' \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude='./config.json' \
  --exclude='./.git' \
  -cf - -C "$PANEL_DIR" . | tar -xf - -C "$STAGE/$INSTALL_ROOT"

# --- 2. Лаунчер /usr/bin/wow-server-panel ---
mkdir -p "$STAGE/usr/bin"
cat > "$STAGE/usr/bin/$PKG" <<EOF
#!/usr/bin/env bash
# Запуск WoW Server Panel из системной установки.
export WOW_PANEL_HOME="\${WOW_PANEL_HOME:-\$HOME/.local/share/$PKG}"
mkdir -p "\$WOW_PANEL_HOME"
exec /$INSTALL_ROOT/run-panel.sh "\$@"
EOF
chmod 755 "$STAGE/usr/bin/$PKG"

# --- 3. Иконка ---
ICON_DST="$STAGE/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DST"
if [[ -f "$PANEL_DIR/assets/wow-panel.png" ]]; then
  cp "$PANEL_DIR/assets/wow-panel.png" "$ICON_DST/$PKG.png"
fi

# --- 4. Инструкция для пользователей пакета ---
DOC_DST="$STAGE/usr/share/doc/$PKG"
mkdir -p "$DOC_DST"
cp "$PANEL_DIR/packaging/readme.md" "$DOC_DST/README.md"

# --- 5. Ярлык в меню приложений ---
APP_DST="$STAGE/usr/share/applications"
mkdir -p "$APP_DST"
cat > "$APP_DST/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=WoW Server Panel
Comment=Управление сервером WoW 3.3.5 + Telegram-бот
Exec=$PKG
Icon=$PKG
Terminal=false
Categories=Utility;Game;
EOF

# --- 6. Автозапуск при входе в систему (для всех пользователей) ---
AUTO_DST="$STAGE/etc/xdg/autostart"
mkdir -p "$AUTO_DST"
cat > "$AUTO_DST/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=WoW Server Panel
Comment=Автозапуск панели управления сервером WoW
Exec=$PKG --tray
Icon=$PKG
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=8
Categories=Utility;
EOF

# --- 7. Метаданные пакета (DEBIAN/control + скрипты) ---
mkdir -p "$STAGE/DEBIAN"

INSTALLED_KB="$(du -sk "$STAGE" | cut -f1)"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-venv, python3-pip, libxcb-cursor0, libxcb-xinerama0, libxkbcommon-x11-0, libgl1
Installed-Size: $INSTALLED_KB
Maintainer: aizen <aizen@panel>
Description: WoW 3.3.5 Server Panel
 GUI-панель управления сервером WoW 3.3.5 (OrstetCore/AzerothCore):
 запуск/остановка authserver и worldserver, статус, MySQL/SOAP и
 Telegram-бот с доступом только для владельца.
EOF

# postinst: создать venv и поставить зависимости
cat > "$STAGE/DEBIAN/postinst" <<EOF
#!/bin/bash
set -e
INSTALL="/$INSTALL_ROOT"

echo "Настройка WoW Server Panel: установка Python-зависимостей…"
if [ ! -x "\$INSTALL/venv/bin/python" ]; then
  python3 -m venv "\$INSTALL/venv"
fi
"\$INSTALL/venv/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
"\$INSTALL/venv/bin/pip" install -r "\$INSTALL/requirements.txt"

chmod +x "\$INSTALL"/*.sh 2>/dev/null || true
chmod +x "\$INSTALL/run_bot.py" 2>/dev/null || true

update-desktop-database -q 2>/dev/null || true
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true

echo "Готово. Запуск: меню приложений «WoW Server Panel» или команда $PKG"
echo "Конфиг пользователя: ~/.local/share/$PKG/config.json"
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

# prerm: остановить возможный запущенный экземпляр не пытаемся — GUI пользовательский
cat > "$STAGE/DEBIAN/postrm" <<EOF
#!/bin/bash
set -e
if [ "\$1" = "remove" ] || [ "\$1" = "purge" ]; then
  rm -rf "/$INSTALL_ROOT/venv" "/$INSTALL_ROOT/logs"
  rmdir "/$INSTALL_ROOT" 2>/dev/null || true
  update-desktop-database -q 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postrm"

# conffiles: ничего пользовательского не трогаем (config.json не в пакете)

# --- 8. Права и сборка ---
find "$STAGE/$INSTALL_ROOT" -type d -exec chmod 755 {} +
find "$STAGE/$INSTALL_ROOT" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/$INSTALL_ROOT/run-panel.sh" 2>/dev/null || true
chmod 755 "$STAGE/$INSTALL_ROOT/install-autostart.sh" 2>/dev/null || true
chmod 755 "$STAGE/$INSTALL_ROOT/run_bot.py" 2>/dev/null || true
chmod 755 "$STAGE/$INSTALL_ROOT/main.py" 2>/dev/null || true

chmod 755 "$STAGE"
# Нормализуем права каталогов (staging мог получить 775 из-за umask)
find "$STAGE/usr" "$STAGE/etc" -type d -exec chmod 755 {} + 2>/dev/null || true
find "$STAGE/usr/share" "$STAGE/etc" -type f -exec chmod 644 {} + 2>/dev/null || true
chmod 644 "$STAGE/usr/share/applications/$PKG.desktop"
chmod 755 "$STAGE/usr/bin/$PKG"

mkdir -p "$OUT_DIR"
DEB_PATH="$OUT_DIR/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB_PATH"

echo
echo "==> Готово: $DEB_PATH"
echo
echo "Установка:"
echo "  sudo apt install $DEB_PATH        # подтянет зависимости"
echo "  # или: sudo dpkg -i $DEB_PATH && sudo apt -f install"
