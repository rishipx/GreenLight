"""Settings validation."""

import pytest


def test_worker_lease_must_exceed_execution_timeout():
    from greenlight.core.config import Settings

    with pytest.raises(ValueError):
        Settings(worker_lease_seconds=15, remediation_timeout_seconds=15)
