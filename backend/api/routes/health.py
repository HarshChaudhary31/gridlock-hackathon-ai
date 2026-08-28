"""Health check endpoints."""

from fastapi import APIRouter

from backend.models.schemas import HealthResponse
from backend.services.detector import get_detector

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    detector = get_detector()

    try:
        detector.load()
        models_loaded = detector.is_loaded
    except Exception:
        models_loaded = False

    return HealthResponse(
        status="healthy" if models_loaded else "degraded",
        models_loaded=models_loaded,
        database="connected",
    )
