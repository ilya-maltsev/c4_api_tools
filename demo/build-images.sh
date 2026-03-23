#!/bin/bash
#
# Build, export and import Docker images for the demo environment.
#
# Usage:
#   cd demo && bash build-images.sh build     # build all images
#   cd demo && bash build-images.sh export    # export to c4-images.tar.gz
#   cd demo && bash build-images.sh import    # import from c4-images.tar.gz
#   cd demo && bash build-images.sh           # build + export
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCHIVE="${SCRIPT_DIR}/c4-images.tar.gz"
IMAGES="c4-nginx-gost:latest c4-config-exporter:latest c4-dashboard:latest"

build_images() {
    echo "=== Building c4-nginx-gost ==="
    docker build -t c4-nginx-gost:latest \
        -f "${REPO_ROOT}/dev_env/dev-nginx-gost/Dockerfile" \
        "${REPO_ROOT}/dev_env/dev-nginx-gost/"

    echo ""
    echo "=== Building c4-config-exporter ==="
    docker build -t c4-config-exporter:latest \
        -f "${REPO_ROOT}/dev_env/dev-c4-config-exporter/Dockerfile" \
        "${REPO_ROOT}/"

    echo ""
    echo "=== Building c4-dashboard ==="
    docker build -t c4-dashboard:latest \
        -f "${REPO_ROOT}/dev_env/dev-c4-dashboard/Dockerfile" \
        "${REPO_ROOT}/"

    echo ""
    echo "=== Images built ==="
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  c4-"
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
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  c4-"
    echo ""
    echo "Now run:  cd demo && docker compose up -d"
}

CMD="${1:-all}"

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
