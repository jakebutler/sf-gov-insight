#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYVENV=".venv-sfgov"
if [ ! -d "$PYVENV" ]; then
  echo "[dev] Creating Python venv at $PYVENV"
  python3 -m venv "$PYVENV"
fi

# Ensure backend deps are installed
"$PYVENV/bin/pip" install -r requirements.txt

# Start backend (FastAPI) in background
BACK_LOG=".dev-backend.log"
echo "[dev] Starting backend on http://localhost:8000 (logs: $BACK_LOG)"
"$PYVENV/bin/uvicorn" backend.api:app --host 0.0.0.0 --port 8000 --reload > "$BACK_LOG" 2>&1 &
BACK_PID=$!

echo "[dev] Backend PID: $BACK_PID"
cleanup() {
  echo "[dev] Stopping backend PID $BACK_PID"
  kill $BACK_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start frontend
if [ -d "web" ]; then
  cd web
  if [ ! -d "node_modules" ]; then
    echo "[dev] Installing web dependencies"
    npm install
  fi
  echo "[dev] Starting Vite dev server on http://127.0.0.1:5173"
  npm run dev
else
  echo "[dev] web/ directory not found" >&2
  exit 1
fi
