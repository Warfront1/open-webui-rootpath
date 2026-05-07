#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

UPSTREAM_URL="${1:-$(cat "${REPO_ROOT}/UPSTREAM_URL")}"
UPSTREAM_VERSION="${2:-$(cat "${REPO_ROOT}/UPSTREAM_VERSION")}"
OUTPUT_DIR="${3:-${REPO_ROOT}/output}"
IMAGE_TAG="open-webui:latest"

echo "=== Building prepare stage ==="
echo "  Upstream:  ${UPSTREAM_URL}"
echo "  Version:   ${UPSTREAM_VERSION}"
echo ""

docker build \
  --target prepare \
  --build-arg UPSTREAM_URL="${UPSTREAM_URL}" \
  --build-arg UPSTREAM_VERSION="${UPSTREAM_VERSION}" \
  -t "${IMAGE_TAG}" \
  "${REPO_ROOT}"

echo ""
echo "=== Extracting patched source ==="
CONTAINER_ID=$(docker create "${IMAGE_TAG}")
mkdir -p "${OUTPUT_DIR}"
docker cp "${CONTAINER_ID}:/upstream/." "${OUTPUT_DIR}/"
docker rm "${CONTAINER_ID}" >/dev/null

echo "=== Done. Patched source at ${OUTPUT_DIR} ==="
echo ""
echo "To build the full image:"
echo "  docker build --build-arg UPSTREAM_VERSION=\"\$(cat ${REPO_ROOT}/UPSTREAM_VERSION)\" -t open-webui-rootpath:latest \"${REPO_ROOT}\""
echo ""
echo "Then run with a root path:"
echo "  docker run -e WEBUI_ROOT_PATH=/openwebui -p 8080:8080 open-webui-rootpath:latest"