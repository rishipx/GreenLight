"""Source webhooks: Linux agent, Prometheus Alertmanager and the generic observability contract."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from greenlight.core.config import settings
from greenlight.core.security import verify_ingest_secret
from greenlight.db import get_db
from greenlight.schemas import CrashReport, IncidentOut
from greenlight.services.incidents import create_incident
from greenlight.services.ingestion import alertmanager_reports, generic_report

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/agent", response_model=IncidentOut, status_code=201)
async def agent_webhook(request: Request, report: CrashReport, db: Session = Depends(get_db)):
    verify_ingest_secret(request, settings.agent_webhook_secret, "agent")
    return await create_incident(report, db, "linux-agent")


@router.post("/alertmanager", response_model=list[IncidentOut], status_code=201)
async def alertmanager_webhook(request: Request, payload: dict, db: Session = Depends(get_db)):
    verify_ingest_secret(request, settings.alertmanager_webhook_secret, "Alertmanager")
    return [await create_incident(report, db, "alertmanager") for report in alertmanager_reports(payload)]


@router.post("/generic", response_model=IncidentOut, status_code=201)
async def generic_webhook(request: Request, payload: dict, db: Session = Depends(get_db)):
    verify_ingest_secret(request, settings.generic_webhook_secret, "generic")
    try:
        report = generic_report(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False, include_context=False, include_input=False)) from exc
    return await create_incident(report, db, "generic-webhook")
