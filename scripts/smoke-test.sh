#!/usr/bin/env bash

set -euo pipefail

: "${APP_URL:?Set APP_URL to the deployed application, e.g. https://pay-align-dev.onrender.com.}"
HEALTH_URL="${APP_URL%/}/health"
ATTEMPTS="${SMOKE_ATTEMPTS:-30}"
DELAY_SECONDS="${SMOKE_DELAY_SECONDS:-10}"

for attempt in $(seq 1 "$ATTEMPTS"); do
  if curl --fail --silent --max-time 60 "$HEALTH_URL" | grep -q '"status":"ok"'; then
    echo "Smoke test passed: $HEALTH_URL (attempt $attempt)."
    exit 0
  fi
  sleep "$DELAY_SECONDS"
done

echo "Smoke test failed: $HEALTH_URL did not answer {\"status\":\"ok\"} after $ATTEMPTS attempts." >&2
exit 1
