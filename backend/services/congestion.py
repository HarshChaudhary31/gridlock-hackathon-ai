"""Traffic congestion classification engine."""

from typing import Dict, List, Tuple

import numpy as np

from backend.config import get_settings
from backend.models.schemas import CongestionLevel

settings = get_settings()


class CongestionAnalyzer:
    """
    Classifies traffic congestion using:
    - Vehicle density (count / ROI area)
    - Lane occupancy (bbox coverage ratio)
    - Average movement speed
    - Traffic flow stability
    """

    def __init__(self) -> None:
        self.speed_history: List[float] = []
        self.density_history: List[float] = []

    def analyze(
        self,
        detections: List[Dict],
        frame_shape: Tuple[int, ...],
        speeds: List[float],
    ) -> Dict:
        h, w = frame_shape[:2]
        frame_area = h * w

        vehicle_dets = [d for d in detections if d["class_name"] != "person"]
        count = len(vehicle_dets)

        # Density: vehicles per 100k pixels
        density = min(count / (frame_area / 100000), 1.0)

        # Occupancy: sum of bbox areas / frame
        occupancy = 0.0
        for d in vehicle_dets:
            x1, y1, x2, y2 = d["bbox"]
            occupancy += (x2 - x1) * (y2 - y1)
        occupancy = min(occupancy / frame_area, 1.0)

        # Average speed
        valid_speeds = [s for s in speeds if s is not None and s > 0]
        avg_speed = float(np.mean(valid_speeds)) if valid_speeds else 0.0

        self.speed_history.append(avg_speed)
        self.density_history.append(density)
        if len(self.speed_history) > 60:
            self.speed_history.pop(0)
            self.density_history.pop(0)

        # Flow stability: variance in recent speeds
        flow_variance = float(np.std(self.speed_history[-15:])) if len(self.speed_history) >= 3 else 0.0
        low_movement = avg_speed < 5.0 and count >= 5

        # Composite congestion score (0-1)
        density_score = density * 0.35 + occupancy * 0.35
        speed_score = max(0, 1.0 - avg_speed / 40.0) * 0.2
        stall_score = (0.15 if low_movement else 0.0) + (0.1 if flow_variance < 2 and count > 8 else 0.0)

        score = min(density_score + speed_score + stall_score, 1.0)

        level = self._classify(score, count, avg_speed)
        return {
            "level": level,
            "score": round(score, 3),
            "density": round(density, 3),
            "occupancy": round(occupancy, 3),
            "avg_speed": round(avg_speed, 2),
            "vehicle_count": count,
        }

    def _classify(self, score: float, count: int, avg_speed: float) -> CongestionLevel:
        if score >= settings.CONGESTION_HEAVY and (avg_speed < 8 or count > 25):
            if score >= 0.9 or (count > 35 and avg_speed < 3):
                return CongestionLevel.GRIDLOCK
            return CongestionLevel.HEAVY
        if score >= settings.CONGESTION_MEDIUM:
            return CongestionLevel.MEDIUM
        if score >= settings.CONGESTION_LOW:
            return CongestionLevel.LOW
        return CongestionLevel.LOW
