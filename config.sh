#!/usr/bin/env bash
# ============================================================
# Конфиг рестартера WoW 3.3.5 (OrstetCore / AzerothCore)
# При необходимости поправьте пути под свою установку.
# ============================================================

# Пользователь, от которого запускаются серверы
WOW_USER="${WOW_USER:-aizen}"

# Корень установленного сервера
SERVER_ROOT="${SERVER_ROOT:-/home/aizen/Server/Wotlk}"

BIN_DIR="${BIN_DIR:-$SERVER_ROOT/bin}"
ETC_DIR="${ETC_DIR:-$SERVER_ROOT/etc}"

# Логи и pid лежат рядом с рестартером
RESTARTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-$RESTARTER_ROOT/logs}"
PID_DIR="${PID_DIR:-$RESTARTER_ROOT/pids}"

AUTH_BIN="${AUTH_BIN:-$BIN_DIR/authserver}"
WORLD_BIN="${WORLD_BIN:-$BIN_DIR/worldserver}"

AUTH_CONF="${AUTH_CONF:-$ETC_DIR/authserver.conf}"
WORLD_CONF="${WORLD_CONF:-$ETC_DIR/worldserver.conf}"

# Пауза между попытками перезапуска при краше (секунды)
RESTART_DELAY="${RESTART_DELAY:-5}"

# Интервал проверки процессов в watchdog-режиме (секунды)
CHECK_INTERVAL="${CHECK_INTERVAL:-10}"

# Сколько секунд ждать «живой» процесс после старта
START_WAIT="${START_WAIT:-5}"

# Максимум рестартов подряд; 0 = без лимита
MAX_RESTARTS="${MAX_RESTARTS:-0}"
