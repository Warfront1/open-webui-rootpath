from starlette.datastructures import MutableHeaders

from open_webui.env import WEBUI_ROOT_PATH


class PathPrefixStripMiddleware:
    """ASGI middleware that strips WEBUI_ROOT_PATH from incoming request paths
    and re-adds it to client-facing root-relative redirect Locations.

    This allows the app to be deployed behind a reverse proxy that routes
    requests to /openwebui/... without the proxy needing to strip the prefix
    itself. The frontend generates URLs prefixed with WEBUI_ROOT_PATH, and
    this middleware strips it before FastAPI routing sees the request.

    Response Location headers the backend builds from already-stripped
    request paths (redirect_slashes 307s, static-asset redirects, proxied
    redirects) are prefixed again on the way out, since the browser resolves
    root-relative Locations against the origin, not the deployment root.

    When WEBUI_ROOT_PATH is empty, this middleware is a no-op.

    Note: We do NOT set scope["root_path"] here because Starlette's
    get_route_path() assumes root_path is a prefix of path, which breaks
    mount matching. The app uses WEBUI_ROOT_PATH directly for URL generation.
    """

    def __init__(self, app):
        self.app = app
        self.prefix = WEBUI_ROOT_PATH.rstrip("/") if WEBUI_ROOT_PATH else ""

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket") and self.prefix:
            path = scope.get("path", "")
            if path.startswith(self.prefix + "/") or path == self.prefix:
                scope["path"] = path[len(self.prefix):] or "/"
                raw_path = scope.get("raw_path", b"")
                prefix_bytes = self.prefix.encode("utf-8")
                if raw_path.startswith(prefix_bytes + b"/") or raw_path == prefix_bytes:
                    scope["raw_path"] = raw_path[len(prefix_bytes):] or b"/"

        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_prefixed_location(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                location = headers.get("location")
                if (
                    location
                    and location.startswith("/")
                    and not location.startswith("//")
                    and not (
                        location == self.prefix or location.startswith(self.prefix + "/")
                    )
                ):
                    headers["location"] = f"{self.prefix}{location}"
            await send(message)

        await self.app(scope, receive, send_with_prefixed_location)