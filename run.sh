#!/usr/bin/env bash
# ============================================================
# Observability Demo — 入口腳本
# 實際邏輯拆分在 scripts/ 目錄
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

help() {
    echo "Observability Demo — 本地測試 & 鏡像構建"
    echo ""
    echo "Usage: ./run.sh <command>"
    echo ""
    echo "Commands:"
    echo "  help                      顯示幫助"
    echo ""
    echo "  ── 本地測試（不依賴容器）───────────────────────"
    echo "  test-local    [all|backend|frontend|backend-quiet]  本地運行 (scripts/test-local.sh)"
    echo "  test-backend              本地運行後端"
    echo "  test-frontend             本地運行前端"
    echo "  test-backend-quiet        本地運行後端 (JSON 日誌)"
    echo ""
    echo "  ── Podman 容器測試 ────────────────────────────"
    echo "  test-podman   [quick|full|down]  容器運行 (scripts/test-podman.sh)"
    echo "  test-podman-quick          快速模式 — 僅 CRUD"
    echo "  test-podman-full           完整模式 — CRUD + Jaeger"
    echo "  test-podman-down           停止並清理"
    echo ""
    echo "  ── 鏡像構建推送 ────────────────────────────────"
    echo "  build-image  <registry> [tag]  構建並推送 (scripts/build-and-push-image.sh)"
    echo "  clean                    清理構建產物"
    echo ""
    echo "快捷命令 (保持兼容):"
    echo "  test-docker 系列 → 自動轉發到 test-podman"
}

# ── 轉發到子腳本 ──────────────────────────────────────────

main() {
    if [ $# -eq 0 ]; then
        help
        exit 0
    fi

    case "$1" in
        help|--help|-h)
            help
            ;;

        # ── 本地測試 ─────────────────────────────────
        test-local)
            shift
            "$SCRIPT_DIR/scripts/test-local.sh" "${@:-all}"
            ;;
        test-backend)
            "$SCRIPT_DIR/scripts/test-local.sh" backend
            ;;
        test-frontend)
            "$SCRIPT_DIR/scripts/test-local.sh" frontend
            ;;
        test-backend-quiet)
            "$SCRIPT_DIR/scripts/test-local.sh" backend-quiet
            ;;

        # ── Podman 容器測試 ──────────────────────────
        test-podman)
            shift
            "$SCRIPT_DIR/scripts/test-podman.sh" "${@:-help}"
            ;;
        test-podman-quick)
            "$SCRIPT_DIR/scripts/test-podman.sh" quick
            ;;
        test-podman-full)
            "$SCRIPT_DIR/scripts/test-podman.sh" full
            ;;
        test-podman-down)
            "$SCRIPT_DIR/scripts/test-podman.sh" down
            ;;
        # 兼容舊命令
        test-docker)
            "$SCRIPT_DIR/scripts/test-podman.sh" quick
            ;;
        test-docker-detached)
            "$SCRIPT_DIR/scripts/test-podman.sh" quick-detached
            ;;
        test-docker-full)
            "$SCRIPT_DIR/scripts/test-podman.sh" full
            ;;
        test-docker-full-detached)
            "$SCRIPT_DIR/scripts/test-podman.sh" full-detached
            ;;
        test-docker-down)
            "$SCRIPT_DIR/scripts/test-podman.sh" down
            ;;
        test-docker-full-down)
            "$SCRIPT_DIR/scripts/test-podman.sh" down
            ;;

        # ── 構建推送 ────────────────────────────────
        build-image)
            shift
            "$SCRIPT_DIR/scripts/build-and-push-image.sh" "$@"
            ;;

        # ── 清理 ────────────────────────────────────
        clean)
            info "Cleaning build artifacts..."
            rm -rf "$SCRIPT_DIR/backend/app/__pycache__" "$SCRIPT_DIR/backend/app/"*.pyc
            rm -rf "$SCRIPT_DIR/frontend/node_modules"
            rm -f "$SCRIPT_DIR/backend/todos.db"
            find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
            ok "Clean complete."
            ;;

        *)
            err "Unknown command: $1"
            echo ""
            help
            exit 1
            ;;
    esac
}

main "$@"
