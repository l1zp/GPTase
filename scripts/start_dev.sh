#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$ROOT_DIR/ui"
LOG_DIR="$ROOT_DIR/logs"

HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8765}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$LOG_DIR"

if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found. Install Node.js first."
    exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python executable not found: $PYTHON_BIN"
    exit 1
fi

port_in_use() {
    local port="$1"
    "$PYTHON_BIN" -c '
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((host, port))
except OSError:
    sys.exit(0)
finally:
    sock.close()
sys.exit(1)
' "$HOST" "$port"
}

find_free_port() {
    local candidate="$1"
    while port_in_use "$candidate"; do
        candidate=$((candidate + 1))
    done
    echo "$candidate"
}

BACKEND_PORT="$(find_free_port "$BACKEND_PORT")"
FRONTEND_PORT="$(find_free_port "$FRONTEND_PORT")"

if [ ! -d "$UI_DIR/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd "$UI_DIR" && npm install)
fi

if command -v gptase >/dev/null 2>&1; then
    BACKEND_CMD=(gptase web --host "$HOST" --port "$BACKEND_PORT")
else
    BACKEND_CMD=("$PYTHON_BIN" -m gptase.main web --host "$HOST" --port "$BACKEND_PORT")
fi

cleanup() {
    local exit_code=$?

    if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
        kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    fi

    if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        kill "$BACKEND_PID" >/dev/null 2>&1 || true
    fi

    wait >/dev/null 2>&1 || true
    exit "$exit_code"
}

trap cleanup INT TERM EXIT

echo "Starting backend on http://$HOST:$BACKEND_PORT"
(
    cd "$ROOT_DIR"
    export BROWSER=/bin/false
    "${BACKEND_CMD[@]}"
) >"$LOG_DIR/backend-dev.log" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend on http://$HOST:$FRONTEND_PORT"
(
    cd "$UI_DIR"
    VITE_API_TARGET="http://127.0.0.1:$BACKEND_PORT" \
        npm run dev -- --host "$HOST" --port "$FRONTEND_PORT"
) >"$LOG_DIR/frontend-dev.log" 2>&1 &
FRONTEND_PID=$!

echo "Frontend logs: $LOG_DIR/frontend-dev.log"
echo "Backend logs:  $LOG_DIR/backend-dev.log"
echo "Press Ctrl+C to stop both services."

while true; do
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        echo "Backend exited. Shutting down frontend."
        break
    fi

    if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
        echo "Frontend exited. Shutting down backend."
        break
    fi

    sleep 1
done
