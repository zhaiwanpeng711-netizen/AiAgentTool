#!/usr/bin/env bash
# Development mode: runs backend + frontend dev server concurrently
# Run this from YOUR OWN terminal (not inside Cursor IDE terminal)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env
if [ -f .env ]; then
  set -a; source .env; set +a
  echo "✓ Loaded .env"
fi

# Ensure venv and deps
if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  .venv/bin/pip install -q "uvicorn[standard]" websockets
  echo "✓ Python dependencies installed"
fi

cleanup() {
  echo -e "\nStopping services..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "Starting backend on :8000 ..."
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 2

echo "Starting frontend dev server on :5173 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  Dev Mode - AI Agent Scheduler"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  Ctrl+C to stop both"
echo "========================================"
echo ""

wait
