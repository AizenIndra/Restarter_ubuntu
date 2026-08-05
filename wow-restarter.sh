#!/usr/bin/env bash
# WoW 3.3.5 restarter — authserver + worldserver без терминала
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"

ensure_dirs() {
  mkdir -p "$LOG_DIR" "$PID_DIR"
}

usage() {
  cat <<'EOF'
Использование: ./wow-restarter.sh <команда>

Команды:
  start           Запустить auth + world в фоне
  stop            Остановить оба сервера
  restart         Перезапустить оба
  status          Статус процессов
  start-auth      Только authserver
  start-world     Только worldserver
  stop-auth       Остановить authserver
  stop-world      Остановить worldserver
  watchdog        Следить и перезапускать при краше (держать в фоне)
  install-systemd Установить systemd-сервисы (нужен sudo)
  uninstall-systemd Удалить systemd-сервисы (нужен sudo)

Примеры:
  ./wow-restarter.sh start
  ./wow-restarter.sh watchdog &
  sudo ./wow-restarter.sh install-systemd
EOF
}

log() {
  ensure_dirs
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$msg" | tee -a "$LOG_DIR/restarter.log"
}

die() {
  echo "Ошибка: $*" >&2
  exit 1
}

require_bins() {
  [[ -x "$AUTH_BIN" ]] || die "Не найден authserver: $AUTH_BIN
Соберите и установите сервер, либо поправьте пути в config.sh"
  [[ -x "$WORLD_BIN" ]] || die "Не найден worldserver: $WORLD_BIN
Соберите и установите сервер, либо поправьте пути в config.sh"
}

is_running() {
  local name="$1"
  local pidfile="$PID_DIR/${name}.pid"
  [[ -f "$pidfile" ]] || return 1
  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  [[ -n "${pid:-}" ]] || return 1
  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  rm -f "$pidfile"
  return 1
}

# pid по имени бинарника (если запускали не через этот скрипт)
find_pid_by_bin() {
  local bin="$1"
  # Только точный путь бинарника, без ложных совпадений в cmdline
  pgrep -f "^${bin}( |$)" 2>/dev/null | head -n1 || true
}

tail_log() {
  local logfile="$1"
  if [[ -f "$logfile" ]]; then
    echo "---- последние строки $logfile ----"
    tail -n 25 "$logfile" | sed 's/\x1b\[[0-9;]*m//g' || true
    echo "---- конец лога ----"
  fi
}

start_one() {
  local name="$1"
  local bin="$2"
  local conf="$3"
  ensure_dirs
  local logfile="$LOG_DIR/${name}.out"
  local bindir
  bindir="$(dirname "$bin")"

  if is_running "$name"; then
    log "$name уже запущен (pid $(cat "$PID_DIR/${name}.pid"))"
    return 0
  fi

  local existing
  existing="$(find_pid_by_bin "$bin")"
  if [[ -n "$existing" ]]; then
    echo "$existing" > "$PID_DIR/${name}.pid"
    log "$name уже работал вне рестартера (pid $existing) — подхватил"
    return 0
  fi

  [[ -x "$bin" ]] || die "Нет исполняемого файла: $bin"

  local conf_args=()
  if [[ -f "$conf" ]]; then
    conf_args=(-c "$conf")
  else
    log "Предупреждение: конфиг не найден ($conf), запуск без -c"
  fi

  : >"$logfile"

  # setsid — отдельная сессия; LD_LIBRARY_PATH — libs рядом с бинарником
  (
    cd "$bindir"
    export LD_LIBRARY_PATH="${bindir}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    setsid "$bin" "${conf_args[@]}" >>"$logfile" 2>&1 &
    echo $! > "$PID_DIR/${name}.pid"
  )

  local wait_s="${START_WAIT:-5}"
  local i
  for i in $(seq 1 "$wait_s"); do
    sleep 1
    if is_running "$name"; then
      log "$name запущен (pid $(cat "$PID_DIR/${name}.pid")), лог: $logfile"
      return 0
    fi
  done

  log "$name не стартовал за ${wait_s}с"
  tail_log "$logfile" >&2
  die "$name не стартовал. Смотрите: $logfile"
}

stop_one() {
  local name="$1"
  local bin="$2"
  local pidfile="$PID_DIR/${name}.pid"
  local pid=""

  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
  fi
  if [[ -z "${pid:-}" ]] || ! kill -0 "$pid" 2>/dev/null; then
    pid="$(find_pid_by_bin "$bin")"
  fi

  if [[ -z "${pid:-}" ]]; then
    log "$name не запущен"
    rm -f "$pidfile"
    return 0
  fi

  log "Останавливаю $name (pid $pid)..."
  kill -TERM "$pid" 2>/dev/null || true

  local i
  for i in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  if kill -0 "$pid" 2>/dev/null; then
    log "$name не завершился за 30с — SIGKILL"
    kill -KILL "$pid" 2>/dev/null || true
  fi

  rm -f "$pidfile"
  log "$name остановлен"
}

cmd_start() {
  require_bins
  start_one authserver "$AUTH_BIN" "$AUTH_CONF"
  start_one worldserver "$WORLD_BIN" "$WORLD_CONF"
}

cmd_stop() {
  # world сначала (аккуратнее для игроков), потом auth
  stop_one worldserver "$WORLD_BIN"
  stop_one authserver "$AUTH_BIN"
}

cmd_restart() {
  cmd_stop
  sleep 2
  cmd_start
}

cmd_status() {
  ensure_dirs
  printf "%-12s %-8s %s\n" "SERVICE" "STATUS" "PID"
  for name_bin in "authserver:$AUTH_BIN" "worldserver:$WORLD_BIN"; do
    local name="${name_bin%%:*}"
    local bin="${name_bin#*:}"
    if is_running "$name"; then
      printf "%-12s %-8s %s\n" "$name" "UP" "$(cat "$PID_DIR/${name}.pid")"
    else
      local p
      p="$(find_pid_by_bin "$bin")"
      if [[ -n "$p" ]]; then
        printf "%-12s %-8s %s\n" "$name" "UP*" "$p"
      else
        printf "%-12s %-8s %s\n" "$name" "DOWN" "-"
      fi
    fi
  done
}

cmd_watchdog() {
  require_bins
  ensure_dirs
  log "Watchdog запущен (delay=${RESTART_DELAY}s, check=${CHECK_INTERVAL}s)"
  local auth_restarts=0
  local world_restarts=0

  # стартуем если ещё не подняты
  start_one authserver "$AUTH_BIN" "$AUTH_CONF" || true
  start_one worldserver "$WORLD_BIN" "$WORLD_CONF" || true

  while true; do
    if ! is_running authserver && [[ -z "$(find_pid_by_bin "$AUTH_BIN")" ]]; then
      auth_restarts=$((auth_restarts + 1))
      if [[ "$MAX_RESTARTS" -gt 0 && "$auth_restarts" -gt "$MAX_RESTARTS" ]]; then
        log "authserver: лимит рестартов ($MAX_RESTARTS), выхожу"
        exit 1
      fi
      log "authserver упал — перезапуск через ${RESTART_DELAY}с (#$auth_restarts)"
      sleep "$RESTART_DELAY"
      start_one authserver "$AUTH_BIN" "$AUTH_CONF" || true
    fi

    if ! is_running worldserver && [[ -z "$(find_pid_by_bin "$WORLD_BIN")" ]]; then
      world_restarts=$((world_restarts + 1))
      if [[ "$MAX_RESTARTS" -gt 0 && "$world_restarts" -gt "$MAX_RESTARTS" ]]; then
        log "worldserver: лимит рестартов ($MAX_RESTARTS), выхожу"
        exit 1
      fi
      log "worldserver упал — перезапуск через ${RESTART_DELAY}с (#$world_restarts)"
      sleep "$RESTART_DELAY"
      start_one worldserver "$WORLD_BIN" "$WORLD_CONF" || true
    fi

    sleep "$CHECK_INTERVAL"
  done
}

install_systemd() {
  local unit_dir="/etc/systemd/system"
  local restarter_dir="$SCRIPT_DIR"

  [[ "$(id -u)" -eq 0 ]] || die "install-systemd нужен root: sudo $0 install-systemd"

  cat > "$unit_dir/wow-authserver.service" <<EOF
[Unit]
Description=WoW 3.3.5 Authserver (OrstetCore)
After=network.target mysql.service mariadb.service
Wants=network.target

[Service]
Type=simple
User=$WOW_USER
Group=$WOW_USER
WorkingDirectory=$(dirname "$AUTH_BIN")
ExecStart=$AUTH_BIN -c $AUTH_CONF
Restart=always
RestartSec=$RESTART_DELAY
LimitNOFILE=102400
StandardOutput=append:$LOG_DIR/authserver.service.log
StandardError=append:$LOG_DIR/authserver.service.log

[Install]
WantedBy=multi-user.target
EOF

  cat > "$unit_dir/wow-worldserver.service" <<EOF
[Unit]
Description=WoW 3.3.5 Worldserver (OrstetCore)
After=network.target mysql.service mariadb.service wow-authserver.service
Wants=network.target wow-authserver.service

[Service]
Type=simple
User=$WOW_USER
Group=$WOW_USER
WorkingDirectory=$(dirname "$WORLD_BIN")
ExecStart=$WORLD_BIN -c $WORLD_CONF
Restart=always
RestartSec=$RESTART_DELAY
LimitNOFILE=102400
# worldserver иногда ждёт ввод — отключаем tty-зависимости
StandardInput=null
StandardOutput=append:$LOG_DIR/worldserver.service.log
StandardError=append:$LOG_DIR/worldserver.service.log

[Install]
WantedBy=multi-user.target
EOF

  # каталог логов под пользователя сервера
  mkdir -p "$LOG_DIR" "$PID_DIR"
  chown -R "$WOW_USER:$WOW_USER" "$LOG_DIR" "$PID_DIR" 2>/dev/null || true

  systemctl daemon-reload
  systemctl enable wow-authserver.service wow-worldserver.service
  systemctl restart wow-authserver.service
  sleep 2
  systemctl restart wow-worldserver.service

  echo
  echo "Готово. Сервисы установлены и запущены."
  echo "  systemctl status wow-authserver wow-worldserver"
  echo "  journalctl -u wow-worldserver -f"
  echo "Конфиг рестартера (пути): $restarter_dir/config.sh"
}

uninstall_systemd() {
  [[ "$(id -u)" -eq 0 ]] || die "нужен root: sudo $0 uninstall-systemd"
  systemctl stop wow-worldserver.service wow-authserver.service 2>/dev/null || true
  systemctl disable wow-worldserver.service wow-authserver.service 2>/dev/null || true
  rm -f /etc/systemd/system/wow-authserver.service /etc/systemd/system/wow-worldserver.service
  systemctl daemon-reload
  echo "systemd-сервисы удалены"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    start)            cmd_start ;;
    stop)             cmd_stop ;;
    restart)          cmd_restart ;;
    status)           cmd_status ;;
    start-auth)       require_bins; start_one authserver "$AUTH_BIN" "$AUTH_CONF" ;;
    start-world)      require_bins; start_one worldserver "$WORLD_BIN" "$WORLD_CONF" ;;
    stop-auth)        stop_one authserver "$AUTH_BIN" ;;
    stop-world)       stop_one worldserver "$WORLD_BIN" ;;
    watchdog)         cmd_watchdog ;;
    install-systemd)  install_systemd ;;
    uninstall-systemd) uninstall_systemd ;;
    -h|--help|help|"") usage ;;
    *) die "Неизвестная команда: $cmd (см. --help)" ;;
  esac
}

main "$@"
