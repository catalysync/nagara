#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Rebuild + redeploy the nagara marketing site container.
#
# You only need this when CODE changes (components, routes, config).
# CONTENT and IMAGE edits made in the Keystatic admin (/keystatic) go live
# immediately with NO rebuild — content/ and public/images/ are bind-mounted
# into the running container and the pages render at request time.
#
# Usage:  bash /opt/nagara/deploy.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd /opt/nagara

echo "==> Building image nagara:latest"
docker build -t nagara:latest .

echo "==> Replacing running container"
docker rm -f nagara 2>/dev/null || true
docker run -d --name nagara --restart unless-stopped \
  -p 127.0.0.1:8092:3000 \
  -e KEYSTATIC_STORAGE_LOCAL=true \
  -v /opt/nagara/public/images:/app/public/images \
  -v /opt/nagara/content:/app/content \
  nagara:latest

echo "==> Waiting for health"
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8092/ || true)
  [ "$code" = "200" ] && { echo "OK ($code)"; exit 0; }
  sleep 1
done
echo "WARN: site did not return 200 within 30s" >&2
exit 1
