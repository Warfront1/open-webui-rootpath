#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCREENSHOT_DIR="$SCRIPT_DIR/screenshots"
ROOT_PATH="${E2E_ROOT_PATH:-/openwebui}"
COMPOSE_NGINX="$SCRIPT_DIR/docker-compose.e2e-nginx.yml"
COMPOSE_DIRECT="$SCRIPT_DIR/docker-compose.e2e-direct.yml"
PROJECT_NAME="e2e"

mkdir -p "$SCREENSHOT_DIR"
chmod 777 "$SCREENSHOT_DIR"

echo "=== E2E Test: Open WebUI Root Path ==="
echo

wait_for_app() {
    local url="$1"
    local max_wait="${2:-60}"
    echo "   Waiting for app at $url ..."
    for i in $(seq 1 "$max_wait"); do
        if docker exec selenium curl -sf "$url" -o /dev/null 2>/dev/null; then
            echo "   App is ready (after ${i}s)."
            return 0
        fi
        sleep 1
    done
    echo "   ERROR: App did not become ready within ${max_wait}s at $url"
    return 1
}

cleanup() {
    echo "Cleaning up..."
    docker rm -f selenium 2>/dev/null || true
    docker compose -f "$COMPOSE_NGINX" -p "$PROJECT_NAME" down --remove-orphans 2>/dev/null || true
    docker compose -f "$COMPOSE_DIRECT" -p "$PROJECT_NAME-direct" down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

OVERALL_EXIT=0

# ═══════════════════════════════════════════════════════════════════
# Phase 1: Via NGINX (isolated on frontend/backend networks)
# ═══════════════════════════════════════════════════════════════════
echo "=== Phase 1: Testing via NGINX (port 80) ==="
echo

echo "Starting NGINX + Open WebUI stack..."
docker compose -f "$COMPOSE_NGINX" -p "$PROJECT_NAME" up -d --build --wait 2>/dev/null || {
    echo "ERROR: Failed to start NGINX compose stack."
    exit 1
}

NGINX_NETWORK="${PROJECT_NAME}_frontend"

echo "Starting Selenium Chrome container on network: $NGINX_NETWORK..."
docker rm -f selenium 2>/dev/null || true
docker run -d --name selenium --network "$NGINX_NETWORK" --shm-size=2g \
    -v "$SCREENSHOT_DIR:/tmp/e2e-screenshots" selenium/standalone-chrome:latest >/dev/null

echo "Waiting for Selenium to be ready..."
for i in $(seq 1 30); do
    if docker exec selenium curl -sf http://localhost:4444/wd/hub/status >/dev/null 2>&1; then
        echo "Selenium is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Selenium did not become ready in 30 seconds."
        exit 1
    fi
    sleep 2
done

docker exec selenium pip3 install selenium >/dev/null 2>&1

# Copy shared utilities into the container
docker cp "$SCRIPT_DIR/e2e_utils.py" selenium:/tmp/e2e_utils.py

wait_for_app "http://nginx:80${ROOT_PATH}/" 90

# ── Run all tests via NGINX ────────────────────────────────────────
echo
echo "Running main E2E test (nginx)..."
docker cp "$SCRIPT_DIR/test_rootpath.py" selenium:/tmp/test_rootpath.py
docker exec -e E2E_MODE=nginx -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e "E2E_BASE_URL=http://nginx:80${ROOT_PATH}/" -e E2E_BASE_HOST=http://nginx:80 \
    -e "E2E_ROOT_PATH=$ROOT_PATH" \
    selenium python3 /tmp/test_rootpath.py || OVERALL_EXIT=1

echo
echo "Running model profile image test (nginx)..."
docker cp "$SCRIPT_DIR/test_model_image.py" selenium:/tmp/test_model_image.py
docker exec -e E2E_MODE=nginx -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e E2E_BASE_HOST=http://nginx:80 -e "E2E_ROOT_PATH=$ROOT_PATH" \
    selenium python3 /tmp/test_model_image.py || OVERALL_EXIT=1

echo
echo "Running profile links test (nginx)..."
docker cp "$SCRIPT_DIR/test_profile_links.py" selenium:/tmp/test_profile_links.py
docker exec -e E2E_MODE=nginx -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e "E2E_BASE_URL=http://nginx:80${ROOT_PATH}/" -e E2E_BASE_HOST=http://nginx:80 \
    -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_profile_links.py || OVERALL_EXIT=1

echo
echo "Running admin settings links test (nginx)..."
docker cp "$SCRIPT_DIR/test_admin_settings.py" selenium:/tmp/test_admin_settings.py
docker exec -e E2E_MODE=nginx -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e "E2E_BASE_URL=http://nginx:80${ROOT_PATH}/" -e E2E_BASE_HOST=http://nginx:80 \
    -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_admin_settings.py || OVERALL_EXIT=1

# ── Tear down NGINX stack + Selenium ──────────────────────────────
echo
echo "Tearing down NGINX stack..."
docker rm -f selenium >/dev/null 2>&1 || true
docker compose -f "$COMPOSE_NGINX" -p "$PROJECT_NAME" down

# ═══════════════════════════════════════════════════════════════════
# Phase 2: Direct (bypassing NGINX, isolated on e2e network)
# ═══════════════════════════════════════════════════════════════════
echo
echo "=== Phase 2: Testing directly on port 8080 (bypassing NGINX) ==="
echo

echo "Starting Open WebUI stack (no NGINX)..."
docker compose -f "$COMPOSE_DIRECT" -p "$PROJECT_NAME-direct" up -d --build --wait 2>/dev/null || {
    echo "ERROR: Failed to start direct compose stack."
    exit 1
}

DIRECT_NETWORK="${PROJECT_NAME}-direct_e2e"

echo "Starting Selenium Chrome container on network: $DIRECT_NETWORK..."
docker rm -f selenium 2>/dev/null || true
docker run -d --name selenium --network "$DIRECT_NETWORK" --shm-size=2g \
    -v "$SCREENSHOT_DIR:/tmp/e2e-screenshots" selenium/standalone-chrome:latest >/dev/null

echo "Waiting for Selenium to be ready..."
for i in $(seq 1 30); do
    if docker exec selenium curl -sf http://localhost:4444/wd/hub/status >/dev/null 2>&1; then
        echo "Selenium is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Selenium did not become ready in 30 seconds."
        exit 1
    fi
    sleep 2
done

docker exec selenium pip3 install selenium >/dev/null 2>&1

# Copy shared utilities into the container
docker cp "$SCRIPT_DIR/e2e_utils.py" selenium:/tmp/e2e_utils.py

wait_for_app "http://open-webui:8080${ROOT_PATH}/" 90

# ── Run all tests directly ──────────────────────────────────────────
echo
echo "Running main E2E test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_rootpath.py" selenium:/tmp/test_rootpath.py
docker exec -e E2E_MODE=direct -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e "E2E_BASE_URL=http://open-webui:8080${ROOT_PATH}/" -e E2E_BASE_HOST=http://open-webui:8080 \
    -e "E2E_ROOT_PATH=$ROOT_PATH" \
    selenium python3 /tmp/test_rootpath.py || OVERALL_EXIT=1

echo
echo "Running model profile image test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_model_image.py" selenium:/tmp/test_model_image.py
docker exec -e E2E_MODE=direct -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e E2E_BASE_HOST=http://open-webui:8080 -e "E2E_ROOT_PATH=$ROOT_PATH" \
    selenium python3 /tmp/test_model_image.py || OVERALL_EXIT=1

echo
echo "Running profile links test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_profile_links.py" selenium:/tmp/test_profile_links.py
docker exec -e E2E_MODE=direct -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e "E2E_BASE_URL=http://open-webui:8080${ROOT_PATH}/" -e E2E_BASE_HOST=http://open-webui:8080 \
    -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_profile_links.py || OVERALL_EXIT=1

echo
echo "Running admin settings links test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_admin_settings.py" selenium:/tmp/test_admin_settings.py
docker exec -e E2E_MODE=direct -e SCREENSHOT_DIR=/tmp/e2e-screenshots \
    -e "E2E_BASE_URL=http://open-webui:8080${ROOT_PATH}/" -e E2E_BASE_HOST=http://open-webui:8080 \
    -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_admin_settings.py || OVERALL_EXIT=1

# ── Clean up ───────────────────────────────────────────────────────
echo
echo "Tearing down direct stack..."
docker rm -f selenium >/dev/null 2>&1 || true
docker compose -f "$COMPOSE_DIRECT" -p "$PROJECT_NAME-direct" down

if [ $OVERALL_EXIT -eq 0 ]; then
    echo
    echo "=== ALL CHECKS PASSED ==="
else
    echo
    echo "=== TESTS FAILED ==="
fi

exit $OVERALL_EXIT