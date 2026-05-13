# Open WebUI Root Path Support

Deploy [Open WebUI](https://github.com/open-webui/open-webui) under a URL prefix (e.g. `https://example.com/openwebui/`), controlled by a single `WEBUI_ROOT_PATH` environment variable.

**`WEBUI_ROOT_PATH`** — URL prefix (e.g. `/openwebui`). No trailing slash. Runtime config, no rebuild.

## Quick Start
```shell
docker run -d -p 80:8080 -e WEBUI_ROOT_PATH=/openwebui -e ENABLE_PERSISTENT_CONFIG=False -e WEBUI_AUTH=false warfront1owu/open-webui:latest
```
Navigate to `http://localhost/openwebui/` in your browser.

## Why not cut a PR against open-webui?
The core Open WebUI [team doesn't want this feature to be merged](https://github.com/open-webui/open-webui/pull/23242#issuecomment-4159269533).  
This repo intends to host a minimal, ideally fully automated solution, to keep up to date with upstream changes while adding Root Path support.  
We hope that the Open WebUI team will reconsider this feature in the future.

For development and architecture details, see [`DEVELOPERS.md`](DEVELOPERS.md).