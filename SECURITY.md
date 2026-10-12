# Security Policy

## Supported versions

Only the latest release and the `main` branch are supported.

## Reporting a vulnerability

Do **not** open a public issue for security problems. Use GitHub's private vulnerability reporting (**Security → Report a vulnerability**) and include the affected component, reproduction steps and impact.

Expected response: acknowledgement within 7 days. This is a volunteer-maintained project with no SLA or bounty.

## Scope

In scope: authentication or authorization bypass, approval-token replay, allowlist bypass, injection into runbook execution, privacy-filter bypass of documented patterns, container hardening regressions.

Out of scope: findings that require `APP_ENV=development` with unset keys (documented open mode), default local-development database credentials, denial of service against the single-instance in-process rate limiter, and issues listed in [DISCLAIMER.md](DISCLAIMER.md).

## Hardening checklist

See the production checklist in [docs/deployment.md](docs/deployment.md).
