# Open WebUI Root Path Support

Deploy [Open WebUI](https://github.com/open-webui/open-webui) under a URL prefix (e.g. `https://example.com/openwebui/`) behind a reverse proxy, controlled by a single `WEBUI_ROOT_PATH` environment variable.

## How It Works

Instead of forking open-webui and modifying source files, this overlay repo:

1. **Clones upstream** open-webui at a pinned version (inside Docker)
2. **Applies 3 small patches** to infrastructure files not covered by the transform script
3. **Injects 1 new file** — a Svelte preprocessor that automatically transforms all `.svelte` files at build time
4. **Runs a Python transform script** that applies backend and frontend config changes (env.py, main.py, models.py, svelte.config.js, vite.config.ts, constants.ts, layout, etc.)
5. **Builds the Docker image** with a sentinel root path (`/__WEBUI_ROOT_PATH__/`)
6. **At container startup**, an entrypoint script replaces the sentinel with the actual `WEBUI_ROOT_PATH` value

The root path is configured at **runtime** via the `WEBUI_ROOT_PATH` environment variable — no rebuild needed to change the path.

## Quick Start

### Build and run with Docker Compose

```bash
docker compose build
docker compose up -d
```

Open `http://localhost/openwebui/` in your browser (nginx serves on port 80).

### Change the root path

Set `WEBUI_ROOT_PATH` in your environment and recreate the container:

```bash
docker compose up -d -e WEBUI_ROOT_PATH=/myapp
```

Or edit `docker-compose.yml` and change the `WEBUI_ROOT_PATH` environment variable, then `docker compose up -d`.

No rebuild is required — the root path is configured at container startup.

> **Note:** The `nginx.conf` must also be updated to match the new root path. See the Nginx Example section.

### CUDA variant

```bash
docker build \
  --build-arg UPSTREAM_IMAGE=ghcr.io/open-webui/open-webui-cuda \
  -t open-webui-rootpath-cuda:latest .
```

Then run with a root path:

```bash
docker run -e WEBUI_ROOT_PATH=/openwebui -p 8080:8080 open-webui-rootpath-cuda:latest
```

### Extract patched source (optional)

If you need the patched source tree outside Docker (e.g. for debugging):

```bash
bash scripts/apply.sh [UPSTREAM_URL] [UPSTREAM_VERSION] [OUTPUT_DIR]
# Defaults: UPSTREAM_URL from UPSTREAM_URL file, UPSTREAM_VERSION from UPSTREAM_VERSION file, output to ./output
```

### Run tests

```bash
bash scripts/test.sh [UPSTREAM_URL] [UPSTREAM_VERSION] [OUTPUT_DIR]
```

## Configuration

### WEBUI_ROOT_PATH (runtime)

Set `WEBUI_ROOT_PATH` to the desired URL prefix at container startup:

- Must start with a leading slash (e.g. `/openwebui`)
- Must **not** end with a trailing slash
- Leave empty or set to `/` to serve at root path
- **No rebuild needed** — configured at runtime via environment variable

### Docker Build Args

| Arg | Default | Description |
|-----|---------|-------------|
| `UPSTREAM_IMAGE` | `ghcr.io/open-webui/open-webui` | Upstream Docker image to inherit runtime from |
| `UPSTREAM_URL` | `https://github.com/open-webui/open-webui.git` | Upstream git URL |
| `UPSTREAM_VERSION` | *(required)* | Upstream tag/branch/commit to build (read from `UPSTREAM_VERSION` file) |
| `BUILD_HASH` | `dev-build` | Build hash for version tracking |

### Nginx Example

```nginx
location /openwebui {
    proxy_pass http://open-webui:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Updating Upstream Version

1. Edit `UPSTREAM_VERSION` to the new tag/commit
2. Push to main — CI builds automatically
3. If CI fails, check the workflow logs for which patch failed
4. Fix the patch file or update `transforms/backend-rootpath.py`
5. Push the fix

## Architecture

| Path | Purpose |
|------|---------|
| `Dockerfile` | 3-stage build: prepare (patch), build (frontend), base (inherit upstream image) |
| `entrypoint.sh` | Runtime script that replaces the sentinel root path with the actual `WEBUI_ROOT_PATH` value |
| `patches/*.patch` | Unified diffs for upstream files not covered by the transform script (env example, Google Drive/OneDrive pickers) |
| `inject/src/lib/root-path-preprocess.js` | Svelte preprocessor (the core innovation) |
| `transforms/backend-rootpath.py` | Python script that applies backend and frontend config changes (replaces most patches) |
| `scripts/apply.sh` | Extract patched source via Docker |
| `UPSTREAM_VERSION` | Git ref to build against |
| `UPSTREAM_URL` | Git URL of upstream repo |

## What the Preprocessor Does

SvelteKit's `paths.base` config handles routing and static assets automatically. The preprocessor fixes what it doesn't:

- `goto('/...')` calls
- `href="/..."` attributes
- `location.href = '/...'` assignments
- `window.history.replaceState(...)` with absolute paths
- Image error fallback handlers
- Socket.IO path configuration

## Reference

- Reference branch: `jearly/subpath` on `github.com/jearlyno10/open-webui`
- SvelteKit `paths.base`: https://kit.svelte.dev/docs/configuration#paths
- Svelte preprocessor docs: https://kit.svelte.dev/docs/preprocessing