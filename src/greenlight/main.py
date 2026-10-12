"""FastAPI application factory and ASGI entry point (``greenlight.main:app``)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from greenlight import __version__
from greenlight.api.middleware import install_middleware
from greenlight.api.router import api_router
from greenlight.core.config import settings
from greenlight.core.logging_config import configure_logging
from greenlight.core.security import seed_operators
from greenlight.db import SessionLocal, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.is_production:
        errors = settings.production_config_errors()
        if errors:
            raise RuntimeError("Refusing to start with insecure production configuration: " + "; ".join(errors))
    init_db()
    with SessionLocal() as db:
        seed_operators(db)
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="GreenLight",
        version=__version__,
        description="AI-assisted incident control plane with human approval and isolated remediation workers",
        lifespan=lifespan,
    )
    install_middleware(app)
    app.include_router(api_router)
    return app


app = create_app()
