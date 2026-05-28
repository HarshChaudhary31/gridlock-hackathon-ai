"""SQLAlchemy ORM models for traffic analytics persistence."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class VehicleCountRecord(Base):
    __tablename__ = "vehicle_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    cars: Mapped[int] = mapped_column(Integer, default=0)
    bikes: Mapped[int] = mapped_column(Integer, default=0)
    buses: Mapped[int] = mapped_column(Integer, default=0)
    trucks: Mapped[int] = mapped_column(Integer, default=0)
    autos: Mapped[int] = mapped_column(Integer, default=0)
    frame_number: Mapped[int] = mapped_column(Integer, default=0)


class CongestionRecord(Base):
    __tablename__ = "congestion_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)
    density: Mapped[float] = mapped_column(Float, default=0.0)
    avg_speed: Mapped[float] = mapped_column(Float, default=0.0)
    occupancy: Mapped[float] = mapped_column(Float, default=0.0)
    frame_number: Mapped[int] = mapped_column(Integer, default=0)


class ViolationRecord(Base):
    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    violation_type: Mapped[str] = mapped_column(String(64))
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    screenshot_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    alert_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class AnalyticsSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    output_video_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_frames: Mapped[int] = mapped_column(Integer, default=0)
    peak_congestion: Mapped[str | None] = mapped_column(String(32), nullable=True)
