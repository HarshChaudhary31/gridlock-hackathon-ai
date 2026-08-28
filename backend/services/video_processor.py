"""Main video processing pipeline orchestrating all AI services."""

import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

from backend.config import get_settings
from backend.models.schemas import CongestionLevel, VehicleCounts
from backend.services.alert_service import AlertService
from backend.services.analytics import AnalyticsService
from backend.services.anomaly_detector import AnomalyDetector
from backend.services.congestion import CongestionAnalyzer
from backend.services.detector import get_detector
from backend.services.heatmap import HeatmapGenerator
from backend.services.tracker import TrackState
from backend.services.visualizer import FrameVisualizer
from backend.utils.logger import logger

settings = get_settings()


class VideoProcessor:
    """Processes video streams frame-by-frame with full analytics pipeline."""

    def __init__(self) -> None:
        self.detector = get_detector()
        self.congestion_analyzer = CongestionAnalyzer()
        self.track_state = TrackState()
        self.heatmap = HeatmapGenerator(decay=settings.HEATMAP_DECAY)
        self.anomaly_detector = AnomalyDetector()
        self.alert_service = AlertService()
        self.visualizer = FrameVisualizer()
        self.analytics_service = AnalyticsService()
        self._sessions: Dict[str, Dict] = {}
        self._peak_congestion: Dict[str, str] = {}
        self._session_accum: Dict[str, Dict[str, Any]] = {}

    def _count_vehicles(self, detections: List[Dict]) -> VehicleCounts:
        counts = defaultdict(int)
        for d in detections:
            if d["class_name"] == "person":
                continue
            counts[d["class_name"]] += 1
        total = sum(counts.values())
        return VehicleCounts(
            total=total,
            cars=counts.get("car", 0),
            bikes=counts.get("bike", 0),
            buses=counts.get("bus", 0),
            trucks=counts.get("truck", 0),
            autos=counts.get("auto", 0),
        )

    def _counts_payload(self, detections: List[Dict], counts: VehicleCounts) -> Dict[str, int]:
        dumped = counts.model_dump()
        extra = defaultdict(int)
        for d in detections:
            name = d["class_name"]
            if name not in {"car", "bike", "bus", "truck", "auto", "person"}:
                extra[name] += 1
        dumped.update(extra)
        return dumped

    def _init_accum(self, session_id: str) -> Dict[str, Any]:
        accum = {
            "unique_vehicles": defaultdict(set),
            "speeds": [],
            "max_speed": None,
            "helmet_ids": set(),
            "no_helmet_ids": set(),
            "rider_ids": set(),
            "violation_keys": set(),
            "violation_counts": defaultdict(int),
            "violation_events": [],
            "overspeed_ids": set(),
        }
        self._session_accum[session_id] = accum
        return accum

    def _build_session_stats(
        self,
        accum: Dict[str, Any],
        current_avg_speed: float,
        current_counts: Dict[str, int],
        per_vehicle_speed: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        unique = accum["unique_vehicles"]
        vehicles: Dict[str, int] = {}
        for cls_name, ids in unique.items():
            key = {"car": "cars", "bike": "bikes", "bus": "buses", "truck": "trucks", "auto": "autos"}.get(
                cls_name, cls_name
            )
            vehicles[key] = len(ids)
        vehicles["total"] = sum(len(ids) for ids in unique.values())
        if vehicles["total"] == 0:
            vehicles = dict(current_counts)

        speeds = accum["speeds"]
        avg_speed = float(np.mean(speeds)) if speeds else current_avg_speed
        max_speed = accum["max_speed"]
        helmet_n = len(accum["helmet_ids"])
        no_helmet_n = len(accum["no_helmet_ids"])
        riders = len(accum["rider_ids"]) or (helmet_n + no_helmet_n)

        return {
            "vehicles": vehicles,
            "speed": {
                "current": current_avg_speed,
                "average": round(avg_speed, 2) if avg_speed is not None else None,
                "max": round(max_speed, 2) if max_speed is not None else None,
                "violations": len(accum["overspeed_ids"]),
                "per_vehicle": per_vehicle_speed,
            },
            "helmet": {
                "riders_checked": riders,
                "helmet": helmet_n,
                "no_helmet": no_helmet_n,
                "violations": no_helmet_n,
            },
            "violation_counts": dict(accum["violation_counts"]),
            "violation_events": accum["violation_events"][-50:],
        }

    def _update_accum(
        self,
        accum: Dict[str, Any],
        detections: List[Dict],
        violations: List[Dict],
        helmet_stats: Dict[str, Any],
        speed_limit: float,
    ) -> List[Dict[str, Any]]:
        per_vehicle_speed: List[Dict[str, Any]] = []
        for d in detections:
            if d["class_name"] == "person":
                continue
            tid = d.get("track_id")
            if tid is not None:
                accum["unique_vehicles"][d["class_name"]].add(tid)
            sp = d.get("speed_kmh")
            if sp is not None:
                accum["speeds"].append(sp)
                if accum["max_speed"] is None or sp > accum["max_speed"]:
                    accum["max_speed"] = sp
                per_vehicle_speed.append(
                    {
                        "track_id": tid,
                        "class_name": d["class_name"],
                        "speed_kmh": round(float(sp), 2),
                    }
                )
                if tid is not None and sp > speed_limit:
                    accum["overspeed_ids"].add(tid)
                    key = ("overspeeding", tid)
                    if key not in accum["violation_keys"]:
                        accum["violation_keys"].add(key)
                        accum["violation_counts"]["overspeeding"] += 1
                        accum["violation_events"].append(
                            {
                                "type": "overspeeding",
                                "track_id": tid,
                                "confidence": 0.8,
                                "bbox": d["bbox"],
                                "details": f"Speed {sp:.1f} km/h exceeds {speed_limit:.0f} km/h",
                                "speed_kmh": round(float(sp), 2),
                            }
                        )

        for tid in helmet_stats.get("helmet_track_ids") or []:
            accum["helmet_ids"].add(tid)
            accum["rider_ids"].add(tid)
            accum["no_helmet_ids"].discard(tid)
        for tid in helmet_stats.get("no_helmet_track_ids") or []:
            accum["no_helmet_ids"].add(tid)
            accum["rider_ids"].add(tid)
            accum["helmet_ids"].discard(tid)

        for v in violations:
            tid = v.get("track_id")
            vtype = v.get("type", "unknown")
            key = (vtype, tid)
            if key in accum["violation_keys"]:
                continue
            accum["violation_keys"].add(key)
            accum["violation_counts"][vtype] += 1
            accum["violation_events"].append(v)

        return per_vehicle_speed

    def _update_peak(self, session_id: str, level: CongestionLevel) -> None:
        order = ["Low Traffic", "Medium Traffic", "Heavy Traffic", "Gridlock"]
        current = self._peak_congestion.get(session_id, "Low Traffic")
        level_str = level.value if hasattr(level, "value") else str(level)
        if order.index(level_str) > order.index(current):
            self._peak_congestion[session_id] = level_str

    async def process_video(
        self,
        source_path: str,
        session_id: Optional[str] = None,
        save_output: bool = True,
        frame_skip: int = 2,
        progress_callback: Optional[Callable[[Dict], None]] = None,
        db_session=None,
        max_frames: Optional[int] = None,
    ) -> Dict[str, Any]:
        session_id = session_id or str(uuid.uuid4())[:12]
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {source_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.track_state = TrackState(fps=fps)
        self.track_state.set_counting_line(height)
        self.congestion_analyzer = CongestionAnalyzer()
        self.heatmap.reset((height, width))
        self.anomaly_detector = AnomalyDetector()

        writer = None
        output_path = None
        if save_output:
            output_path = str(settings.OUTPUT_DIR / f"processed_{session_id}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_path, fourcc, fps / frame_skip, (width, height))

        if db_session:
            await self.analytics_service.create_session(
                db_session, session_id, "upload", source_path
            )

        frame_number = 0
        processed = 0
        latest_state: Dict[str, Any] = {}

        self._sessions[session_id] = {"status": "processing", "latest": {}}
        self._peak_congestion[session_id] = "Low Traffic"
        accum = self._init_accum(session_id)
        speed_limit = settings.SPEED_LIMIT_KMH

        try:
            self.detector.load()
        except Exception as e:
            logger.warning("Detector load deferred: %s", e)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1
            if frame_number % frame_skip != 0:
                continue

            if max_frames and processed >= max_frames:
                break

            detections, _ = self.detector.detect(frame, track=True)
            persons = [d for d in detections if d["class_name"] == "person"]
            vehicles = [d for d in detections if d["class_name"] != "person"]
            bikes = [d for d in vehicles if d["class_name"] == "bike"]

            speeds = []
            for det in detections:
                if det.get("track_id") is not None and det["class_name"] != "person":
                    motion = self.track_state.update(
                        det["track_id"], det["bbox"], frame_number
                    )
                    det["speed_kmh"] = motion["speed_kmh"]
                    det["direction"] = motion["direction"]
                    if motion["speed_kmh"] is not None:
                        speeds.append(motion["speed_kmh"])

            violations, helmet_stats = self.detector.detect_helmets(frame, bikes, persons)

            counts = self._count_vehicles(detections)
            counts_payload = self._counts_payload(detections, counts)
            congestion = self.congestion_analyzer.analyze(detections, frame.shape, speeds)
            self._update_peak(session_id, congestion["level"])
            per_vehicle_speed = self._update_accum(
                accum, detections, violations, helmet_stats, speed_limit
            )
            session_stats = self._build_session_stats(
                accum, congestion["avg_speed"], counts_payload, per_vehicle_speed
            )
            for d in detections:
                sp = d.get("speed_kmh")
                if d["class_name"] == "person" or sp is None or sp <= speed_limit:
                    continue
                violations.append(
                    {
                        "type": "overspeeding",
                        "track_id": d.get("track_id"),
                        "confidence": 0.8,
                        "bbox": d["bbox"],
                        "details": f"Speed {sp:.1f} km/h exceeds {speed_limit:.0f} km/h",
                        "speed_kmh": round(float(sp), 2),
                    }
                )

            anomalies = self.anomaly_detector.analyze(
                counts.total,
                congestion["avg_speed"],
                detections,
                frame_number,
            )

            alerts: List[Dict] = []
            cong_alert = self.alert_service.check_congestion(
                congestion["level"].value if hasattr(congestion["level"], "value") else str(congestion["level"]),
                congestion["score"],
            )
            if cong_alert:
                alerts.append(cong_alert)
            for v in violations:
                va = self.alert_service.check_violation(v)
                if va:
                    alerts.append(va)
            for a in anomalies:
                aa = self.alert_service.check_anomaly(a)
                if aa:
                    alerts.append(aa)

            self.heatmap.update(detections, frame.shape)
            vis_frame = self.visualizer.draw_frame(
                frame,
                detections,
                congestion,
                counts_payload,
                violations,
                session_id,
                frame_number,
                {"entry": self.track_state.entry_count, "exit": self.track_state.exit_count},
            )
            heat_frame = self.heatmap.render(vis_frame)
            if writer:
                writer.write(heat_frame)

            # Save violation screenshots
            for v in violations:
                vpath = settings.OUTPUT_DIR / f"violation_{session_id}_{frame_number}_{v['type']}.jpg"
                x1, y1, x2, y2 = [int(x) for x in v["bbox"]]
                crop = frame[max(0, y1) : y2, max(0, x1) : x2]
                if crop.size > 0:
                    cv2.imwrite(str(vpath), crop)
                    v["screenshot"] = str(vpath)

            if db_session and processed % 5 == 0:
                await self.analytics_service.save_frame_analytics(
                    db_session, session_id, frame_number, counts, congestion
                )
                for v in violations:
                    await self.analytics_service.save_violation(
                        db_session, session_id, v, v.get("screenshot")
                    )
                for al in alerts:
                    await self.analytics_service.save_alert(db_session, session_id, al)

            processed += 1
            latest_state = {
                "session_id": session_id,
                "frame_number": frame_number,
                "processed_frames": processed,
                "total_frames": total_frames,
                "progress": min(frame_number / max(total_frames, 1), 1.0),
                "vehicle_counts": counts_payload,
                "vehicles": session_stats["vehicles"],
                "speed": session_stats["speed"],
                "helmet": session_stats["helmet"],
                "violation_counts": session_stats["violation_counts"],
                "violation_events": session_stats["violation_events"],
                "congestion": {
                    "level": congestion["level"].value if hasattr(congestion["level"], "value") else str(congestion["level"]),
                    "score": congestion["score"],
                    "density": congestion["density"],
                    "avg_speed": congestion["avg_speed"],
                    "occupancy": congestion["occupancy"],
                },
                "violations": violations,
                "alerts": alerts,
                "anomalies": anomalies,
                "hotspots": self.heatmap.get_hotspots(),
                "flow": self.track_state.get_flow_stats(),
                "entry_exit": {
                    "entry": self.track_state.entry_count,
                    "exit": self.track_state.exit_count,
                },
                "output_frame_path": None,
            }

            # Save latest frame for dashboard polling
            frame_path = settings.OUTPUT_DIR / f"latest_{session_id}.jpg"
            cv2.imwrite(str(frame_path), heat_frame)
            latest_state["output_frame_path"] = str(frame_path)

            self._sessions[session_id]["latest"] = latest_state

            if progress_callback:
                progress_callback(latest_state)

        cap.release()
        if writer:
            writer.release()

        if db_session:
            await self.analytics_service.end_session(
                db_session,
                session_id,
                output_path,
                processed,
                self._peak_congestion.get(session_id),
            )

        self._sessions[session_id]["status"] = "completed"
        final_stats = self._build_session_stats(
            accum,
            latest_state.get("congestion", {}).get("avg_speed", 0.0) if latest_state else 0.0,
            latest_state.get("vehicle_counts", {}) if latest_state else {},
            latest_state.get("speed", {}).get("per_vehicle", []) if latest_state else [],
        )
        if latest_state:
            latest_state.update(
                {
                    "vehicles": final_stats["vehicles"],
                    "speed": final_stats["speed"],
                    "helmet": final_stats["helmet"],
                    "violation_counts": final_stats["violation_counts"],
                    "violation_events": final_stats["violation_events"],
                    "output_video": output_path,
                }
            )
            self._sessions[session_id]["latest"] = latest_state
        return {
            "session_id": session_id,
            "status": "completed",
            "processed_frames": processed,
            "output_video": output_path,
            "peak_congestion": self._peak_congestion.get(session_id),
            "latest": latest_state,
            "vehicles": final_stats["vehicles"],
            "speed": final_stats["speed"],
            "helmet": final_stats["helmet"],
            "violation_counts": final_stats["violation_counts"],
            "violation_events": final_stats["violation_events"],
        }

    def get_session_state(self, session_id: str) -> Optional[Dict]:
        return self._sessions.get(session_id)

    def generate_sample_video(self, output_path: str, duration_sec: int = 10, fps: int = 25) -> str:
        """Generate synthetic traffic video for demo/testing."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        w, h = 1280, 720
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
        total = duration_sec * fps
        for i in range(total):
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:] = (40, 45, 50)
            # Road
            cv2.rectangle(frame, (0, h // 2 - 80), (w, h // 2 + 80), (60, 60, 60), -1)
            cv2.line(frame, (0, h // 2), (w, h // 2), (200, 200, 200), 2)
            # Moving vehicles
            n_vehicles = 5 + int(8 * (0.5 + 0.5 * np.sin(i / 30)))
            for j in range(n_vehicles):
                x = int((i * (12 + j * 3) + j * 200) % (w + 100)) - 50
                y = h // 2 - 40 + (j % 3) * 50
                color = [(0, 165, 255), (0, 255, 0), (255, 0, 0), (128, 0, 128)][j % 4]
                cv2.rectangle(frame, (x, y), (x + 80, y + 45), color, -1)
            cv2.putText(
                frame,
                f"Bengaluru Traffic Sim | Frame {i}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            writer.write(frame)
        writer.release()
        return str(path)


_processor: Optional[VideoProcessor] = None


def get_video_processor() -> VideoProcessor:
    global _processor
    if _processor is None:
        _processor = VideoProcessor()
    return _processor
