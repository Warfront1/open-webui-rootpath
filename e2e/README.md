# E2E Test: Open WebUI under Root Path

Automated end-to-end test that verifies Open WebUI works correctly when deployed
behind an nginx reverse proxy at the `/openwebui` root path.

## What it tests

1. The app loads at `/openwebui/`
2. `__sveltekit` base path resolves to `/openwebui`
3. Onboarding/user-creation via the UI
4. Model selection from the dropdown
5. Sending a chat message and receiving a response
6. No unexpected JavaScript errors

## Prerequisites

- Docker and Docker Compose
- The Open WebUI root-path stack must be **already running** (`docker compose up -d`)

## Quick start

```bash
# From the repo root:

# 1. Build and launch the stack (if not already running)
docker compose build --no-cache
docker compose up -d

# 2. Run the E2E test
./e2e/run.sh
```

## Manual step-by-step

```bash
# 1. Start the Selenium Chrome container on the same Docker network
docker run -d --name selenium --network open-webui-rootpath_default --shm-size=2g selenium/standalone-chrome:latest

# 2. Install the Python selenium package inside the container
docker exec selenium pip3 install selenium

# 3. Copy the test script in and run it
docker cp e2e/test_rootpath.py selenium:/tmp/test_rootpath.py
docker exec selenium python3 /tmp/test_rootpath.py

# 4. Clean up
docker rm -f selenium
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `E2E_BASE_URL` | `http://nginx:80/openwebui/` | URL of the Open WebUI instance (inside Docker network) |
| `E2E_MODEL_KEYWORD` | `kimi` | Keyword to match in the model dropdown |
| `E2E_CHAT_MESSAGE` | `Say hello in one word` | Message to send in the chat |
| `E2E_RESPONSE_TIMEOUT` | `60` | Seconds to wait for the LLM response |

## Exit codes

- `0` — all checks passed
- `1` — one or more assertions failed
- `2` — fatal/unexpected error