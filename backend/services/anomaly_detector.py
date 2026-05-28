"""Accident and traffic anomaly detection."""

from collections import deque
from typing import Deque, Dict, List, Optional

import numpy as np


class AnomalyDetector:
    """
    Detects:
    - Sudden stoppages (many vehicles, near-zero speed)
    - Abnormal clustering
    - Possible accidents
    """

    def __init__(self, window: int = 15) -> None:
        self.speed_window: Deque[float] = deque(maxlen=window)
        self.count_window: Deque[int] = deque(maxlen=window)
        self.last_alert_frame = -100

    def analyze(
        self,
        vehicle_count: int,
        avg_speed: float,
        detections: List[Dict],
        frame_number: int,
        cooldown_frames: int = 90,
    ) -> List[Dict]:
        self.speed_window.append(avg_speed)
        self.count_window.append(vehicle_count)
        anomalies: List[Dict] = []

        if frame_number - self.last_alert_frame < cooldown_frames:
            return anomalies

        if len(self.speed_window) < 5:
            return anomalies

        recent_speeds = list(self.speed_window)[-5:]
        prev_speeds = list(self.speed_window)[-10:-5] if len(self.speed_window) >= 10 else []

        # Sudden stoppage: speed dropped sharply with high vehicle count
        if vehicle_count >= 8 and avg_speed < 2.0:
            if prev_speeds and np.mean(prev_speeds) > 15:
                anomalies.append(
                    {
                        "type": "sudden_stoppage",
                        "severity": "high",
                        "message": "Sudden traffic stoppage detected — possible incident",
                        "frame": frame_number,
                    }
                )
                self.last_alert_frame = frame_number

        # Gridlock anomaly
        if vehicle_count > 20 and avg_speed < 1.5:
            anomalies.append(
                {
                    "type": "gridlock_anomaly",
                    "severity": "medium",
                    "message": "Severe gridlock conditions detected",
                    "frame": frame_number,
                }
            )
            self.last_alert_frame = frame_number

        # Abnormal clustering: many overlapping stationary boxes
        stationary = sum(
            1
            for d in detections
            if d.get("speed_kmh") is not None and d["speed_kmh"] < 1.0
        )
        if stationary >= 6 and vehicle_count >= 10:
            anomalies.append(
                {
                    "type": "abnormal_cluster",
                    "severity": "medium",
                    "message": "Abnormal vehicle clustering — investigate for accident",
                    "frame": frame_number,
                }
            )
            self.last_alert_frame = frame_number

        return anomalies
