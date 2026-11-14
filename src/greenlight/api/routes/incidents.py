"""Incident ingestion and read endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, load_only

from greenlight.core.security import require_ingest_api, require_read_api
from greenlight.db import get_db
from greenlight.db.models import Incident
from greenlight.schemas import CrashReport, IncidentOut
from greenlight.services.incidents import create_incident

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

# Columns exposed by IncidentOut; skipping the large trace/result columns keeps reads cheap.
_OUT_COLUMNS = load_only(
    Incident.id,
    Incident.service_name,
    Incident.host_ip,
    Incident.severity,
    Incident.root_cause,
    Incident.suggested_fix,
    Incident.remediation_key,
    Incident.confidence_score,
    Incident.status,
    Incident.source,
)


@router.post("/ingest", response_model=IncidentOut, status_code=201, dependencies=[Depends(require_ingest_api)])
async def ingest(report: CrashReport, db: Session = Depends(get_db)):
    return await create_incident(report, db, "api")


@router.get("", response_model=list[IncidentOut], dependencies=[Depends(require_read_api)])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(Incident).options(_OUT_COLUMNS).order_by(Incident.created_at.desc()).limit(50).all()


@router.get("/{incident_id}", response_model=IncidentOut, dependencies=[Depends(require_read_api)])
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    item = db.query(Incident).options(_OUT_COLUMNS).filter(Incident.id == incident_id).one_or_none()
    if not item:
        raise HTTPException(404, "Incident not found")
    return item
