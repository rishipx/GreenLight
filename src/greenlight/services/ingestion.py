"""Normalization of Alertmanager and generic webhook payloads into ``CrashReport`` objects."""

import json
import logging
from typing import Any

from pydantic import ValidationError

from greenlight.schemas import HOST_RE, CrashReport, Severity

logger = logging.getLogger("greenlight.ingestion")

_SEVERITY_ALIASES = {
    "CRITICAL": Severity.P0,
    "EMERGENCY": Severity.P0,
    "ALERT": Severity.P0,
    "ERROR": Severity.P1,
    "WARNING": Severity.P1,
    "WARN": Severity.P1,
}


def normalize_host(value: Any) -> str:
    host = str(value or "unknown")[:255]
    return host if HOST_RE.fullmatch(host) else "unknown"


def _text(value: Any, limit: int = 50000) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        value = json.dumps(value, sort_keys=True, default=str)
    return str(value)[:limit]


def _severity(value: Any, default: Severity = Severity.P1) -> Severity:
    raw = str(value or "").upper()
    if raw in Severity.__members__:
        return Severity(raw)
    return _SEVERITY_ALIASES.get(raw, default)


def _service_from_alert(alert: dict) -> str:
    labels = alert.get("labels") or {}
    return str(labels.get("service") or labels.get("job") or labels.get("alertname") or "alertmanager")[:64]


def _host_from_alert(alert: dict) -> str:
    labels = alert.get("labels") or {}
    instance = str(labels.get("instance") or labels.get("host") or labels.get("node") or "unknown")
    return instance.split(":", 1)[0] if instance else "unknown"


def _alert_trace(alert: dict) -> str:
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    parts = [
        f"Alert: {labels.get('alertname', 'unknown')}",
        f"Status: {alert.get('status', 'unknown')}",
        f"Summary: {annotations.get('summary', '')}",
        f"Description: {annotations.get('description', '')}",
    ]
    useful_labels = {k: v for k, v in labels.items() if k != "alertname"}
    if useful_labels:
        parts.append("Labels: " + json.dumps(useful_labels, sort_keys=True))
    return "\n".join(p for p in parts if p.strip())[:50000]


def alertmanager_reports(payload: dict) -> list[CrashReport]:
    """Convert firing alerts in an Alertmanager webhook batch; resolved alerts are ignored."""
    reports = []
    for alert in payload.get("alerts") or []:
        if str(alert.get("status", "firing")).lower() != "firing":
            continue
        try:
            reports.append(
                CrashReport(
                    service_name=_service_from_alert(alert),
                    host_ip=normalize_host(_host_from_alert(alert)),
                    severity=_severity((alert.get("labels") or {}).get("severity")),
                    error_trace=_alert_trace(alert) or "Alertmanager firing alert",
                )
            )
        except ValidationError:
            # One malformed alert must not discard the rest of the batch.
            logger.warning(
                {"event": "alert_skipped_invalid", "alertname": str(alert.get("labels", {}).get("alertname"))[:64]}
            )
    return reports


def generic_report(payload: dict) -> CrashReport:
    """Convert a normalized observability webhook payload (see docs/integrations.md)."""
    labels = payload.get("labels") or {}
    service = (
        payload.get("service_name")
        or payload.get("service")
        or labels.get("service")
        or payload.get("job")
        or "webhook"
    )
    host = (
        payload.get("host_ip") or payload.get("host") or payload.get("instance") or labels.get("instance") or "unknown"
    )
    trace_source = payload.get("error_trace") or payload.get("message") or payload.get("description")
    if trace_source is not None:
        trace = trace_source
    elif payload.get("body") is not None:
        trace = "Request body:\n" + _text(payload.get("body"))
    else:
        trace = payload
    return CrashReport(
        service_name=str(service)[:64],
        host_ip=normalize_host(host),
        severity=_severity(payload.get("severity") or labels.get("severity")),
        error_trace=_text(trace) or "Generic webhook incident",
    )
