"""Aggregates every route module into a single router."""

from fastapi import APIRouter

from greenlight.api.routes import health, incidents, telegram, webhooks

api_router = APIRouter()
for module in (health, incidents, webhooks, telegram):
    api_router.include_router(module.router)
