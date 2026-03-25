#!/bin/bash
#
# Build, export and import Docker images for the demo environment.
#
# Usage:
#   cd demo && bash build-images.sh           # build all images (default)
#   cd demo && bash build-images.sh build     # same as above
#   cd demo && bash build-images.sh export    # export to c4-images.tar.gz
#   cd demo && bash build-images.sh import    # import from c4-images.tar.gz
#   cd demo && bash build-images.sh all       # build + export
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCHIVE="${SCRIPT_DIR}/c4-images.tar.gz"
IMAGES="postgres:16 c4-nginx-gost:latest c4-dashboard:latest"

build_images() {
    echo "=== Pulling postgres:16 ==="
    docker pull postgres:16

    echo ""
    echo "=== Building c4-nginx-gost ==="
    docker build -t c4-nginx-gost:latest \
        -f "${REPO_ROOT}/dev_env/nginx/Dockerfile" \
        "${REPO_ROOT}/dev_env/nginx/"

    echo ""
    echo "=== Building c4-dashboard ==="
    docker build -t c4-dashboard:latest \
        -f "${REPO_ROOT}/dev_env/dashboard/Dockerfile" \
        "${REPO_ROOT}/"

    echo ""
    echo "=== Images built ==="
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  (c4-|postgres)"
}

export_images() {
    echo "=== Exporting images to ${ARCHIVE} ==="
    docker save ${IMAGES} | gzip > "${ARCHIVE}"
    echo "  $(du -h "${ARCHIVE}" | cut -f1)  ${ARCHIVE}"
    echo "=== Export done ==="
}

import_images() {
    if [ ! -f "${ARCHIVE}" ]; then
        echo "ERROR: ${ARCHIVE} not found."
        echo "Run '$(basename "$0") export' first or copy the archive here."
        exit 1
    fi
    echo "=== Importing images from ${ARCHIVE} ==="
    gunzip -c "${ARCHIVE}" | docker load
    echo ""
    echo "=== Images loaded ==="
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  (c4-|postgres)"
    echo ""
    echo "Now run:  cd demo && docker compose up -d"
}

CMD="${1:-build}"

case "${CMD}" in
    build)
        build_images
        ;;
    export)
        export_images
        ;;
    import)
        import_images
        ;;
    all)
        build_images
        echo ""
        export_images
        ;;
    *)
        echo "Usage: $(basename "$0") {build|export|import|all}"
        exit 1
        ;;
esac
