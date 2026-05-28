"""Analytics and alerts API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.models.schemas import AlertResponse, AnalyticsSummary
from backend.services.analytics import AnalyticsService
from backend.services.forecast import CongestionForecaster
from backend.services.video_processor import get_video_processor

router = APIRouter(prefix="/analytics", tags=["analytics"])
analytics_service = AnalyticsService()
forecaster = CongestionForecaster()


@router.get("/summary/{session_id}", response_model=AnalyticsSummary)
async def get_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    summary = await analytics_service.get_session_summary(db, session_id)
    if summary["total_frames"] == 0:
        proc = get_video_processor()
        state = proc.get_session_state(session_id)
        if not state:
            raise HTTPException(404, "Session not found")
    return AnalyticsSummary(**summary)


@router.get("/congestion/{session_id}")
async def congestion_history(session_id: str, limit: int = 200, db: AsyncSession = Depends(get_db)):
    history = await analytics_service.get_congestion_history(db, session_id, limit)
    return {"session_id": session_id, "history": history}


@router.get("/alerts")
async def list_alerts(
    session_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    alerts = await analytics_service.get_alerts(db, session_id, limit)
    return [
        AlertResponse(
            id=a.id,
            session_id=a.session_id,
            timestamp=a.timestamp,
            alert_type=a.alert_type,
            severity=a.severity,
            message=a.message,
            acknowledged=a.acknowledged,
        )
        for a in alerts
    ]


@router.get("/live/{session_id}")
async def live_metrics(session_id: str):
    proc = get_video_processor()
    state = proc.get_session_state(session_id)
    if not state or not state.get("latest"):
        raise HTTPException(404, "No live data for session")
    latest = state["latest"]
    if "congestion" in latest and "score" in latest["congestion"]:
        forecaster.update(latest["congestion"]["score"])
    predictions = forecaster.predict(10)
    recommendation = forecaster.signal_recommendation(
        latest.get("congestion", {}).get("level", "Low Traffic"), predictions
    )
    return {
        **latest,
        "forecast": predictions,
        "signal_recommendation": recommendation,
    }
