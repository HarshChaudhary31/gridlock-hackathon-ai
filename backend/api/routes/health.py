"""Health check endpoints."""

from fastapi import APIRouter

from backend.models.schemas import HealthResponse
from backend.services.detector import get_detector

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    detector = get_detector()
    return HealthResponse(
        status="healthy",
        models_loaded=detector.is_loaded,
        database="connected",
    )
