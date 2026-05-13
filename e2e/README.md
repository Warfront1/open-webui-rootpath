# E2E Test: Open WebUI under Root Path

Automated end-to-end test that verifies Open WebUI works correctly when deployed
behind an nginx reverse proxy at the `/openwebui` root path, and also when accessed
directly (bypassing nginx).

## What it tests

1. The app loads at `/openwebui/`
2. `__sveltekit` base path resolves to `/openwebui`
3. Onboarding/user-creation via the UI
4. Model selection from the dropdown
5. Sending a chat message and receiving a response
6. No unexpected JavaScript errors
7. Model profile image redirects include the root path prefix
8. Admin settings page links include the root path prefix
9. User profile menu links include the root path prefix

## Routing isolation

Each test phase runs in a fully isolated Docker network to prevent misrouting:

- **NGINX phase**: Uses `docker-compose.e2e-nginx.yml`. The Selenium container is on
  the `frontend` network, which only has access to the `nginx` service — it **cannot**
  reach `open-webui` directly. A response header guard (`X-Proxied-By: nginx`) confirms
  traffic flows through NGINX.

- **Direct phase**: Uses `docker-compose.e2e-direct.yml`. No nginx container exists at
  all. The Selenium container is on the `e2e` network with only `open-webui`. The
  response header guard confirms `X-Proxied-By` is absent, verifying traffic goes
  directly to the app.

If a test is accidentally configured with the wrong URL (e.g., targeting `nginx:80`
during the direct phase, or `open-webui:8080` during the NGINX phase), the connection
will simply fail — it is impossible for tests to silently route through the wrong path.

## Quick start

```bash
# From the repo root:
./e2e/run.sh
```

This script handles everything: building the Docker images, starting isolated compose
stacks, running Selenium, executing all tests in both modes, and tearing down.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `E2E_MODE` | *(required)* | Must be `nginx` or `direct`. Set automatically by `run.sh`. |
| `E2E_BASE_URL` | `http://nginx:80/openwebui/` | URL of the Open WebUI instance (inside Docker network) |
| `E2E_BASE_HOST` | `http://nginx:80` | Base host for tests that construct URLs from parts |
| `E2E_ROOT_PATH` | `/openwebui` | Root path prefix |
| `E2E_MODEL_KEYWORD` | `minimax-m2` | Keyword to match in the model dropdown |
| `E2E_MODEL_WAIT_TIMEOUT` | `8` | Seconds to wait for the target model to appear |
| `E2E_CHAT_MESSAGE` | `Say hello in one word` | Message to send in the chat |
| `E2E_RESPONSE_TIMEOUT` | `20` | Seconds to wait for the LLM response |

## Exit codes

- `0` — all checks passed
- `1` — one or more assertions failed
- `2` — fatal/unexpected error (including routing guard failure)