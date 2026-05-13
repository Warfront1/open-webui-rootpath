#!/usr/bin/env python3
"""
Applies WEBUI_ROOT_PATH changes to backend Python files and frontend config
files. The root-path-preprocess Svelte preprocessor handles most frontend path
rewrites, but SvelteKit's build optimizer can inline `base` to an empty string
inside object literals, so some layout-specific transforms are still needed here.

Usage: python3 transforms/backend-rootpath.py /path/to/upstream/clone [WEBUI_ROOT_PATH]
"""
import sys
import os
import re


def insert_import_after_future(content, import_line):
    """Insert an import line after any from __future__ imports and module docstrings."""
    pattern = r'^((?:(?:""".*?"""|\'\'\'.*?\'\'\')\n*)?(?:from __future__ import [^\n]+\n)*)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        end = match.end()
        return content[:end] + import_line + '\n' + content[end:]
    return import_line + '\n' + content


def transform_env_py(path):
    filepath = os.path.join(path, 'backend/open_webui/env.py')
    with open(filepath, 'r') as f:
        content = f.read()

    if 'WEBUI_ROOT_PATH' in content:
        print(f"  [skip] {filepath} — WEBUI_ROOT_PATH already present")
        return

    insertion = """

####################################
# WEBUI_ROOT_PATH
####################################

# Optional URL root path prefix for reverse-proxy deployments (e.g. "/openwebui").
# Must start with a leading slash and must not end with a trailing slash.
# Leave empty to serve at the root path.
WEBUI_ROOT_PATH = os.environ.get('WEBUI_ROOT_PATH', '')
"""

    content = content.replace(
        "WEBUI_BUILD_HASH = os.environ.get('WEBUI_BUILD_HASH', 'dev-build')",
        "WEBUI_BUILD_HASH = os.environ.get('WEBUI_BUILD_HASH', 'dev-build')" + insertion
    )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_main_py(path):
    filepath = os.path.join(path, 'backend/open_webui/main.py')
    with open(filepath, 'r') as f:
        content = f.read()

    if "PathPrefixStripMiddleware" in content:
        print(f"  [skip] {filepath} — PathPrefixStripMiddleware already present")
        return

    content = content.replace(
        "    ENABLE_EASTER_EGGS,\n    LOG_FORMAT,",
        "    ENABLE_EASTER_EGGS,\n    LOG_FORMAT,\n    WEBUI_ROOT_PATH,"
    )

    content = content.replace(
        "        'version': VERSION,\n        'default_locale':",
        "        'version': VERSION,\n        'root_path': WEBUI_ROOT_PATH,\n        'default_locale':"
    )

    content = content.replace("'start_url': '/'", "'start_url': f'{WEBUI_ROOT_PATH}/'")
    content = content.replace("'src': '/static/logo.png'", "'src': f'{WEBUI_ROOT_PATH}/static/logo.png'")
    content = content.replace("'action': '/'", "'action': f'{WEBUI_ROOT_PATH}/'")

    content = content.replace(
        "swagger_js_url='/static/swagger-ui/swagger-ui-bundle.js'",
        "swagger_js_url=f'{WEBUI_ROOT_PATH}/static/swagger-ui/swagger-ui-bundle.js'"
    )
    content = content.replace(
        "swagger_css_url='/static/swagger-ui/swagger-ui.css'",
        "swagger_css_url=f'{WEBUI_ROOT_PATH}/static/swagger-ui/swagger-ui.css'"
    )
    content = content.replace(
        "swagger_favicon_url='/static/swagger-ui/favicon.png'",
        "swagger_favicon_url=f'{WEBUI_ROOT_PATH}/static/swagger-ui/favicon.png'"
    )

    # Import PathPrefixStripMiddleware alongside other middleware imports
    content = content.replace(
        "from open_webui.utils.asgi_middleware import (\n    AuthTokenMiddleware,\n    CommitSessionMiddleware,\n    RedirectMiddleware,\n    WebsocketUpgradeGuardMiddleware,\n)",
        "from open_webui.utils.asgi_middleware import (\n    AuthTokenMiddleware,\n    CommitSessionMiddleware,\n    RedirectMiddleware,\n    WebsocketUpgradeGuardMiddleware,\n)\nfrom open_webui.utils.path_prefix_middleware import PathPrefixStripMiddleware"
    )

    # Add PathPrefixStripMiddleware as outermost middleware (added last = runs first)
    content = content.replace(
        "app.add_middleware(\n    CORSMiddleware,\n    allow_origins=CORS_ALLOW_ORIGIN,\n    allow_credentials=True,\n    allow_methods=['*'],\n    allow_headers=['*'],\n)",
        "app.add_middleware(\n    CORSMiddleware,\n    allow_origins=CORS_ALLOW_ORIGIN,\n    allow_credentials=True,\n    allow_methods=['*'],\n    allow_headers=['*'],\n)\n\n# PathPrefixStripMiddleware must be added last so it runs first (outermost),\n# stripping WEBUI_ROOT_PATH from incoming request paths before any other\n# middleware or FastAPI routing processes them.\napp.add_middleware(PathPrefixStripMiddleware)"
    )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_asgi_middleware_py(path):
    filepath = os.path.join(path, 'backend/open_webui/utils/asgi_middleware.py')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist (redirect middleware still in main.py)")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    if 'WEBUI_ROOT_PATH' in content:
        print(f"  [skip] {filepath} — WEBUI_ROOT_PATH already present")
        return

    content = insert_import_after_future(content, "from open_webui.env import WEBUI_ROOT_PATH")

    content = content.replace(
        "redirect_url = f'/?{urlencode(redirect_params)}'",
        "redirect_url = f'{WEBUI_ROOT_PATH}/?{urlencode(redirect_params)}'"
    )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_svelte_config(path):
    filepath = os.path.join(path, 'svelte.config.js')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    if 'rootPathPreprocess' in content:
        print(f"  [skip] {filepath} — rootPathPreprocess already present")
        return

    # 1. Add rootPathPreprocess import
    content = content.replace(
        "import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';",
        "import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';\nimport { rootPathPreprocess } from './src/lib/root-path-preprocess.js';"
    )

    # 2. Add rootPathPreprocess to preprocess — handle both array and non-array forms
    #    Upstream v0.9.2 uses: preprocess: vitePreprocess()      (non-array)
    #    Some versions use:     preprocess: [vitePreprocess()]    (array)
    if 'preprocess: [rootPathPreprocess()' not in content:
        content = content.replace(
            "preprocess: [vitePreprocess()]",
            "preprocess: [rootPathPreprocess(), vitePreprocess()]"
        )
    preprocess_line = content.split('preprocess')[1].split('\n')[0] if 'preprocess' in content else ''
    if 'rootPathPreprocess' not in preprocess_line:
        content = content.replace(
            "preprocess: vitePreprocess()",
            "preprocess: [rootPathPreprocess(), vitePreprocess()]"
        )

    # 3. Add WEBUI_BASE_PATH constant before the config object
    if 'WEBUI_BASE_PATH' not in content:
        content = content.replace(
            "/** @type {import('@sveltejs/kit').Config} */",
            "const WEBUI_BASE_PATH = process.env.WEBUI_ROOT_PATH || '';\n\n/** @type {import('@sveltejs/kit').Config} */"
        )

    # 4. Add paths.base config after adapter fallback
    #    fallback is indented with 3 tabs (inside adapter({)), closing }), with 2 tabs
    if 'paths:' not in content:
        content = content.replace(
            "\t\t\tfallback: 'index.html'\n\t\t}),",
            "\t\t\tfallback: 'index.html'\n\t\t}),\n\t\tpaths: {\n\t\t\tbase: WEBUI_BASE_PATH\n\t\t},"
        )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_vite_config(path):
    filepath = os.path.join(path, 'vite.config.ts')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    if 'WEBUI_ROOT_PATH' in content:
        print(f"  [skip] {filepath} — WEBUI_ROOT_PATH already present")
        return

    content = content.replace(
        "import { viteStaticCopy } from 'vite-plugin-static-copy';",
        "import { viteStaticCopy } from 'vite-plugin-static-copy';\n\nconst WEBUI_BASE_PATH = process.env.WEBUI_ROOT_PATH || '';"
    )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_constants_ts(path):
    filepath = os.path.join(path, 'src/lib/constants.ts')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    if 'getBasePath' in content or '__sveltekit' in content:
        print(f"  [skip] {filepath} — getBasePath already present")
        return

    getbasePath_fn = """
function getBasePath(): string {
\tif (!browser) return '';
\tfor (const key of Object.keys(globalThis as any)) {
\t\tif (key.startsWith('__sveltekit')) {
\t\t\tconst cfg = (globalThis as any)[key];
\t\t\tif (cfg?.base) return cfg.base;
\t\t}
\t}
\treturn '';
}
"""

    content = content.replace(
        "import { browser, dev } from '$app/environment';",
        "import { browser, dev } from '$app/environment';\n" + getbasePath_fn
    )

    content = content.replace(
        "export const WEBUI_BASE_URL = browser ? (dev ? `http://${WEBUI_HOSTNAME}` : ``) : ``;",
        "export const WEBUI_BASE_URL = browser ? (dev ? `http://${WEBUI_HOSTNAME}` : getBasePath()) : getBasePath();"
    )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_app_html(path, root_path):
    filepath = os.path.join(path, 'src/app.html')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist")
        return

    # NOTE: We intentionally do NOT transform app.html with the root path prefix.
    # SvelteKit's paths.base config already prefixes all runtime paths correctly,
    # and the Dockerfile's post-build sed pass handles any remaining bare paths
    # in the built output. Transforming app.html here would cause double-prefixing
    # (e.g., /openwebui/openwebui/static/favicon.png).
    print(f"  [skip] {filepath} — skipped to avoid double-prefixing (SvelteKit handles this)")


def transform_layout_svelte(path):
    filepath = os.path.join(path, 'src/routes/+layout.svelte')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    changed = False

    # Fix Socket.IO path: '/ws/socket.io' → `${base}/ws/socket.io`
    # The preprocessor handles this too, but SvelteKit's build optimizer can
    # inline `base` to an empty string inside object literals, so we need to
    # ensure the source uses `${base}` explicitly before the build runs.
    if "path: '/ws/socket.io'" in content:
        content = content.replace(
            "path: '/ws/socket.io'",
            "path: `${base}/ws/socket.io`",
        )
        changed = True
        if "import { base } from '$app/paths'" not in content and "from '$app/paths'" not in content:
            content = content.replace(
                "import { ",
                "import { base } from '$app/paths';\nimport { ",
                1,
            )

    if not changed:
        print(f"  [skip] {filepath} — no changes needed")
        return

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_arena_model_modal(path):
    filepath = os.path.join(path, 'src/lib/components/admin/Settings/Evaluations/ArenaModelModal.svelte')
    if not os.path.exists(filepath):
        # Try alternate paths in case upstream restructures
        import glob
        matches = glob.glob(os.path.join(path, 'src/**/ArenaModelModal.svelte'), recursive=True)
        if matches:
            filepath = matches[0]
        else:
            print(f"  [skip] ArenaModelModal.svelte — file does not exist")
            return

    with open(filepath, 'r') as f:
        content = f.read()

    changed = False

    # Fix: ${WEBUI_BASE_URL}/favicon.png → ${WEBUI_BASE_URL}/static/favicon.png
    if '${WEBUI_BASE_URL}/favicon.png' in content:
        content = content.replace(
            '${WEBUI_BASE_URL}/favicon.png',
            '${WEBUI_BASE_URL}/static/favicon.png',
        )
        changed = True

    # Also fix getBasePath() form after transform_constants_ts runs
    if 'getBasePath()/favicon.png' in content:
        content = content.replace(
            'getBasePath()/favicon.png',
            'getBasePath()/static/favicon.png',
        )
        changed = True

    if not changed:
        print(f"  [skip] {filepath} — no changes needed")
        return

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def transform_models_py(path):
    filepath = os.path.join(path, 'backend/open_webui/routers/models.py')
    if not os.path.exists(filepath):
        print(f"  [skip] {filepath} — file does not exist")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    if "f'{WEBUI_ROOT_PATH}/static/favicon.png'" in content:
        print(f"  [skip] {filepath} — WEBUI_ROOT_PATH already present in models.py")
        return

    # Add import
    content = content.replace(
        "from open_webui.utils.auth import get_admin_user, get_verified_user",
        "from open_webui.utils.auth import get_admin_user, get_verified_user\nfrom open_webui.env import WEBUI_ROOT_PATH",
    )

    # Prefix safe_static_redirect_path return value with WEBUI_ROOT_PATH
    content = content.replace(
        "    return normalized\n",
        "    return f'{WEBUI_ROOT_PATH}{normalized}'\n",
    )

    # Prefix fallback favicon redirect
    content = content.replace(
        "    return RedirectResponse(\n        url='/static/favicon.png',\n        status_code=status.HTTP_302_FOUND,\n    )",
        "    return RedirectResponse(\n        url=f'{WEBUI_ROOT_PATH}/static/favicon.png',\n        status_code=status.HTTP_302_FOUND,\n    )",
    )

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  [done] {filepath}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/upstream/clone [WEBUI_ROOT_PATH]")
        sys.exit(1)

    clone_path = sys.argv[1]
    root_path = sys.argv[2] if len(sys.argv) > 2 else ''
    print(f"Applying backend root path transforms to {clone_path} (root_path={root_path!r})...")

    transform_env_py(clone_path)
    transform_main_py(clone_path)
    transform_models_py(clone_path)
    transform_asgi_middleware_py(clone_path)
    transform_svelte_config(clone_path)
    transform_vite_config(clone_path)
    transform_constants_ts(clone_path)
    transform_arena_model_modal(clone_path)
    transform_layout_svelte(clone_path)
    transform_app_html(clone_path, root_path)

    print("Done.")


if __name__ == '__main__':
    main()