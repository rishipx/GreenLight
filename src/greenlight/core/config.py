"""Application settings, loaded from environment variables and an optional ``.env`` file."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./greenlight.db"

    # LLM triage
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_redaction_enabled: bool = True
    llm_redact_request_bodies: bool = True

    # Telegram approvals
    telegram_bot_token: str | None = None
    telegram_admin_ids: str = ""
    telegram_webhook_secret: str | None = None

    # API and webhook authentication
    ingest_api_key: str | None = None
    read_api_key: str | None = None
    agent_webhook_secret: str | None = None
    alertmanager_webhook_secret: str | None = None
    generic_webhook_secret: str | None = None

    # Remediation
    n8n_webhook_url: str | None = None
    remediation_mode: str = "dry-run"
    remediation_timeout_seconds: int = 15
    approval_ttl_seconds: int = 300

    # Request protection
    max_request_bytes: int = 65536
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    dedupe_window_seconds: int = 300

    # Worker
    worker_poll_seconds: float = 1.0
    worker_batch_size: int = 1
    worker_lease_seconds: int = 60
    worker_max_attempts: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def admin_ids(self) -> set[int]:
        return {int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()}

    def production_config_errors(self) -> list[str]:
        """Return a message for every setting that must be fixed before running in production."""
        required = {
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_ADMIN_IDS": self.telegram_admin_ids,
            "TELEGRAM_WEBHOOK_SECRET": self.telegram_webhook_secret,
            "INGEST_API_KEY": self.ingest_api_key,
            "READ_API_KEY": self.read_api_key,
            "AGENT_WEBHOOK_SECRET": self.agent_webhook_secret,
            "ALERTMANAGER_WEBHOOK_SECRET": self.alertmanager_webhook_secret,
            "GENERIC_WEBHOOK_SECRET": self.generic_webhook_secret,
        }
        errors = [f"{name} must be set when APP_ENV=production" for name, value in required.items() if not value]
        if self.remediation_mode not in {"dry-run", "execute"}:
            errors.append("REMEDIATION_MODE must be 'dry-run' or 'execute'")
        return errors

    @model_validator(mode="after")
    def validate_worker_safety(self):
        if self.worker_max_attempts < 1:
            raise ValueError("WORKER_MAX_ATTEMPTS must be at least 1")
        if self.worker_lease_seconds <= self.remediation_timeout_seconds:
            raise ValueError("WORKER_LEASE_SECONDS must exceed REMEDIATION_TIMEOUT_SECONDS")
        if self.remediation_timeout_seconds < 1:
            raise ValueError("REMEDIATION_TIMEOUT_SECONDS must be at least 1")
        return self


settings = Settings()
