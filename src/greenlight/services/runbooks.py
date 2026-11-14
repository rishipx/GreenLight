"""Authoritative runbook registry and the executor that runs approved runbooks."""

import subprocess

from greenlight.core.config import settings

# The model may only select a key from this registry; the commands themselves are fixed here.
RUNBOOKS: dict[str, list[str]] = {
    "payment_gateway_restart": ["bash", "-lc", "echo '[dry-run] restart payment-gateway-worker'"],
    "redis_worker_restart": ["bash", "-lc", "echo '[dry-run] restart redis-worker'"],
    "clear_stuck_queue": ["bash", "-lc", "echo '[dry-run] clear stuck queue using approved procedure'"],
}


def is_allowlisted_runbook(remediation_key: str | None) -> bool:
    return bool(remediation_key) and remediation_key in RUNBOOKS


def _failure(exit_code: int, stderr: str, mode: str | None = None) -> dict:
    result = {"success": False, "exit_code": exit_code, "stdout": "", "stderr": stderr}
    if mode:
        result["mode"] = mode
    return result


def execute(remediation_key: str) -> dict:
    """Run an allowlisted runbook (or report a dry run) and return a JSON-serializable result."""
    if not is_allowlisted_runbook(remediation_key):
        return _failure(127, "Unknown remediation key")
    if settings.remediation_mode != "execute":
        return {
            "success": True,
            "exit_code": 0,
            "stdout": f"DRY-RUN: {remediation_key}",
            "stderr": "",
            "mode": "dry-run",
        }
    try:
        process = subprocess.run(
            RUNBOOKS[remediation_key],
            capture_output=True,
            text=True,
            timeout=settings.remediation_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failure(-1, "Execution timed out", "execute")
    except OSError as exc:  # e.g. interpreter missing from the worker image
        return _failure(126, f"Runbook could not be started: {exc.strerror or exc}", "execute")
    return {
        "success": process.returncode == 0,
        "exit_code": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "mode": "execute",
    }
