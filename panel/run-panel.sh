#!/usr/bin/env bash
# Запуск WoW Server Panel (быстрый старт)
set -euo pipefail

PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PANEL_DIR"

VENV="$PANEL_DIR/venv"
PYTHON="${PYTHON:-python3}"

if [[ ! -e /usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0 && ! -e /lib/x86_64-linux-gnu/libxcb-cursor.so.0 ]]; then
  cat <<'EOF' >&2
Ошибка: не найдена библиотека libxcb-cursor (нужна для окна Qt).

  sudo apt-get install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
EOF
  exit 1
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Создаю venv…"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r requirements.txt
fi

if [[ -z "${QT_QPA_PLATFORM:-}" && -n "${DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
fi

# Без activate — быстрее
exec "$VENV/bin/python" -u "$PANEL_DIR/main.py" "$@"
