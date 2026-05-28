"""Aggregate API router."""

from fastapi import APIRouter

from backend.api.routes import analytics, health, reports, video

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(video.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
