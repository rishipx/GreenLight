"""Runbook executor."""

import subprocess

from greenlight.core.config import settings
from greenlight.services import runbooks


def test_unknown_key_is_refused():
    assert runbooks.execute("rm_rf_everything")["exit_code"] == 127


def test_dry_run_does_not_spawn_a_process(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("subprocess must not run in dry-run mode")

    monkeypatch.setattr(subprocess, "run", boom)
    result = runbooks.execute("redis_worker_restart")
    assert result["success"] and result["mode"] == "dry-run"


def test_execute_mode_reports_unstartable_runbook_instead_of_raising(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(settings, "remediation_mode", "execute")
    monkeypatch.setattr(subprocess, "run", missing)
    result = runbooks.execute("redis_worker_restart")
    assert result["success"] is False and result["exit_code"] == 126
