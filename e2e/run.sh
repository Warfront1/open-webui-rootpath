#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NETWORK="open-webui-rootpath_default"
SCREENSHOT_DIR="$SCRIPT_DIR/screenshots"
ROOT_PATH="${E2E_ROOT_PATH:-/openwebui}"

# Ensure local screenshot directory exists and is writable by the container user
mkdir -p "$SCREENSHOT_DIR"
chmod 777 "$SCREENSHOT_DIR"

echo "=== E2E Test: Open WebUI Root Path ==="
echo

# Check that the stack is running
if ! docker compose -f "$REPO_ROOT/docker-compose.yml" ps --format '{{.Name}}' 2>/dev/null | grep -q 'nginx'; then
    echo "ERROR: The stack does not appear to be running."
    echo "       Start it with: docker compose -f $REPO_ROOT/docker-compose.yml up -d"
    exit 1
fi

# Start Selenium container (remove first if it exists)
echo "Starting Selenium Chrome container..."
docker rm -f selenium 2>/dev/null || true
docker run -d --name selenium --network "$NETWORK" --shm-size=2g -v "$SCREENSHOT_DIR:/tmp/e2e-screenshots" selenium/standalone-chrome:latest >/dev/null

# Wait for Selenium to be ready
echo "Waiting for Selenium to be ready..."
for i in $(seq 1 30); do
    if docker exec selenium curl -s http://localhost:4444/wd/hub/status >/dev/null 2>&1; then
        echo "Selenium is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Selenium did not become ready in 30 seconds."
        docker rm -f selenium 2>/dev/null || true
        exit 1
    fi
    sleep 2
done

# Install selenium Python package
echo "Installing selenium Python package..."
docker exec selenium pip3 install selenium >/dev/null 2>&1

OVERALL_EXIT=0

# ── Via Nginx (port 80) ─────────────────────────────────────────────
echo "=== Running tests via Nginx (port 80) ==="
echo

# Copy and run the main test
echo "Running main E2E test (nginx)..."
docker cp "$SCRIPT_DIR/test_rootpath.py" selenium:/tmp/test_rootpath.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e E2E_ROOT_PATH="$ROOT_PATH" selenium python3 /tmp/test_rootpath.py || OVERALL_EXIT=1

# Copy and run the model profile image test
echo
echo "Running model profile image test (nginx)..."
docker cp "$SCRIPT_DIR/test_model_image.py" selenium:/tmp/test_model_image.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e E2E_BASE_HOST=http://nginx:80 -e E2E_ROOT_PATH="$ROOT_PATH" selenium python3 /tmp/test_model_image.py || OVERALL_EXIT=1

# Copy and run the profile links test
echo
echo "Running profile links test (nginx)..."
docker cp "$SCRIPT_DIR/test_profile_links.py" selenium:/tmp/test_profile_links.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e "E2E_BASE_URL=http://nginx:80${ROOT_PATH}/" -e E2E_BASE_HOST=http://nginx:80 -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_profile_links.py || OVERALL_EXIT=1

# Copy and run the admin settings links test
echo
echo "Running admin settings links test (nginx)..."
docker cp "$SCRIPT_DIR/test_admin_settings.py" selenium:/tmp/test_admin_settings.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e "E2E_BASE_URL=http://nginx:80${ROOT_PATH}/" -e E2E_BASE_HOST=http://nginx:80 -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_admin_settings.py || OVERALL_EXIT=1

# Stop Nginx so direct tests can't accidentally route through it
echo
echo "Stopping Nginx container for direct tests..."
docker compose -f "$REPO_ROOT/docker-compose.yml" stop nginx

# ── Direct (port 8080, bypassing Nginx) ─────────────────────────────
echo
echo "=== Running tests directly on port 8080 (bypassing Nginx) ==="
echo

# Copy and run the main test
echo "Running main E2E test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_rootpath.py" selenium:/tmp/test_rootpath.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e "E2E_BASE_URL=http://open-webui:8080${ROOT_PATH}/" -e E2E_ROOT_PATH="$ROOT_PATH" selenium python3 /tmp/test_rootpath.py || OVERALL_EXIT=1

# Copy and run the model profile image test
echo
echo "Running model profile image test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_model_image.py" selenium:/tmp/test_model_image.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e E2E_BASE_HOST=http://open-webui:8080 -e E2E_ROOT_PATH="$ROOT_PATH" selenium python3 /tmp/test_model_image.py || OVERALL_EXIT=1

# Copy and run the profile links test
echo
echo "Running profile links test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_profile_links.py" selenium:/tmp/test_profile_links.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e "E2E_BASE_URL=http://open-webui:8080${ROOT_PATH}/" -e E2E_BASE_HOST=http://open-webui:8080 -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_profile_links.py || OVERALL_EXIT=1

# Copy and run the admin settings links test
echo
echo "Running admin settings links test (direct 8080)..."
docker cp "$SCRIPT_DIR/test_admin_settings.py" selenium:/tmp/test_admin_settings.py
docker exec -e SCREENSHOT_DIR=/tmp/e2e-screenshots -e "E2E_BASE_URL=http://open-webui:8080${ROOT_PATH}/" -e E2E_BASE_HOST=http://open-webui:8080 -e "E2E_ROOT_PATH=$ROOT_PATH" selenium python3 /tmp/test_admin_settings.py || OVERALL_EXIT=1

# Restart Nginx to restore the stack
echo
echo "Restarting Nginx container..."
docker compose -f "$REPO_ROOT/docker-compose.yml" start nginx

# Clean up
echo "Cleaning up..."
docker rm -f selenium >/dev/null 2>&1 || true

if [ $OVERALL_EXIT -eq 0 ]; then
    echo
    echo "=== ALL CHECKS PASSED ==="
else
    echo
    echo "=== TESTS FAILED ==="
fi

exit $OVERALL_EXIT