#!/usr/bin/env bash
# Import the Docker Sandboxes proxy CA ($PROXY_CA_CERT_B64) into the system
# trust store so TLS to external services succeeds through the MITM proxy.
# Best-effort and idempotent: never exits non-zero, no-op when the env is absent.
set -u

[ -n "${PROXY_CA_CERT_B64:-}" ] || exit 0

ca_file="$(mktemp)"
if ! printf '%s' "$PROXY_CA_CERT_B64" | base64 -d > "$ca_file" 2>/dev/null; then
    rm -f "$ca_file"
    exit 0
fi

if command -v update-ca-certificates >/dev/null 2>&1; then
    cp "$ca_file" /usr/local/share/ca-certificates/sbx-proxy-ca.crt
    update-ca-certificates >/dev/null 2>&1 || true
elif [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    cat "$ca_file" >> /etc/ssl/certs/ca-certificates.crt 2>/dev/null || true
fi

rm -f "$ca_file"
exit 0