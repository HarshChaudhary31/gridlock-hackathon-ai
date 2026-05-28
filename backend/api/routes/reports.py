"""Report generation API routes."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.services.analytics import AnalyticsService
from backend.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
report_service = ReportService()
analytics_service = AnalyticsService()


@router.get("/traffic/{session_id}")
async def traffic_report(session_id: str, db: AsyncSession = Depends(get_db)):
    path = await report_service.generate_traffic_csv(db, session_id)
    return FileResponse(str(path), filename=path.name, media_type="text/csv")


@router.get("/violations/{session_id}")
async def violations_report(session_id: str, db: AsyncSession = Depends(get_db)):
    path = await report_service.generate_violations_csv(db, session_id)
    return FileResponse(str(path), filename=path.name, media_type="text/csv")


@router.get("/summary/{session_id}")
async def summary_report(session_id: str, db: AsyncSession = Depends(get_db)):
    summary = await analytics_service.get_session_summary(db, session_id)
    if summary["total_frames"] == 0:
        raise HTTPException(404, "No data for session")
    path = await report_service.generate_summary_report(db, session_id, summary)
    return FileResponse(str(path), filename=path.name, media_type="text/plain")
