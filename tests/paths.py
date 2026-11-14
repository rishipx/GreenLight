"""Repository paths shared by tests."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = REPO_ROOT / "database" / "schema.sql"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
N8N_WORKFLOW = REPO_ROOT / "examples" / "n8n" / "greenlight-notifier.json"
