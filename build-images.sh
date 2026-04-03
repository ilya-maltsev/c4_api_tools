#!/bin/bash
#
# Build, export and import Docker images for the DuckDB MCP server.
#
# Usage:
#   cd mcp-server-motherduck && bash build-images.sh           # build (default)
#   cd mcp-server-motherduck && bash build-images.sh build     # same as above
#   cd mcp-server-motherduck && bash build-images.sh export    # export to mcp-duckdb-images.tar.gz
#   cd mcp-server-motherduck && bash build-images.sh import    # import from mcp-duckdb-images.tar.gz
#   cd mcp-server-motherduck && bash build-images.sh all       # build + export
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCHIVE="${SCRIPT_DIR}/mcp-duckdb-images.tar.gz"
IMAGE="mcp-server-motherduck:latest"

build_images() {
    echo "=== Building ${IMAGE} ==="
    docker build \
        -f "${SCRIPT_DIR}/Dockerfile" \
        -t "${IMAGE}" \
        "${SCRIPT_DIR}/"

    echo ""
    echo "=== Images built ==="
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  mcp-server-motherduck"
}

export_images() {
    echo "=== Exporting images to ${ARCHIVE} ==="
    docker save ${IMAGE} | gzip > "${ARCHIVE}"
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
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" | grep -E "^  mcp-server-motherduck"
    echo ""
    echo "Now run:  docker compose up -d"
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
