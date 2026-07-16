#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
STATE_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID="$STATE_DIR/backend.pid"
FRONTEND_PID="$STATE_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

python_bin() {
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    echo "$VENV_DIR/bin/python"
  elif [[ -x "$VENV_DIR/Scripts/python" ]]; then
    echo "$VENV_DIR/Scripts/python"
  else
    echo ""
  fi
}

pip_bin() {
  if [[ -x "$VENV_DIR/bin/pip" ]]; then
    echo "$VENV_DIR/bin/pip"
  elif [[ -x "$VENV_DIR/Scripts/pip" ]]; then
    echo "$VENV_DIR/Scripts/pip"
  else
    echo ""
  fi
}

pid_is_running() {
  local pid_file="$1"

  [[ -f "$pid_file" ]] || return 1

  local pid
  pid="$(cat "$pid_file")"
  [[ -n "$pid" ]] || return 1

  kill -0 "$pid" >/dev/null 2>&1
}

port_is_free() {
  local host="$1"
  local port="$2"

  python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.2)
    sys.exit(1 if sock.connect_ex((host, port)) == 0 else 0)
PY
}

create_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating backend virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi
}

install_backend_deps() {
  local pip
  pip="$(pip_bin)"

  if [[ -z "$pip" ]]; then
    echo "Could not find pip in $VENV_DIR" >&2
    exit 1
  fi

  echo "Installing backend dependencies..."
  "$pip" install -r "$BACKEND_DIR/requirements.txt"
}

install_frontend_deps() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

setup_backend() {
  local python
  python="$(python_bin)"

  if [[ -z "$python" ]]; then
    echo "Could not find python in $VENV_DIR" >&2
    exit 1
  fi

  echo "Running database migrations..."
  "$python" "$BACKEND_DIR/manage.py" migrate

  echo "Seeding demo data..."
  "$python" "$BACKEND_DIR/manage.py" seed_demo

  echo "Ensuring local admin user exists..."
  "$python" "$BACKEND_DIR/manage.py" shell -c "from django.contrib.auth.models import User; u,_=User.objects.get_or_create(username='admin', defaults={'is_staff': True, 'is_superuser': True, 'is_active': True}); u.is_staff=True; u.is_superuser=True; u.is_active=True; u.set_password('admin1234'); u.save()"
}

bootstrap() {
  mkdir -p "$STATE_DIR" "$LOG_DIR"
  create_venv
  install_backend_deps
  install_frontend_deps
  setup_backend
}

start_backend() {
  if pid_is_running "$BACKEND_PID"; then
    echo "Backend is already running (PID $(cat "$BACKEND_PID"))."
    return
  fi
  if ! port_is_free "$BACKEND_HOST" "$BACKEND_PORT"; then
    echo "Backend port $BACKEND_HOST:$BACKEND_PORT is already in use." >&2
    echo "Use BACKEND_PORT=8001 $0 start, or stop the process using that port." >&2
    exit 1
  fi

  local python
  python="$(python_bin)"

  echo "Starting backend at http://$BACKEND_HOST:$BACKEND_PORT ..."
  nohup "$python" "$BACKEND_DIR/manage.py" runserver "$BACKEND_HOST:$BACKEND_PORT" --noreload >"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID"
  sleep 1
  if ! pid_is_running "$BACKEND_PID"; then
    echo "Backend failed to start. See $BACKEND_LOG" >&2
    exit 1
  fi
}

start_frontend() {
  if pid_is_running "$FRONTEND_PID"; then
    echo "Frontend is already running (PID $(cat "$FRONTEND_PID"))."
    return
  fi

  echo "Starting frontend at http://localhost:$FRONTEND_PORT ..."
  VITE_API_PROXY_TARGET="${VITE_API_PROXY_TARGET:-http://$BACKEND_HOST:$BACKEND_PORT}" \
    nohup npm --prefix "$FRONTEND_DIR" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID"
  sleep 1
  if ! pid_is_running "$FRONTEND_PID"; then
    echo "Frontend failed to start. See $FRONTEND_LOG" >&2
    exit 1
  fi
}

start() {
  bootstrap
  start_backend
  start_frontend

  echo
  echo "Started AI Innovator Web."
  echo "Frontend: http://localhost:$FRONTEND_PORT"
  echo "Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
  echo "Login:    admin / admin1234"
  echo "Logs:     $LOG_DIR"
}

stop_process() {
  local name="$1"
  local pid_file="$2"

  if ! pid_is_running "$pid_file"; then
    echo "$name is not running."
    rm -f "$pid_file"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"

  echo "Stopping $name (PID $pid)..."
  kill "$pid" >/dev/null 2>&1 || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$pid_file"
      return
    fi
    sleep 0.25
  done

  echo "$name did not stop gracefully; forcing shutdown..."
  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$pid_file"
}

stop() {
  stop_process "frontend" "$FRONTEND_PID"
  stop_process "backend" "$BACKEND_PID"
}

restart() {
  stop
  start
}

status() {
  if pid_is_running "$BACKEND_PID"; then
    echo "Backend:  running (PID $(cat "$BACKEND_PID"))"
  else
    echo "Backend:  stopped"
  fi

  if pid_is_running "$FRONTEND_PID"; then
    echo "Frontend: running (PID $(cat "$FRONTEND_PID"))"
  else
    echo "Frontend: stopped"
  fi
}

usage() {
  echo "Usage: $0 {start|stop|restart|status}"
  echo
  echo "Environment overrides:"
  echo "  BACKEND_HOST=$BACKEND_HOST"
  echo "  BACKEND_PORT=$BACKEND_PORT"
  echo "  FRONTEND_HOST=$FRONTEND_HOST"
  echo "  FRONTEND_PORT=$FRONTEND_PORT"
}

case "${1:-}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    restart
    ;;
  status)
    status
    ;;
  *)
    usage
    exit 1
    ;;
esac
