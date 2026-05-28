"""Analytics aggregation and database persistence."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.schema import (
    AlertRecord,
    AnalyticsSession,
    CongestionRecord,
    VehicleCountRecord,
    ViolationRecord,
)
from backend.models.schemas import VehicleCounts


class AnalyticsService:
    async def create_session(
        self,
        db: AsyncSession,
        session_id: str,
        source_type: str,
        source_path: Optional[str] = None,
    ) -> None:
        db.add(
            AnalyticsSession(
                session_id=session_id,
                source_type=source_type,
                source_path=source_path,
                status="active",
            )
        )
        await db.flush()

    async def end_session(
        self,
        db: AsyncSession,
        session_id: str,
        output_path: Optional[str],
        total_frames: int,
        peak_congestion: Optional[str],
    ) -> None:
        result = await db.execute(
            select(AnalyticsSession).where(AnalyticsSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.status = "completed"
            session.ended_at = datetime.utcnow()
            session.output_video_path = output_path
            session.total_frames = total_frames
            session.peak_congestion = peak_congestion
            await db.flush()

    async def save_frame_analytics(
        self,
        db: AsyncSession,
        session_id: str,
        frame_number: int,
        counts: VehicleCounts,
        congestion: Dict[str, Any],
    ) -> None:
        db.add(
            VehicleCountRecord(
                session_id=session_id,
                frame_number=frame_number,
                total=counts.total,
                cars=counts.cars,
                bikes=counts.bikes,
                buses=counts.buses,
                trucks=counts.trucks,
                autos=counts.autos,
            )
        )
        db.add(
            CongestionRecord(
                session_id=session_id,
                frame_number=frame_number,
                level=congestion["level"].value if hasattr(congestion["level"], "value") else str(congestion["level"]),
                score=congestion["score"],
                density=congestion["density"],
                avg_speed=congestion["avg_speed"],
                occupancy=congestion["occupancy"],
            )
        )

    async def save_violation(
        self,
        db: AsyncSession,
        session_id: str,
        violation: Dict,
        screenshot_path: Optional[str] = None,
    ) -> None:
        db.add(
            ViolationRecord(
                session_id=session_id,
                violation_type=violation.get("type", "unknown"),
                track_id=violation.get("track_id"),
                confidence=violation.get("confidence", 0.0),
                screenshot_path=screenshot_path,
                details=violation.get("details"),
            )
        )

    async def save_alert(self, db: AsyncSession, session_id: str, alert: Dict) -> None:
        db.add(
            AlertRecord(
                session_id=session_id,
                alert_type=alert.get("alert_type", "general"),
                severity=alert.get("severity", "medium"),
                message=alert.get("message", ""),
            )
        )

    async def get_session_summary(self, db: AsyncSession, session_id: str) -> Dict:
        counts_result = await db.execute(
            select(
                func.sum(VehicleCountRecord.total),
                func.avg(VehicleCountRecord.cars),
                func.avg(VehicleCountRecord.bikes),
                func.avg(VehicleCountRecord.buses),
                func.avg(VehicleCountRecord.trucks),
                func.avg(VehicleCountRecord.autos),
            ).where(VehicleCountRecord.session_id == session_id)
        )
        row = counts_result.one()

        cong_result = await db.execute(
            select(func.avg(CongestionRecord.score), func.max(CongestionRecord.score)).where(
                CongestionRecord.session_id == session_id
            )
        )
        cong_row = cong_result.one()

        violations = await db.execute(
            select(func.count()).select_from(ViolationRecord).where(
                ViolationRecord.session_id == session_id
            )
        )
        alerts = await db.execute(
            select(func.count()).select_from(AlertRecord).where(AlertRecord.session_id == session_id)
        )

        session_result = await db.execute(
            select(AnalyticsSession).where(AnalyticsSession.session_id == session_id)
        )
        session = session_result.scalar_one_or_none()

        return {
            "session_id": session_id,
            "total_frames": session.total_frames if session else 0,
            "peak_congestion": session.peak_congestion if session else None,
            "total_vehicles_detected": int(row[0] or 0),
            "avg_congestion_score": float(cong_row[0] or 0),
            "max_congestion_score": float(cong_row[1] or 0),
            "violations_count": violations.scalar() or 0,
            "alerts_count": alerts.scalar() or 0,
            "vehicle_breakdown": VehicleCounts(
                cars=int(row[1] or 0),
                bikes=int(row[2] or 0),
                buses=int(row[3] or 0),
                trucks=int(row[4] or 0),
                autos=int(row[5] or 0),
                total=int(row[0] or 0),
            ),
        }

    async def get_congestion_history(
        self, db: AsyncSession, session_id: str, limit: int = 500
    ) -> List[Dict]:
        result = await db.execute(
            select(CongestionRecord)
            .where(CongestionRecord.session_id == session_id)
            .order_by(CongestionRecord.timestamp.desc())
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "level": r.level,
                "score": r.score,
                "density": r.density,
                "avg_speed": r.avg_speed,
            }
            for r in reversed(records)
        ]

    async def get_alerts(self, db: AsyncSession, session_id: Optional[str] = None, limit: int = 50) -> List:
        q = select(AlertRecord).order_by(AlertRecord.timestamp.desc()).limit(limit)
        if session_id:
            q = q.where(AlertRecord.session_id == session_id)
        result = await db.execute(q)
        return result.scalars().all()
