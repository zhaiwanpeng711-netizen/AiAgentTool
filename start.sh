#!/usr/bin/env bash
# AI Agent Scheduler - One-command startup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo "✓ Loaded .env"
fi

# Check venv
if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  echo "✓ Python dependencies installed"
fi

# Build frontend if dist is missing or outdated
if [ ! -d frontend/dist ] || [ frontend/src -nt frontend/dist ]; then
  echo "Building frontend..."
  cd frontend
  npm install --silent
  npm run build --silent
  cd ..
  echo "✓ Frontend built"
fi

echo ""
echo "========================================"
echo "  AI Agent Scheduler"
echo "  Backend:  http://localhost:${PORT:-8000}"
echo "  API Docs: http://localhost:${PORT:-8000}/docs"
echo "  Frontend: http://localhost:${PORT:-8000}"
echo "========================================"
echo ""

# Start backend (serves built frontend too)
.venv/bin/python -m uvicorn backend.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}" \
  --reload
