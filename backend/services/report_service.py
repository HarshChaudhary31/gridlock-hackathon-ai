"""CSV and analytics report generation."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.schema import AlertRecord, CongestionRecord, VehicleCountRecord, ViolationRecord

settings = get_settings()


class ReportService:
    async def generate_traffic_csv(self, db: AsyncSession, session_id: str) -> Path:
        out_path = settings.REPORTS_DIR / f"traffic_{session_id}_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"

        counts = await db.execute(
            select(VehicleCountRecord).where(VehicleCountRecord.session_id == session_id)
        )
        cong = await db.execute(
            select(CongestionRecord).where(CongestionRecord.session_id == session_id)
        )

        rows = []
        count_records = {r.frame_number: r for r in counts.scalars().all()}
        for c in cong.scalars().all():
            vc = count_records.get(c.frame_number)
            rows.append(
                {
                    "timestamp": c.timestamp.isoformat(),
                    "frame": c.frame_number,
                    "congestion_level": c.level,
                    "congestion_score": c.score,
                    "density": c.density,
                    "avg_speed": c.avg_speed,
                    "occupancy": c.occupancy,
                    "total_vehicles": vc.total if vc else 0,
                    "cars": vc.cars if vc else 0,
                    "bikes": vc.bikes if vc else 0,
                    "buses": vc.buses if vc else 0,
                    "trucks": vc.trucks if vc else 0,
                    "autos": vc.autos if vc else 0,
                }
            )

        df = pd.DataFrame(rows)
        df.to_csv(out_path, index=False)
        return out_path

    async def generate_violations_csv(self, db: AsyncSession, session_id: str) -> Path:
        out_path = settings.REPORTS_DIR / f"violations_{session_id}_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
        result = await db.execute(
            select(ViolationRecord).where(ViolationRecord.session_id == session_id)
        )
        rows = [
            {
                "timestamp": v.timestamp.isoformat(),
                "type": v.violation_type,
                "track_id": v.track_id,
                "confidence": v.confidence,
                "screenshot": v.screenshot_path,
                "details": v.details,
            }
            for v in result.scalars().all()
        ]
        pd.DataFrame(rows).to_csv(out_path, index=False)
        return out_path

    async def generate_summary_report(self, db: AsyncSession, session_id: str, summary: dict) -> Path:
        out_path = settings.REPORTS_DIR / f"summary_{session_id}_{datetime.utcnow():%Y%m%d_%H%M%S}.txt"
        vb = summary.get("vehicle_breakdown", {})
        if hasattr(vb, "model_dump"):
            vb = vb.model_dump()

        content = f"""
TRAFFIC MOBILITY INTELLIGENCE REPORT
=====================================
Session ID: {session_id}
Generated: {datetime.utcnow().isoformat()} UTC
Location Context: Bengaluru Smart Traffic Monitoring

SUMMARY
-------
Total Frames Processed: {summary.get('total_frames', 0)}
Peak Congestion Level: {summary.get('peak_congestion', 'N/A')}
Average Congestion Score: {summary.get('avg_congestion_score', 0):.3f}
Total Vehicle Detections: {summary.get('total_vehicles_detected', 0)}
Violations Detected: {summary.get('violations_count', 0)}
Alerts Generated: {summary.get('alerts_count', 0)}

VEHICLE BREAKDOWN (avg per frame)
---------------------------------
Cars: {vb.get('cars', 0)}
Bikes: {vb.get('bikes', 0)}
Buses: {vb.get('buses', 0)}
Trucks: {vb.get('trucks', 0)}
Auto-rickshaws: {vb.get('autos', 0)}

RECOMMENDATIONS
---------------
- Deploy dynamic signal timing at peak congestion corridors
- Increase enforcement at helmet violation hotspots
- Route advisory for gridlock-prone zones during peak hours
"""
        out_path.write_text(content.strip())
        return out_path
