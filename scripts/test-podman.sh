#!/usr/bin/env bash
# ============================================================
# Podman 容器測試 — 使用 Podman 替代 Docker 本地運行
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

PODMAN="podman"
PODMAN_COMPOSE="${PODMAN} compose"

# ── cleanup ────────────────────────────────────────────────
cleanup() {
    info "Cleaning up..."
    cd "$PROJECT_DIR"
    $PODMAN_COMPOSE down --remove-orphans 2>/dev/null || true
    $PODMAN_COMPOSE --profile full down --remove-orphans 2>/dev/null || true
    ok "Containers stopped and removed"
}
trap cleanup EXIT

# ── check-podman ───────────────────────────────────────────
check-podman() {
    if ! command -v podman &>/dev/null; then
        err "podman is not installed. Please install it first:"
        echo "  https://podman.io/docs/installation"
        exit 1
    fi
    info "Podman version: $(podman --version)"
}

# ── test-quick ─────────────────────────────────────────────
test-quick() {
    info "快速模式 — 僅驗證 CRUD（無 OTel 追蹤）"
    check-podman
    cd "$PROJECT_DIR"
    $PODMAN_COMPOSE up --build
}

# ── test-quick-detached ────────────────────────────────────
test-quick-detached() {
    info "快速模式 — 後臺運行"
    check-podman
    cd "$PROJECT_DIR"
    $PODMAN_COMPOSE up --build -d
    echo ""
    ok "Services running (快速模式 — 無 OTel):"
    echo "  Frontend:        http://localhost:3000"
    echo "  Backend API:     http://localhost:8000/docs"
    echo "  Backend metrics: http://localhost:8000/metrics"
    echo ""
    echo "Stop with: ./scripts/test-podman.sh down"
    echo "Press Ctrl+C to stop and cleanup."
    wait
}

# ── test-full ──────────────────────────────────────────────
test-full() {
    info "完整模式 — CRUD + 全鏈路追蹤 (Jaeger: :16686)"
    check-podman
    cd "$PROJECT_DIR"
    $PODMAN_COMPOSE --profile full up --build
}

# ── test-full-detached ────────────────────────────────────
test-full-detached() {
    info "完整模式 — 後臺運行"
    check-podman
    cd "$PROJECT_DIR"
    $PODMAN_COMPOSE --profile full up --build -d
    echo ""
    ok "Services running (完整模式 — 含全鏈路追蹤):"
    echo "  Frontend:        http://localhost:3000"
    echo "  Backend API:     http://localhost:8000/docs"
    echo "  Backend metrics: http://localhost:8000/metrics"
    echo "  Jaeger UI:       http://localhost:16686"
    echo ""
    echo "Stop with: ./scripts/test-podman.sh down"
    echo "Press Ctrl+C to stop and cleanup."
    wait
}

# ── down ────────────────────────────────────────────────────
down() {
    info "停止所有 Podman 服務..."
    cd "$PROJECT_DIR"
    $PODMAN_COMPOSE down --remove-orphans 2>/dev/null || true
    $PODMAN_COMPOSE --profile full down --remove-orphans 2>/dev/null || true
    ok "All services stopped."
}

# ── help ───────────────────────────────────────────────────
help() {
    echo "Usage: ./scripts/test-podman.sh [command]"
    echo ""
    echo "Commands:"
    echo "  quick             快速模式 — 僅驗證 CRUD（前臺運行，Ctrl+C 清理）"
    echo "  quick-detached    快速模式 — 後臺運行"
    echo "  full              完整模式 — CRUD + Jaeger 全鏈路追蹤"
    echo "  full-detached     完整模式 — 後臺運行"
    echo "  down              停止並清理所有服務"
    echo ""
    echo "Podman 替代 Docker: docker compose → podman compose"
}

# ── main ───────────────────────────────────────────────────
main() {
    local cmd="${1:-help}"
    case "$cmd" in
        quick)               test-quick ;;
        quick-detached)      test-quick-detached ;;
        full)                test-full ;;
        full-detached)       test-full-detached ;;
        down)                down ;;
        help|--help|-h)      help ;;
        *)
            err "Unknown command: $cmd"
            help
            exit 1
            ;;
    esac
}

main "$@"
