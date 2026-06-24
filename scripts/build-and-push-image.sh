#!/usr/bin/env bash
# ============================================================
# 構建鏡像並推送到指定鏡像倉庫
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

# ── 默認值 ─────────────────────────────────────────────────
ENGINE="${BUILD_ENGINE:-podman}"
TAG="${TAG:-latest}"
SKIP_PUSH="${SKIP_PUSH:-false}"

# ── help ───────────────────────────────────────────────────
help() {
    echo "Usage: ./scripts/build-and-push-image.sh <registry> [tag] [options]"
    echo ""
    echo "參數:"
    echo "  registry    必需: 鏡像倉庫地址 (例: quay.io/yourorg)"
    echo "  tag         可選: 鏡像標籤，默認 'latest'"
    echo ""
    echo "選項:"
    echo "  --engine=<podman|docker>  構建引擎，默認 podman"
    echo "  --build-only              只構建不推送"
    echo ""
    echo "示例:"
    echo "  ./scripts/build-and-push-image.sh quay.io/myorg v1.0.0"
    echo "  ./scripts/build-and-push-image.sh quay.io/myorg --build-only"
    echo "  ./scripts/build-and-push-image.sh quay.io/myorg --engine=docker"
    echo ""
    echo "環境變量:"
    echo "  BUILD_ENGINE  構建引擎 (默認: podman)"
    echo "  TAG           鏡像標籤 (默認: latest)"
}

# ── build ──────────────────────────────────────────────────
build() {
    local registry="$1"
    local backend_img="${registry}/observability-demo-backend:${TAG}"
    local frontend_img="${registry}/observability-demo-frontend:${TAG}"

    # 檢查引擎
    if ! command -v "$ENGINE" &>/dev/null; then
        err "構建引擎 '$ENGINE' 未安裝。請安裝 podman 或 docker。"
        exit 1
    fi

    info "Building backend image..."
    cd "$PROJECT_DIR/backend"
    $ENGINE build -t "$backend_img" .
    ok "Backend image built: $backend_img"

    info "Building frontend image..."
    cd "$PROJECT_DIR/frontend"
    $ENGINE build -t "$frontend_img" .
    ok "Frontend image built: $frontend_img"

    # 推送
    if [ "$SKIP_PUSH" != "true" ]; then
        info "Pushing backend image..."
        $ENGINE push "$backend_img"
        ok "Backend image pushed: $backend_img"

        info "Pushing frontend image..."
        $ENGINE push "$frontend_img"
        ok "Frontend image pushed: $frontend_img"
    else
        info "Skipping push (--build-only)"
    fi

    echo ""
    ok "Done!"
    echo "  Backend:  $backend_img"
    echo "  Frontend: $frontend_img"
}

# ── main ───────────────────────────────────────────────────
main() {
    if [ $# -lt 1 ]; then
        err "Missing required argument: <registry>"
        echo ""
        help
        exit 1
    fi

    local registry=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --engine=*)    ENGINE="${1#*=}" ;;
            --build-only)  SKIP_PUSH="true" ;;
            --help|-h)     help; exit 0 ;;
            -*)
                err "Unknown option: $1"
                help
                exit 1
                ;;
            *)
                if [ -z "$registry" ]; then
                    registry="$1"
                else
                    TAG="$1"
                fi
                ;;
        esac
        shift
    done

    if [ -z "$registry" ]; then
        err "registry is required"
        exit 1
    fi

    build "$registry"
}

main "$@"
