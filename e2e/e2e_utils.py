import os
import sys
import urllib.request
import urllib.error


def verify_routing_mode():
    mode = os.environ.get("E2E_MODE")
    if not mode:
        print("FATAL: E2E_MODE environment variable is not set.")
        print("       Set E2E_MODE=nginx or E2E_MODE=direct before running tests.")
        print("       Use e2e/run.sh which sets this automatically.")
        sys.exit(2)

    if mode not in ("nginx", "direct"):
        print(f"FATAL: E2E_MODE='{mode}' is invalid. Must be 'nginx' or 'direct'.")
        sys.exit(2)

    base_host = os.environ.get("E2E_BASE_HOST")
    root_path = os.environ.get("E2E_ROOT_PATH", "/openwebui")
    base_url_env = os.environ.get("E2E_BASE_URL")

    if not base_host and base_url_env:
        base_host = base_url_env.replace(f"{root_path}/", "").rstrip("/")
    elif not base_host:
        base_host = "http://nginx:80"

    url = f"{base_host}{root_path}/"
    print(f"Verifying E2E_MODE={mode} by checking {url} ...")

    try:
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=10)
        proxied_by = resp.headers.get("X-Proxied-By", "")
        server = resp.headers.get("Server", "")
        print(f"   X-Proxied-By: {proxied_by!r}")
        print(f"   Server: {server!r}")
    except urllib.error.HTTPError as e:
        proxied_by = e.headers.get("X-Proxied-By", "")
        server = e.headers.get("Server", "")
        print(f"   HTTP {e.code} — X-Proxied-By: {proxied_by!r}, Server: {server!r}")
    except Exception as e:
        print(f"FATAL: Could not reach {url}: {e}")
        sys.exit(2)

    if mode == "nginx":
        if proxied_by != "nginx":
            print(f"FATAL: E2E_MODE=nginx but X-Proxied-By='{proxied_by}' — traffic is NOT going through NGINX.")
            print(f"       Server header: {server!r}")
            print(f"       This usually means the test is accidentally reaching the app directly.")
            sys.exit(2)
        print("   PASS: NGINX routing confirmed (X-Proxied-By: nginx)")
    elif mode == "direct":
        if proxied_by == "nginx":
            print(f"FATAL: E2E_MODE=direct but X-Proxied-By='nginx' — traffic IS going through NGINX.")
            print(f"       Server header: {server!r}")
            print(f"       This usually means the test is accidentally going through the NGINX proxy.")
            sys.exit(2)
        print("   PASS: Direct routing confirmed (no X-Proxied-By header)")