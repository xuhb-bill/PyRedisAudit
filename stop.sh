#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="${PID_FILE:-$APP_DIR/run/pyredisaudit.pid}"

if [[ ! -f "$PID_FILE" ]]; then
  echo "not running"
  exit 0
fi

PID="$(cat "$PID_FILE" || true)"
if [[ -z "${PID:-}" ]]; then
  rm -f "$PID_FILE"
  echo "not running"
  exit 0
fi

if ! kill -0 "$PID" >/dev/null 2>&1; then
  rm -f "$PID_FILE"
  echo "not running"
  exit 0
fi

kill "$PID" >/dev/null 2>&1 || true

for _ in {1..30}; do
  if ! kill -0 "$PID" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
    echo "stopped"
    exit 0
  fi
  sleep 1
done

kill -9 "$PID" >/dev/null 2>&1 || true
rm -f "$PID_FILE"
echo "stopped"

