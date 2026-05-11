#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PREPARE_ONLY=false
if [ "${1:-}" = "--prepare-only" ]; then
  PREPARE_ONLY=true
  shift
fi

UPSTREAM_URL="${1:-$(cat "${REPO_ROOT}/UPSTREAM_URL")}"
UPSTREAM_VERSION="${2:-$(cat "${REPO_ROOT}/UPSTREAM_VERSION")}"
OUTPUT_DIR="${3:-${REPO_ROOT}/output}"
PREPARE_TAG="open-webui-rootpath-prepare:latest"
FULL_TAG="open-webui-rootpath:latest"

echo "=== Building prepare stage ==="
echo "  Upstream:  ${UPSTREAM_URL}"
echo "  Version:   ${UPSTREAM_VERSION}"
echo ""

docker build \
  --target prepare \
  --build-arg UPSTREAM_URL="${UPSTREAM_URL}" \
  --build-arg UPSTREAM_VERSION="${UPSTREAM_VERSION}" \
  -t "${PREPARE_TAG}" \
  "${REPO_ROOT}"

echo ""
echo "=== Extracting patched source ==="
CONTAINER_ID=$(docker create "${PREPARE_TAG}")
mkdir -p "${OUTPUT_DIR}"
docker cp "${CONTAINER_ID}:/upstream/." "${OUTPUT_DIR}/"
docker rm "${CONTAINER_ID}" >/dev/null

echo "=== Patched source extracted to ${OUTPUT_DIR} ==="

if [ "$PREPARE_ONLY" = false ]; then
  echo ""
  echo "=== Building full image ==="
  docker build \
    --build-arg UPSTREAM_URL="${UPSTREAM_URL}" \
    --build-arg UPSTREAM_VERSION="${UPSTREAM_VERSION}" \
    -t "${FULL_TAG}" \
    "${REPO_ROOT}"

  echo ""
  echo "=== Done. Run with: ==="
  echo "  docker run -e WEBUI_ROOT_PATH=/openwebui -p 8080:8080 ${FULL_TAG}"
else
  echo ""
  echo "=== Done (--prepare-only) ==="
  echo "To build the full image:"
  echo "  docker build --build-arg UPSTREAM_VERSION=\"\$(cat ${REPO_ROOT}/UPSTREAM_VERSION)\" -t ${FULL_TAG} \"${REPO_ROOT}\""
  echo ""
  echo "Then run with a root path:"
  echo "  docker run -e WEBUI_ROOT_PATH=/openwebui -p 8080:8080 ${FULL_TAG}"
fi