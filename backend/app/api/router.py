"""Aggregate API routers. Feature routers are included here as they are added."""

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
