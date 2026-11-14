"""database/schema.sql must work with the ORM on a real PostgreSQL.

Elsewhere the test tables are built from the ORM, so this is the only test that exercises the SQL
schema Docker Compose actually loads. Skipped unless TEST_POSTGRES_URL is set.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from greenlight.db import Base
from greenlight.db.models import Incident, IncidentAudit, Operator, RemediationJob
from tests.paths import SCHEMA_SQL

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set")

OPERATOR_ID = 5_000_000_000  # > 2**31: needs BIGINT


@pytest.fixture()
def engine():
    engine = create_engine(PG_URL, future=True)
    Base.metadata.drop_all(engine)
    raw = engine.raw_connection()
    try:
        raw.cursor().execute(SCHEMA_SQL.read_text())
        raw.commit()
    finally:
        raw.close()
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_orm_round_trips_against_the_sql_schema(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add(Operator(telegram_id=OPERATOR_ID, role="ADMIN", enabled=True))
        incident = Incident(service_name="svc", host_ip="10.0.0.1", error_trace="x" * 20)
        db.add(incident)
        db.flush()
        job = RemediationJob(incident_id=incident.id, remediation_key="restart", requested_by=OPERATOR_ID)
        audit = IncidentAudit(incident_id=incident.id, actor_telegram_id=OPERATOR_ID, action="APPROVED", details={})
        db.add_all([job, audit])
        db.commit()
        incident_id = incident.id

    with Session() as db:
        loaded = db.get(Incident, incident_id)
        assert isinstance(loaded.id, str) and loaded.status == "PENDING"
        assert loaded.job.remediation_key == "restart"
        assert [audit.action for audit in loaded.audits] == ["APPROVED"]
