# Deployment

## Local stack

```bash
cp .env.example .env
docker compose up --build
```

Runs PostgreSQL, the API (published on `127.0.0.1:8000` only) and the worker. PostgreSQL and the worker share an internal network with no external access.

## TLS with Caddy

`docker-compose.prod.yml` adds Caddy, removes the published API port and sets `APP_ENV=production`. It requires Docker Compose v2.24+.

```bash
GREENLIGHT_DOMAIN=greenlight.example.com \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Caddy is pinned to `172.28.0.10` on the edge network and the API trusts `X-Forwarded-For` only from that address, so the rate limiter sees real client IPs. With a different proxy, set `FORWARDED_ALLOW_IPS` accordingly or all clients share one rate-limit bucket.

## Production checklist

- `APP_ENV=production` with every required secret set, each distinct.
- Replace the default database password (`POSTGRES_PASSWORD`) or use managed PostgreSQL over TLS.
- Keep `REMEDIATION_MODE=dry-run` until runbooks are reviewed, tested and idempotent.
- Terminate TLS at a reverse proxy; never publish the API container directly.
- Never mount a Docker socket, cloud credentials or privileged access into the worker.

## Going beyond the reference deployment

External secret management, versioned database migrations (the app uses `create_all` at startup), distributed rate limiting, centralized metrics/traces/logs, signed and versioned runbooks, a least-privilege remediation target, organization-specific database roles and RLS policies, and HA/DR appropriate to incident criticality.
