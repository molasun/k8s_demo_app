#!/usr/bin/env bash
# ============================================================
# 本地測試 — 不依賴 Docker/Podman，直接運行前後端應用
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ── cleanup ────────────────────────────────────────────────
cleanup() {
    info "Cleaning up..."

    # 殺掉後臺進程
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
        ok "Backend stopped"
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
        ok "Frontend stopped"
    fi

    # 清理數據庫
    rm -f "$PROJECT_DIR/backend/todos.db"
    ok "Database cleaned"
}
trap cleanup EXIT

# ── start-backend ──────────────────────────────────────────
start-backend() {
    info "Starting Backend (Python FastAPI + uv)"
    echo "============================================="
    cd "$PROJECT_DIR"
    uv pip install -r backend/requirements.txt
    cd "$PROJECT_DIR/backend"
    DISABLE_OTEL=true \
    ENVIRONMENT=development \
    LOG_LEVEL=DEBUG \
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    ok "Backend PID: $BACKEND_PID"
}

# ── start-frontend ─────────────────────────────────────────
start-frontend() {
    info "Starting Frontend (Node.js Express)"
    echo "============================================="

    local wsl_node_modules="${NODE_MODULES_PATH:-$HOME/k8s_demo_app/frontend/node_modules}"
    if [ ! -d "$wsl_node_modules" ]; then
        info "Setting up node_modules in WSL native path: $wsl_node_modules"
        mkdir -p "$(dirname "$wsl_node_modules")"
        cp "$PROJECT_DIR/frontend/package.json" "$(dirname "$wsl_node_modules")/"
        (cd "$(dirname "$wsl_node_modules")" && npm install)
    fi

    cd "$PROJECT_DIR/frontend"
    DISABLE_OTEL=true \
    ENVIRONMENT=development \
    LOG_LEVEL=debug \
    BACKEND_URL=http://localhost:8000 \
    PORT=3000 \
    NODE_PATH="$wsl_node_modules" \
    node server.js &
    FRONTEND_PID=$!
    ok "Frontend PID: $FRONTEND_PID"
}

# ── help ───────────────────────────────────────────────────
help() {
    echo "Usage: ./scripts/test-local.sh [command]"
    echo ""
    echo "Commands:"
    echo "  all            同時啓動前端和後端"
    echo "  backend        只啓動後端 (http://localhost:8000/docs)"
    echo "  frontend       只啓動前端 (http://localhost:3000)"
    echo "  backend-quiet  後端 + JSON 日誌輸出"
    echo ""
    echo "Cleanup: 按 Ctrl+C 退出時會自動停止服務並清理數據庫"
}

# ── main ───────────────────────────────────────────────────
main() {
    local cmd="${1:-all}"
    case "$cmd" in
        all)
            start-backend
            sleep 2
            start-frontend
            ok "All services running. Press Ctrl+C to stop."
            ok "  Frontend:        http://localhost:3000"
            ok "  Backend API:     http://localhost:8000/docs"
            ok "  Backend metrics: http://localhost:8000/metrics"
            wait
            ;;
        backend)
            start-backend
            ok "Backend running at http://localhost:8000/docs. Ctrl+C to stop."
            wait
            ;;
        frontend)
            start-frontend
            ok "Frontend running at http://localhost:3000. Ctrl+C to stop."
            wait
            ;;
        backend-quiet)
            info "Starting Backend (JSON 日誌輸出)"
            cd "$PROJECT_DIR"
            uv pip install -r backend/requirements.txt
            cd "$PROJECT_DIR/backend"
            DISABLE_OTEL=true LOG_LEVEL=INFO \
            uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning
            ;;
        help|--help|-h)
            help
            ;;
        *)
            err "Unknown command: $cmd"
            help
            exit 1
            ;;
    esac
}

main "$@"
