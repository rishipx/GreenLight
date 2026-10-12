"""HTTP middleware: request IDs, request guards and structured access logs."""

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from greenlight.core.security import request_guard

logger = logging.getLogger("greenlight.api")


def _log_request(request: Request, request_id: str, started: float) -> None:
    logger.info(
        {
            "event": "http_request",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    )


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        request_id = (request.headers.get("X-Request-ID") or str(uuid.uuid4()))[:64]
        started = time.perf_counter()
        try:
            await request_guard(request)
        except HTTPException as exc:
            logger.warning(
                {
                    "event": "request_rejected",
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": exc.status_code,
                }
            )
            _log_request(request, request_id, started)
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={"X-Request-ID": request_id},
            )
        try:
            response = await call_next(request)
        finally:
            _log_request(request, request_id, started)
        response.headers["X-Request-ID"] = request_id
        return response
