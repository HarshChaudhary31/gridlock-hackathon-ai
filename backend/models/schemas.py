"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CongestionLevel(str, Enum):
    LOW = "Low Traffic"
    MEDIUM = "Medium Traffic"
    HEAVY = "Heavy Traffic"
    GRIDLOCK = "Gridlock"


class SourceType(str, Enum):
    UPLOAD = "upload"
    WEBCAM = "webcam"
    CCTV = "cctv"
    SAMPLE = "sample"


class VehicleCounts(BaseModel):
    total: int = 0
    cars: int = 0
    bikes: int = 0
    buses: int = 0
    trucks: int = 0
    autos: int = 0


class DetectionBox(BaseModel):
    track_id: Optional[int] = None
    class_name: str
    confidence: float
    bbox: List[float]  # x1, y1, x2, y2
    speed_kmh: Optional[float] = None
    direction: Optional[str] = None


class FrameAnalytics(BaseModel):
    frame_number: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    vehicle_counts: VehicleCounts
    congestion_level: CongestionLevel
    congestion_score: float
    density: float
    avg_speed: float
    occupancy: float
    detections: List[DetectionBox] = []
    violations: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []


class ProcessVideoRequest(BaseModel):
    source_type: SourceType = SourceType.UPLOAD
    file_path: Optional[str] = None
    stream_url: Optional[str] = None
    save_output: bool = True
    frame_skip: int = 2


class SessionResponse(BaseModel):
    session_id: str
    status: str
    source_type: str
    started_at: datetime
    message: str = ""


class AnalyticsSummary(BaseModel):
    session_id: str
    total_frames: int
    peak_congestion: Optional[str]
    total_vehicles_detected: int
    violations_count: int
    alerts_count: int
    avg_congestion_score: float
    vehicle_breakdown: VehicleCounts


class AlertResponse(BaseModel):
    id: int
    session_id: str
    timestamp: datetime
    alert_type: str
    severity: str
    message: str
    acknowledged: bool


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    models_loaded: bool
    database: str = "connected"
