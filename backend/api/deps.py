"""FastAPI dependencies."""

from backend.database.db import get_db
from backend.services.video_processor import get_video_processor

__all__ = ["get_db", "get_video_processor"]
