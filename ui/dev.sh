#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BACKEND_PORT=8000
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend) BACKEND_PORT="$2"; shift 2 ;;
        *) echo "[WARNING] Unknown argument: $1"; shift ;;
    esac
done

echo "----------------------------------------"
echo "Starting GPTase UI dev server..."
echo "[INFO] Backend: http://localhost:${BACKEND_PORT}"
echo "----------------------------------------"

if ! command -v npm &> /dev/null; then
    echo "[ERROR] npm not found. Please install Node.js first."
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo "[INFO] Installing frontend dependencies..."
    npm install
fi

echo "[INFO] Starting Vite dev server (HMR enabled)..."
VITE_API_TARGET="http://localhost:${BACKEND_PORT}" npm run dev
