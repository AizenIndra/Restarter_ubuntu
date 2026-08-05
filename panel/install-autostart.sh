#!/usr/bin/env bash
# Установка/удаление автозапуска WoW Server Panel при входе в систему.
# Панель — GUI-приложение, поэтому используем XDG autostart (~/.config/autostart),
# он запускается автоматически после логина в графическую сессию.
set -euo pipefail

PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$PANEL_DIR/run-panel.sh"
ICON="$PANEL_DIR/assets/wow-panel.png"

AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/wow-server-panel.desktop"

usage() {
  cat <<EOF
Использование: ./install-autostart.sh [install|remove|status]

  install  — включить автозапуск при входе в систему (по умолчанию)
  remove   — отключить автозапуск
  status   — показать текущее состояние
EOF
}

do_install() {
  [[ -f "$RUN" ]] || { echo "Нет $RUN"; exit 1; }
  chmod +x "$RUN" 2>/dev/null || true
  mkdir -p "$AUTOSTART_DIR"

  cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=WoW Server Panel
Comment=Автозапуск панели управления сервером + Telegram-бот
Exec=$RUN --tray
Icon=$ICON
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=8
Categories=Utility;
EOF

  chmod +x "$AUTOSTART_FILE" 2>/dev/null || true
  echo "Автозапуск включён: $AUTOSTART_FILE"
  echo "Панель будет открываться после входа в систему (в трее)."
  echo
  echo "Подсказка: сами auth/world можно ставить на автозапуск отдельно, через"
  echo "  sudo $PANEL_DIR/../wow-restarter.sh install-systemd"
}

do_remove() {
  if [[ -f "$AUTOSTART_FILE" ]]; then
    rm -f "$AUTOSTART_FILE"
    echo "Автозапуск отключён (файл удалён)."
  else
    echo "Автозапуск не был установлен."
  fi
}

do_status() {
  if [[ -f "$AUTOSTART_FILE" ]]; then
    echo "Автозапуск: ВКЛЮЧЁН"
    echo "Файл: $AUTOSTART_FILE"
  else
    echo "Автозапуск: выключен"
  fi
}

case "${1:-install}" in
  install) do_install ;;
  remove|uninstall) do_remove ;;
  status) do_status ;;
  -h|--help|help) usage ;;
  *) usage; exit 1 ;;
esac
