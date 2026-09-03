#!/usr/bin/env bash
#
# run-mac.sh — one-command local dev runner for LedgerLens (macOS).
#
# What it does:
#   1. Makes sure Docker Desktop is running, then starts Postgres, Redis,
#      and Neo4j via docker compose (infra only — not the app containers).
#   2. Starts the FastAPI backend (uvicorn --reload) from backend/.venv.
#   3. Starts the Celery worker.
#   4. Starts the Vite frontend dev server from frontend/node_modules.
#   5. Opens the app in your browser and streams logs from all three.
#
# Press Ctrl+C to stop the backend/worker/frontend. Docker infra keeps
# running in the background (fast restarts) — stop it with:
#   docker compose down
#
set -euo pipefail
set -m  # each backgrounded job gets its own process group, so a stray Ctrl+Z
        # (SIGTSTP) at the terminal only affects this script, never the
        # backend/worker/frontend it started — they can't get stuck "stopped"
        # while still holding their ports.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/.run-logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api.log"
WORKER_LOG="$LOG_DIR/worker.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
: > "$API_LOG"; : > "$WORKER_LOG"; : > "$FRONTEND_LOG"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
info()  { echo "${BOLD}${GREEN}==>${RESET} $*"; }
warn()  { echo "${BOLD}${YELLOW}==>${RESET} $*"; }

PIDS=()
cleanup() {
  echo ""
  info "Stopping app processes..."
  # Each PID here is a process-group leader (thanks to `set -m`), so signal
  # the whole group (-$pid) to catch e.g. celery's prefork children and
  # uvicorn's reloader subprocess too — not just the direct child.
  for pid in "${PIDS[@]:-}"; do
    kill -TERM -- "-$pid" >/dev/null 2>&1 || kill "$pid" >/dev/null 2>&1 || true
  done
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    kill -KILL -- "-$pid" >/dev/null 2>&1 || true
  done
  wait 2>/dev/null || true
  info "Stopped. Docker infra (postgres/redis/neo4j) is still running."
  echo "    Stop it with: (cd \"$ROOT_DIR\" && docker compose down)"
}
trap cleanup EXIT INT TERM

# A Ctrl+Z here only suspends this script (children are protected by their
# own process groups, see `set -m` above) — but it's still confusing, so
# explain it once, then fall through to the normal stop-on-suspend behavior.
trap '
  warn "Ctrl+Z pauses run-mac.sh itself — the app keeps running in the background."
  echo "    Resume this script with: fg   /   Actually stop everything with: Ctrl+C"
  trap - TSTP; kill -TSTP $$
' TSTP

port_in_use() {
  lsof -iTCP -sTCP:LISTEN -P 2>/dev/null | grep -q ":$1 "
}

kill_stale() {
  # A previous run stopped uncleanly (Ctrl+Z'd and later killed, terminal
  # closed mid-run, etc.) can leave orphaned backend/worker/frontend
  # processes behind. Celery's worker pool also rewrites its own process
  # title via setproctitle, dropping the working-directory prefix — so
  # matching on the venv path alone can miss it. Match on distinctive,
  # app-specific substrings instead, scoped to this project.
  local any=0 pids
  for pattern in \
    "app.worker.celery_app worker" \
    "$BACKEND_DIR/.venv/bin/uvicorn app.main:app" \
    "$FRONTEND_DIR/node_modules/.bin/vite"
  do
    pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      any=1
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
  done
  if [ "$any" = 1 ]; then
    warn "Cleared stale processes left over from a previous run."
    sleep 1
  fi
}

ensure_postgres_user() {
  # backend/.env points at localhost:5432 — a homebrew Postgres, not the
  # docker-compose one — so the fraudmap role/db it expects may not exist yet.
  local pg_admin="${USER:-$(whoami)}"
  if ! psql -U "$pg_admin" -d postgres -c "SELECT 1 FROM pg_user WHERE usename = 'fraudmap'" 2>/dev/null | grep -q "1"; then
    info "Creating Postgres user 'fraudmap' and database 'fraudmap'..."
    psql -U "$pg_admin" -d postgres <<EOF
CREATE USER fraudmap WITH PASSWORD 'fraudmap';
CREATE DATABASE fraudmap OWNER fraudmap;
GRANT ALL PRIVILEGES ON DATABASE fraudmap TO fraudmap;
EOF
  fi
}

kill_stale

# ---------------------------------------------------------------------------
# 1. Docker + infra services (Postgres, Redis, Neo4j)
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required (Postgres/Redis/Neo4j run in containers) but was not found." >&2
  echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop/" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  info "Docker isn't running — starting Docker Desktop..."
  open -a Docker
  printf "    waiting for Docker to come up"
  for _ in $(seq 1 60); do
    docker info >/dev/null 2>&1 && break
    printf "."
    sleep 2
  done
  echo ""
  if ! docker info >/dev/null 2>&1; then
    echo "Docker Desktop didn't start in time. Start it manually and re-run this script." >&2
    exit 1
  fi
fi

info "Starting Postgres, Redis, Neo4j (docker compose)..."
(cd "$ROOT_DIR" && docker compose up -d --wait postgres redis neo4j)

# Ensure the fraudmap user exists in local postgres (if using homebrew postgres)
ensure_postgres_user

# ---------------------------------------------------------------------------
# 2. Backend (FastAPI + Celery)
# ---------------------------------------------------------------------------
if [ ! -d "$BACKEND_DIR/.venv" ]; then
  info "No backend/.venv found — creating it and installing dependencies..."
  (cd "$BACKEND_DIR" && python3 -m venv .venv)
  (cd "$BACKEND_DIR" && ".venv/bin/pip" install --quiet --upgrade pip)
  (cd "$BACKEND_DIR" && ".venv/bin/pip" install --quiet -r requirements.txt)
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  warn "backend/.env missing — copying from .env.example (fill in API keys later)."
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi

if port_in_use 8000; then
  warn "Port 8000 already in use — assuming the API is already running, skipping."
else
  info "Starting API (uvicorn) on :8000..."
  (cd "$BACKEND_DIR" && ".venv/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000) \
    >> "$API_LOG" 2>&1 &
  PIDS+=($!)
fi

info "Starting Celery worker..."
(cd "$BACKEND_DIR" && ".venv/bin/celery" -A app.worker.celery_app worker --loglevel=info) \
  >> "$WORKER_LOG" 2>&1 &
PIDS+=($!)

# ---------------------------------------------------------------------------
# 3. Frontend (Vite)
# ---------------------------------------------------------------------------
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  info "No frontend/node_modules found — running npm install..."
  (cd "$FRONTEND_DIR" && npm install)
fi

if [ ! -f "$FRONTEND_DIR/.env" ]; then
  warn "frontend/.env missing — copying from .env.example."
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
fi

if port_in_use 5173; then
  warn "Port 5173 already in use — assuming the frontend is already running, skipping."
else
  info "Starting frontend (vite) on :5173..."
  (cd "$FRONTEND_DIR" && npm run dev -- --host) >> "$FRONTEND_LOG" 2>&1 &
  PIDS+=($!)
fi

# ---------------------------------------------------------------------------
# 4. Open the app + stream logs
# ---------------------------------------------------------------------------
sleep 3
info "LedgerLens is up:"
echo "    Frontend:      http://localhost:5173  (investigator / changeme123)"
echo "    API docs:      http://localhost:8000/docs"
echo "    Neo4j browser: http://localhost:7474  (neo4j / fraudmap123)"
open "http://localhost:5173" >/dev/null 2>&1 || true

echo ""
info "Streaming logs (Ctrl+C to stop the app; infra keeps running)..."
tail -n +1 -f "$API_LOG" "$WORKER_LOG" "$FRONTEND_LOG" &
PIDS+=($!)

wait
