from open_webui.env import WEBUI_ROOT_PATH


class PathPrefixStripMiddleware:
    """ASGI middleware that strips WEBUI_ROOT_PATH from incoming request paths.

    This allows the app to be deployed behind a reverse proxy that routes
    requests to /openwebui/... without the proxy needing to strip the prefix
    itself. The frontend generates URLs prefixed with WEBUI_ROOT_PATH, and
    this middleware strips it before FastAPI routing sees the request.

    When WEBUI_ROOT_PATH is empty, this middleware is a no-op.

    Note: We do NOT set scope["root_path"] here because Starlette's
    get_route_path() assumes root_path is a prefix of path, which breaks
    mount matching. The app uses WEBUI_ROOT_PATH directly for URL generation.
    """

    def __init__(self, app):
        self.app = app
        self.prefix = WEBUI_ROOT_PATH.rstrip("/") if WEBUI_ROOT_PATH else ""

    async def __call__(self, scope, receive, send):
        if self.prefix and scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "")
            if path.startswith(self.prefix + "/") or path == self.prefix:
                scope["path"] = path[len(self.prefix):] or "/"
                raw_path = scope.get("raw_path", b"")
                prefix_bytes = self.prefix.encode("utf-8")
                if raw_path.startswith(prefix_bytes + b"/") or raw_path == prefix_bytes:
                    scope["raw_path"] = raw_path[len(prefix_bytes):] or b"/"
        await self.app(scope, receive, send)