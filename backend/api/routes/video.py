"""Video upload and processing API routes."""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.db import get_db
from backend.models.schemas import SessionResponse, SourceType
from backend.services.video_processor import get_video_processor
from backend.utils.logger import logger

router = APIRouter(prefix="/video", tags=["video"])
settings = get_settings()

_processing_tasks: dict = {}


class ProcessRequest(BaseModel):
    file_path: Optional[str] = None
    source_type: SourceType = SourceType.UPLOAD
    save_output: bool = True
    frame_skip: int = 2
    max_frames: Optional[int] = None


async def _run_processing(
    session_id: str,
    source_path: str,
    save_output: bool,
    frame_skip: int,
    max_frames: Optional[int],
):
    processor = get_video_processor()
    from backend.database.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result = await processor.process_video(
                source_path,
                session_id=session_id,
                save_output=save_output,
                frame_skip=frame_skip,
                max_frames=max_frames,
                db_session=db,
            )
            await db.commit()
            _processing_tasks[session_id] = {"status": "completed", "result": result}
        except Exception as e:
            logger.exception("Processing failed: %s", e)
            _processing_tasks[session_id] = {"status": "failed", "error": str(e)}


@router.post("/upload", response_model=SessionResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    frame_skip: int = 2,
    save_output: bool = True,
    max_frames: Optional[int] = None,
):
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        raise HTTPException(400, "Unsupported video format")

    session_id = str(uuid.uuid4())[:12]
    dest = settings.UPLOAD_DIR / f"{session_id}{ext}"
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    _processing_tasks[session_id] = {"status": "processing"}
    background_tasks.add_task(
        _run_processing, session_id, str(dest), save_output, frame_skip, max_frames
    )

    return SessionResponse(
        session_id=session_id,
        status="processing",
        source_type="upload",
        started_at=__import__("datetime").datetime.utcnow(),
        message=f"Video uploaded. Processing started: {dest.name}",
    )


@router.post("/process", response_model=SessionResponse)
async def process_existing(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
):
    if not request.file_path:
        raise HTTPException(400, "file_path required")

    path = Path(request.file_path)
    if not path.exists():
        # Try relative to project
        path = settings.BASE_DIR / request.file_path
    if not path.exists():
        raise HTTPException(404, f"File not found: {request.file_path}")

    session_id = str(uuid.uuid4())[:12]
    _processing_tasks[session_id] = {"status": "processing"}
    background_tasks.add_task(
        _run_processing,
        session_id,
        str(path),
        request.save_output,
        request.frame_skip,
        request.max_frames,
    )

    return SessionResponse(
        session_id=session_id,
        status="processing",
        source_type=request.source_type.value,
        started_at=__import__("datetime").datetime.utcnow(),
        message="Processing started",
    )


@router.post("/sample/generate")
async def generate_sample(duration_sec: int = 10):
    processor = get_video_processor()
    path = settings.DATA_DIR / "sample" / "bengaluru_traffic_sample.mp4"
    out = processor.generate_sample_video(str(path), duration_sec=duration_sec)
    return {"path": out, "message": "Sample video generated"}


@router.post("/sample/process", response_model=SessionResponse)
async def process_sample(
    background_tasks: BackgroundTasks,
    duration_sec: int = 10,
    frame_skip: int = 2,
    max_frames: Optional[int] = 150,
):
    processor = get_video_processor()
    path = settings.DATA_DIR / "sample" / "bengaluru_traffic_sample.mp4"
    if not path.exists():
        processor.generate_sample_video(str(path), duration_sec=duration_sec)

    session_id = str(uuid.uuid4())[:12]
    _processing_tasks[session_id] = {"status": "processing"}
    background_tasks.add_task(
        _run_processing, session_id, str(path), True, frame_skip, max_frames
    )

    return SessionResponse(
        session_id=session_id,
        status="processing",
        source_type="sample",
        started_at=__import__("datetime").datetime.utcnow(),
        message="Sample video processing started",
    )


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    task = _processing_tasks.get(session_id)
    processor = get_video_processor()
    live = processor.get_session_state(session_id)

    if task:
        resp = {"session_id": session_id, **task}
        result = task.get("result") if isinstance(task, dict) else None
        if live and live.get("latest"):
            resp["latest"] = live["latest"]
        elif isinstance(result, dict) and result.get("latest"):
            resp["latest"] = result["latest"]
        if isinstance(result, dict):
            for key in (
                "vehicles",
                "speed",
                "helmet",
                "violation_counts",
                "violation_events",
                "output_video",
                "processed_frames",
                "peak_congestion",
            ):
                if key in result and key not in resp:
                    resp[key] = result[key]
        output_path = settings.OUTPUT_DIR / f"processed_{session_id}.mp4"
        if output_path.exists():
            resp["output_video_url"] = f"/api/v1/video/output/{session_id}"
        return resp

    if live:
        resp = {
            "session_id": session_id,
            "status": live.get("status", "unknown"),
            "latest": live.get("latest"),
        }
        output_path = settings.OUTPUT_DIR / f"processed_{session_id}.mp4"
        if output_path.exists():
            resp["output_video_url"] = f"/api/v1/video/output/{session_id}"
        return resp

    raise HTTPException(404, "Session not found")


@router.get("/output/{session_id}")
async def get_processed_video(session_id: str):
    path = settings.OUTPUT_DIR / f"processed_{session_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "Processed video not available yet")
    from fastapi.responses import FileResponse

    return FileResponse(str(path), media_type="video/mp4", filename=path.name)


@router.get("/frame/{session_id}")
async def get_latest_frame(session_id: str):
    path = settings.OUTPUT_DIR / f"latest_{session_id}.jpg"
    if not path.exists():
        raise HTTPException(404, "No frame available yet")
    from fastapi.responses import FileResponse

    return FileResponse(str(path), media_type="image/jpeg")
