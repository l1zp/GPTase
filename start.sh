#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BACKEND_PORT=8000
BACKEND_HOST=127.0.0.1

echo "----------------------------------------"
echo "Starting GPTase (backend + frontend)..."
echo "----------------------------------------"

# Start backend
echo "[INFO] Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
conda run -n llm gptase web --port "$BACKEND_PORT" --host "$BACKEND_HOST" &
BACKEND_PID=$!
echo "[INFO] Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "[INFO] Waiting for backend..."
for i in $(seq 1 20); do
    if curl -sf "http://${BACKEND_HOST}:${BACKEND_PORT}/api/agents" > /dev/null 2>&1; then
        echo "[OK] Backend ready."
        break
    fi
    sleep 1
    if [ "$i" -eq 20 ]; then
        echo "[ERROR] Backend did not start in time."
        kill "$BACKEND_PID" 2>/dev/null
        exit 1
    fi
done

# Start frontend (foreground — Ctrl+C will stop both)
trap 'echo "[INFO] Shutting down..."; kill "$BACKEND_PID" 2>/dev/null' EXIT INT TERM

echo "[INFO] Starting frontend dev server..."
echo "----------------------------------------"
echo "  Backend : http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "  Frontend: http://localhost:5173"
echo "  (Ctrl+C to stop both)"
echo "----------------------------------------"

VITE_API_TARGET="http://${BACKEND_HOST}:${BACKEND_PORT}" bash ui/dev.sh
