"""Alert generation and cooldown management."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from backend.config import get_settings

settings = get_settings()


class AlertService:
    def __init__(self) -> None:
        self._last_alert: Dict[str, datetime] = {}

    def _can_alert(self, key: str) -> bool:
        if not settings.ENABLE_ALERTS:
            return False
        last = self._last_alert.get(key)
        if last is None:
            return True
        return datetime.utcnow() - last > timedelta(seconds=settings.ALERT_COOLDOWN_SEC)

    def _mark_alert(self, key: str) -> None:
        self._last_alert[key] = datetime.utcnow()

    def check_congestion(self, level: str, score: float) -> Optional[Dict]:
        if level in ("Heavy Traffic", "Gridlock") and self._can_alert(f"congestion_{level}"):
            self._mark_alert(f"congestion_{level}")
            return {
                "alert_type": "congestion",
                "severity": "high" if level == "Gridlock" else "medium",
                "message": f"{level} detected (score: {score:.2f})",
            }
        return None

    def check_violation(self, violation: Dict) -> Optional[Dict]:
        vtype = violation.get("type", "unknown")
        if self._can_alert(f"violation_{vtype}"):
            self._mark_alert(f"violation_{vtype}")
            return {
                "alert_type": "violation",
                "severity": "high" if vtype == "triple_riding" else "medium",
                "message": violation.get("details", f"{vtype} detected"),
            }
        return None

    def check_anomaly(self, anomaly: Dict) -> Optional[Dict]:
        atype = anomaly.get("type", "anomaly")
        if self._can_alert(f"anomaly_{atype}"):
            self._mark_alert(f"anomaly_{atype}")
            return {
                "alert_type": "anomaly",
                "severity": anomaly.get("severity", "medium"),
                "message": anomaly.get("message", "Traffic anomaly detected"),
            }
        return None

    def check_emergency_vehicle(self, detection: Dict) -> Optional[Dict]:
        # Bonus: detect ambulance/fire truck by size + speed pattern (heuristic)
        if detection.get("class_name") == "truck" and detection.get("speed_kmh", 0) > 50:
            if self._can_alert("emergency"):
                self._mark_alert("emergency")
                return {
                    "alert_type": "emergency_vehicle",
                    "severity": "high",
                    "message": "Possible emergency vehicle detected — prioritize corridor",
                }
        return None
