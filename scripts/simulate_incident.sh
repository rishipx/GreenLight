#!/usr/bin/env bash
# Send a sample incident to a running GreenLight API.
#   GREENLIGHT_ENDPOINT  ingest URL (default: http://127.0.0.1:8000/api/v1/incidents/ingest)
#   GREENLIGHT_API_KEY   ingest API key (required when the API has INGEST_API_KEY set)
set -euo pipefail
ENDPOINT="${GREENLIGHT_ENDPOINT:-http://127.0.0.1:8000/api/v1/incidents/ingest}"
AUTH_HEADER=()
if [[ -n "${GREENLIGHT_API_KEY:-}" ]]; then
  AUTH_HEADER=( -H "X-GreenLight-API-Key: ${GREENLIGHT_API_KEY}" )
fi
python3 - <<'PY' | curl -sS --fail-with-body -X POST "$ENDPOINT" -H 'Content-Type: application/json' "${AUTH_HEADER[@]}" --data-binary @-
import json
print(json.dumps({
  "service_name":"payment-gateway",
  "host_ip":"192.168.1.104",
  "severity":"P0",
  "error_trace":"TooManyConnectionsError: too many clients already connected"
}))
PY
