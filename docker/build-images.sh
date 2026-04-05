#!/bin/bash
#
# Build, export and import Docker images for the DuckDB MCP server.
#
# Usage:
#   cd mcp-server-motherduck/docker && bash build-images.sh           # build (default)
#   cd mcp-server-motherduck/docker && bash build-images.sh build     # same
#   cd mcp-server-motherduck/docker && bash build-images.sh export    # export to mcp-duckdb-images.tar.gz
#   cd mcp-server-motherduck/docker && bash build-images.sh import    # import from mcp-duckdb-images.tar.gz
#   cd mcp-server-motherduck/docker && bash build-images.sh all       # build + export
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARCHIVE="${SCRIPT_DIR}/mcp-duckdb-images.tar.gz"
MCP_IMAGE="mcp-server-motherduck:latest"
NGINX_IMAGE="nginx:alpine"
IMAGES="${MCP_IMAGE} ${NGINX_IMAGE}"

build_images() {
    echo "=== Pulling ${NGINX_IMAGE} ==="
    docker pull "${NGINX_IMAGE}"

    echo ""
    echo "=== Building ${MCP_IMAGE} ==="
    docker build \
        -f "${SCRIPT_DIR}/Dockerfile" \
        -t "${MCP_IMAGE}" \
        "${REPO_ROOT}/"

    echo ""
    echo "=== Images built ==="
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  (mcp-server-motherduck|nginx)"
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
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  (mcp-server-motherduck|nginx)"
    echo ""
    echo "Now run:  cd docker && docker compose up -d"
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
