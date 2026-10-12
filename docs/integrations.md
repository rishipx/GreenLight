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
