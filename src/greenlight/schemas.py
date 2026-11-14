"""Request, response and triage schemas."""

import re
from enum import Enum
from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, field_validator

HOST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,252}")


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class CrashReport(BaseModel):
    service_name: str = Field(min_length=2, max_length=64)
    host_ip: str = Field(min_length=1, max_length=255)
    severity: Severity = Severity.P1
    error_trace: str = Field(min_length=10, max_length=50000)

    @field_validator("host_ip")
    @classmethod
    def valid_host(cls, v: str) -> str:
        try:
            ip_address(v)
        except ValueError:
            if not HOST_RE.fullmatch(v):
                raise ValueError("host_ip must be an IP address or hostname") from None
        return v


class TriageDiagnosis(BaseModel):
    root_cause: str = Field(min_length=5, max_length=2000)
    severity: Severity
    suggested_fix: str = Field(min_length=1, max_length=500)
    remediation_key: str | None = Field(default=None, pattern=r"^[a-z0-9._-]+$")
    confidence_score: float = Field(ge=0, le=1)


class IncidentOut(BaseModel):
    id: str
    service_name: str
    host_ip: str
    severity: str
    root_cause: str | None
    suggested_fix: str | None
    remediation_key: str | None
    confidence_score: float | None
    status: str
    source: str
    model_config = ConfigDict(from_attributes=True)
