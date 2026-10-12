-- GreenLight PostgreSQL schema (v1.0.0). Applied automatically by the Docker Compose postgres service.
-- Keep in sync with src/greenlight/db/models.py.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS operators (
  telegram_id BIGINT PRIMARY KEY,
  role VARCHAR(16) NOT NULL DEFAULT 'APPROVER' CHECK (role IN ('ADMIN','APPROVER','VIEWER')),
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_name VARCHAR(64) NOT NULL,
  host_ip VARCHAR(255) NOT NULL,
  source VARCHAR(32) NOT NULL DEFAULT 'api',
  severity VARCHAR(2) NOT NULL CHECK (severity IN ('P0','P1','P2')),
  error_trace TEXT NOT NULL,
  root_cause TEXT,
  suggested_fix TEXT,
  remediation_key VARCHAR(64),
  confidence_score DOUBLE PRECISION,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','EXECUTING','EXECUTED','FAILED','DISMISSED')),
  execution_result JSONB,
  approval_token_hash VARCHAR(64),
  approval_expires_at TIMESTAMPTZ,
  approval_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status_created ON incidents(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_approval_token ON incidents(approval_token_hash);

CREATE TABLE IF NOT EXISTS remediation_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID NOT NULL UNIQUE REFERENCES incidents(id) ON DELETE CASCADE,
  remediation_key VARCHAR(64) NOT NULL,
  requested_by BIGINT NOT NULL REFERENCES operators(telegram_id),
  status VARCHAR(16) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
  attempt_count INTEGER NOT NULL DEFAULT 0,
  result JSONB,
  claimed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON remediation_jobs(status, created_at);

CREATE TABLE IF NOT EXISTS incident_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  actor_telegram_id BIGINT NOT NULL,
  action VARCHAR(32) NOT NULL CHECK (action IN ('APPROVED','DISMISSED','REJECTED','EXECUTED','EXECUTION_FAILED','JOB_REQUEUED')),
  details JSONB, -- sanitized callback metadata only; never store approval tokens or raw Telegram updates
  executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_incident_audits_incident ON incident_audits(incident_id, executed_at DESC);

-- Defense-in-depth: if this database is exposed through a user-facing PostgREST/Supabase layer,
-- RLS can be enabled and policies can be bound to authenticated operator claims. The direct API/worker
-- connections in this project are trusted server-side roles and must never be exposed to clients.
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE operators ENABLE ROW LEVEL SECURITY;
