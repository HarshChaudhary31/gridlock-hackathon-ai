"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    WEIGHTS_DIR: Path = BASE_DIR / "weights"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DATA_DIR: Path = BASE_DIR / "data"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./traffic_ai.db"

    # ML Models
    YOLO_VEHICLE_MODEL: str = "yolov8n.pt"
    YOLO_HELMET_MODEL: str = "yolov8n.pt"
    CONFIDENCE_THRESHOLD: float = 0.35
    IOU_THRESHOLD: float = 0.45
    DEVICE: str = "cpu"  # cuda | cpu | mps

    # Processing
    FRAME_SKIP: int = 2
    MAX_FPS_PROCESS: int = 15
    HEATMAP_DECAY: float = 0.98
    TRACK_MAX_AGE: int = 30

    # Congestion thresholds (density score 0-1)
    CONGESTION_LOW: float = 0.25
    CONGESTION_MEDIUM: float = 0.50
    CONGESTION_HEAVY: float = 0.75

    # Alerts
    ENABLE_ALERTS: bool = True
    ALERT_COOLDOWN_SEC: int = 30

    # Streamlit
    STREAMLIT_PORT: int = 8501
    BACKEND_URL: str = "http://localhost:8000"

    def ensure_dirs(self) -> None:
        for d in (
            self.UPLOAD_DIR,
            self.OUTPUT_DIR,
            self.REPORTS_DIR,
            self.WEIGHTS_DIR,
            self.LOGS_DIR,
            self.DATA_DIR,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
