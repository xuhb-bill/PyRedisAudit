#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

mkdir -p "$APP_DIR/run" "$APP_DIR/logs"

PID_FILE="${PID_FILE:-$APP_DIR/run/pyredisaudit.pid}"
CONFIG_FILE="${CONFIG_FILE:-$APP_DIR/config/default_config.yaml}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
LOG_FILE="${LOG_FILE:-$APP_DIR/logs/audit.log}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
STDOUT_LOG="${STDOUT_LOG:-$APP_DIR/logs/stdout.log}"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" >/dev/null 2>&1; then
    echo "already running: pid=$PID"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

nohup python3 "$APP_DIR/app.py" \
  --config "$CONFIG_FILE" \
  --host "$HOST" \
  --port "$PORT" \
  --log-file "$LOG_FILE" \
  --log-level "$LOG_LEVEL" \
  >>"$STDOUT_LOG" 2>&1 &

echo $! >"$PID_FILE"
echo "started: pid=$(cat "$PID_FILE") host=$HOST port=$PORT"

