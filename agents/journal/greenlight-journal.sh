#!/usr/bin/env bash
set -euo pipefail

# GreenLight Linux/systemd incident source.
# Watches journalctl for error-priority events and forwards them to the control plane.
# Configure these in the systemd unit or environment:
#   GREENLIGHT_URL=https://greenlight.example.com
#   GREENLIGHT_WEBHOOK_SECRET=<shared secret>
#   GREENLIGHT_SERVICE_NAME=my-service
#   GREENLIGHT_JOURNAL_UNIT=my-service.service   (optional)
#   GREENLIGHT_COOLDOWN_SECONDS=300             (optional; suppress identical repeats)
#   GREENLIGHT_MATCH_REGEX='(panic|fatal|segfault|exception|failed|error)' (optional)

: "${GREENLIGHT_URL:?GREENLIGHT_URL is required}"
: "${GREENLIGHT_WEBHOOK_SECRET:?GREENLIGHT_WEBHOOK_SECRET is required}"
: "${GREENLIGHT_SERVICE_NAME:?GREENLIGHT_SERVICE_NAME is required}"

MATCH_REGEX="${GREENLIGHT_MATCH_REGEX:-panic|fatal|segfault|exception|failed|error}"
UNIT_ARGS=()
if [[ -n "${GREENLIGHT_JOURNAL_UNIT:-}" ]]; then
  UNIT_ARGS+=( -u "$GREENLIGHT_JOURNAL_UNIT" )
fi

HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
HOST="${HOST:-$(hostname)}"
ENDPOINT="${GREENLIGHT_URL%/}/api/v1/webhooks/agent"
COOLDOWN="${GREENLIGHT_COOLDOWN_SECONDS:-300}"
declare -A SEEN=()

journalctl -f -n 0 -p err..alert -o short-iso "${UNIT_ARGS[@]}" | while IFS= read -r line; do
  if ! printf '%s\n' "$line" | grep -Eiq "$MATCH_REGEX"; then
    continue
  fi

  # Cooldown: skip a repeat of the same message (timestamp stripped) within COOLDOWN seconds.
  key="$(printf '%s' "${line#* }" | cksum | cut -d' ' -f1)"
  now=$(date +%s)
  last="${SEEN[$key]:-0}"
  if (( now - last < COOLDOWN )); then
    continue
  fi
  SEEN[$key]=$now
  if (( ${#SEEN[@]} > 1000 )); then SEEN=(); fi

  payload=$(python3 - "$GREENLIGHT_SERVICE_NAME" "$HOST" "$line" <<'PY'
import json, sys
service, host, line = sys.argv[1:]
print(json.dumps({
    "service_name": service,
    "host_ip": host,
    "severity": "P1",
    "error_trace": line,
}))
PY
)

  # A failed POST (429, 5xx, network) must not kill the watcher; log and keep reading.
  curl --fail --silent --show-error --max-time 10 \
    -H 'Content-Type: application/json' \
    -H "X-GreenLight-Webhook-Secret: ${GREENLIGHT_WEBHOOK_SECRET}" \
    -d "$payload" "$ENDPOINT" >/dev/null || echo "greenlight-agent: delivery failed, continuing" >&2

done
