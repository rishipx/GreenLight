"""database/schema.sql must describe the same tables and columns as the ORM models.

CI builds its test tables from the ORM, so without this check the SQL schema (which Docker Compose
loads) could drift from the models without any test noticing.
"""

import re

from greenlight.db.models import Incident, IncidentAudit, Operator, RemediationJob
from tests.paths import SCHEMA_SQL

MODELS = (Operator, Incident, RemediationJob, IncidentAudit)
TABLE_RE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", re.DOTALL)


def _sql_without_comments() -> str:
    return "\n".join(line for line in SCHEMA_SQL.read_text().splitlines() if not line.lstrip().startswith("--"))


def test_schema_sql_has_the_same_tables_and_columns_as_the_orm():
    sql = _sql_without_comments()
    in_sql = {name: set(re.findall(r"^  (\w+) ", body, re.MULTILINE)) for name, body in TABLE_RE.findall(sql)}
    in_orm = {model.__tablename__: {column.name for column in model.__table__.columns} for model in MODELS}
    assert in_sql == in_orm


def test_schema_sql_uses_varchar_ids_like_the_orm_not_native_uuid():
    # The ORM maps ids as String(36); a native UUID column rejects its VARCHAR bind parameters.
    assert not re.search(r"\bUUID\b", _sql_without_comments())
