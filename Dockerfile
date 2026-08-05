# syntax=docker/dockerfile:1

ARG UPSTREAM_IMAGE=ghcr.io/open-webui/open-webui
ARG UPSTREAM_VERSION
ARG BUILD_HASH=dev-build
ARG WEBUI_ROOT_PATH="/__WEBUI_ROOT_PATH__"

######## Prepare: clone + patch + inject + transform ########
FROM alpine:3.20 AS prepare

ARG UPSTREAM_URL=https://github.com/open-webui/open-webui.git
ARG UPSTREAM_VERSION
ARG WEBUI_ROOT_PATH="/__WEBUI_ROOT_PATH__"

RUN apk add --no-cache git patch python3

WORKDIR /overlay
COPY patches/ ./patches/
COPY inject/ ./inject/
COPY transforms/ ./transforms/

WORKDIR /upstream
RUN git clone --depth=1 --branch "${UPSTREAM_VERSION}" "${UPSTREAM_URL}" .

RUN echo "=== Injecting new files ===" && \
    cp -rv /overlay/inject/* . 2>/dev/null; \
    if [ -d /overlay/inject/src ]; then cp -rv /overlay/inject/src ./; fi

RUN echo "=== Applying patches ===" && \
    FAILED=""; \
    for pf in /overlay/patches/*.patch; do \
      name=$(basename "$pf"); \
      echo -n "  ${name}... "; \
      if patch -p1 --fuzz=3 --dry-run < "$pf" >/dev/null 2>&1; then \
        patch -p1 --fuzz=3 < "$pf" >/dev/null 2>&1 && echo "OK" || echo "FAILED (apply error)"; \
      else \
        echo "FAILED (dry-run)"; \
        FAILED="$FAILED $name"; \
      fi; \
    done; \
    echo "Failed patches: ${FAILED:-none}"

RUN echo "=== Running script-based transforms ===" && \
    python3 /overlay/transforms/backend-rootpath.py /upstream "${WEBUI_ROOT_PATH}"

######## WebUI frontend ########
FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build
ARG BUILD_HASH
ARG WEBUI_ROOT_PATH

WORKDIR /app

COPY --from=prepare /upstream/package.json /upstream/package-lock.json ./
RUN npm ci --force

COPY --from=prepare /upstream/ .
ENV APP_BUILD_HASH=${BUILD_HASH}
ENV WEBUI_ROOT_PATH=${WEBUI_ROOT_PATH}
ENV NODE_OPTIONS=--max-old-space-size=6144
RUN npm run build

# Post-build: rewrite root-absolute paths SvelteKit doesn't prefix correctly.
# Rewrite /_app/ and /static/ — /api/ and /ws/ are already prefixed at runtime
# via the base variable ($app/paths), so sed would cause double-prefixing.
RUN if [ -n "${WEBUI_ROOT_PATH}" ]; then \
      echo "Rewriting root-absolute paths with prefix: ${WEBUI_ROOT_PATH}"; \
      for f in $(find /app/build -type f \( -name '*.html' -o -name '*.js' \)); do \
        sed -i \
          -e "s|\"/_app/|\"${WEBUI_ROOT_PATH}/_app/|g" \
          -e "s|'/_app/|'${WEBUI_ROOT_PATH}/_app/|g" \
          -e 's|`/_app/|`'"${WEBUI_ROOT_PATH}"'/_app/|g' \
          -e "s|\"/static/|\"${WEBUI_ROOT_PATH}/static/|g" \
          -e "s|'/static/|'${WEBUI_ROOT_PATH}/static/|g" \
          -e 's|`/static/|`'"${WEBUI_ROOT_PATH}"'/static/|g' \
          -e "s|\"/manifest.json\"|\"${WEBUI_ROOT_PATH}/manifest.json\"|g" \
          -e "s|'/manifest.json'|'${WEBUI_ROOT_PATH}/manifest.json'|g" \
          "$f"; \
      done && \
      echo "Done rewriting root-absolute paths"; \
    fi

ARG UPSTREAM_IMAGE
ARG UPSTREAM_VERSION

FROM ${UPSTREAM_IMAGE}:${UPSTREAM_VERSION} AS base

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN rm -rf /app/build
COPY --from=build /app/build /app/build
COPY --from=prepare /upstream/backend/open_webui/ /app/backend/open_webui/

ENV WEBUI_ROOT_PATH=""

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["bash", "start.sh"]