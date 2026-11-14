# Integrations

All source webhooks authenticate with `X-GreenLight-Webhook-Secret` or `Authorization: Bearer <secret>`. Use a separate secret per source.

## Linux / systemd journal

`agents/journal/greenlight-journal.sh` follows `journalctl -p err..alert`, filters lines with a regular expression, suppresses identical repeats for a cooldown period and posts to `POST /api/v1/webhooks/agent`. It requires `curl` and `python3` and has no remediation authority. A failed delivery is logged and the watcher keeps running.

A sandboxed unit is provided in `deploy/systemd/greenlight-journal.service`. Put the secret in `/etc/greenlight/agent.env` (`GREENLIGHT_WEBHOOK_SECRET=…`, mode `0600`).

## Prometheus Alertmanager

`POST /api/v1/webhooks/alertmanager`. Firing alerts are normalized (service, host, severity, annotations, labels); resolved alerts are ignored; a malformed alert is skipped without discarding the rest of the batch. See `examples/alertmanager.yml`.

## Generic webhook

`POST /api/v1/webhooks/generic` accepts a normalized contract:

```json
{
  "service": "redis-worker",
  "host": "worker-01",
  "severity": "P1",
  "message": "queue latency above threshold"
}
```

Accepted aliases: `service_name`, `service`, `host_ip`, `host`, `instance`, `error_trace`, `message`, `description`. A payload that cannot be normalized into a valid incident returns `422`.

Datadog, Grafana, Sentry, CloudWatch and similar systems can feed this contract through their webhook or transformation layer. No vendor-specific payload adapters are shipped. Kubernetes alerts can enter through Alertmanager or the generic webhook.

## Direct API

`POST /api/v1/incidents/ingest` (ingest key) creates an incident; `GET /api/v1/incidents` and `GET /api/v1/incidents/{id}` (read key) return it. Send keys as `X-GreenLight-API-Key` or `Authorization: Bearer`.

## Telegram

1. Create a bot and set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS` and `TELEGRAM_WEBHOOK_SECRET`.
2. Register the webhook with `secret_token` set to the same secret, pointing at `POST /api/v1/webhooks/telegram`.

Callback data has the form `exec:<incident_uuid>:<token>` or `dsm:<incident_uuid>:<token>`. Tokens expire after `APPROVAL_TTL_SECONDS` and cannot be reused.

## n8n (optional)

The worker can POST each finished job to an n8n webhook, for example to forward it to Slack or Discord. It is off unless `N8N_WEBHOOK_URL` is set, and a failed notification is logged without affecting the incident.

1. In `.env`, set `N8N_WEBHOOK_URL=http://n8n:5678/webhook/greenlight`.
2. Start the stack with n8n: `docker compose --profile n8n up --build`.
3. Open <http://localhost:5678>, create the owner account, and import `examples/n8n/greenlight-notifier.json`.
4. In the last node, replace the placeholder with your Slack or Discord webhook URL (for Discord, add `/slack` to the end), then activate the workflow.

The payload fields are `event`, `incident_id`, `execution_id`, `action` (`EXECUTED` or `EXECUTION_FAILED`), `resolved_by_admin`, `service`, `severity` and `execution_summary`. A test fails if the workflow reads a field the worker does not send.

n8n is the only service on both Docker networks, so the worker still has no direct internet access. n8n is published on `127.0.0.1` only because its webhook has no authentication.

