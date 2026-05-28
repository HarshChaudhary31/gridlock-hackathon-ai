"""Draw detections, HUD, and paths on video frames."""

from typing import Dict, List, Optional

import cv2
import numpy as np

from backend.utils.constants import CLASS_COLORS, CONGESTION_COLORS, DISPLAY_NAMES


class FrameVisualizer:
    def draw_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        congestion: Dict,
        counts: Dict,
        violations: List[Dict],
        session_id: str,
        frame_number: int,
        entry_exit: Optional[Dict] = None,
    ) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]

        for det in detections:
            if det["class_name"] == "person":
                continue
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            color = CLASS_COLORS.get(det["class_name"], (200, 200, 200))
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{DISPLAY_NAMES.get(det['class_name'], det['class_name'])}"
            if det.get("track_id") is not None:
                label += f" #{det['track_id']}"
            label += f" {det['confidence']:.2f}"
            if det.get("speed_kmh") is not None:
                label += f" {det['speed_kmh']:.0f}km/h"
            cv2.putText(out, label, (x1, max(y1 - 8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        for v in violations:
            x1, y1, x2, y2 = [int(v) for v in v["bbox"]]
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(
                out,
                v.get("type", "violation").upper(),
                (x1, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )

        level = congestion.get("level")
        level_str = level.value if hasattr(level, "value") else str(level)
        cong_color = CONGESTION_COLORS.get(level_str, (255, 255, 255))

        overlay = out.copy()
        cv2.rectangle(overlay, (10, 10), (380, 200), (0, 0, 0), -1)
        out = cv2.addWeighted(overlay, 0.6, out, 0.4, 0)

        lines = [
            f"Session: {session_id[:12]}...",
            f"Frame: {frame_number}",
            f"Congestion: {level_str} ({congestion.get('score', 0):.2f})",
            f"Vehicles: {counts.get('total', 0)} | Speed: {congestion.get('avg_speed', 0):.1f} km/h",
            f"C:{counts.get('cars',0)} B:{counts.get('bikes',0)} Bu:{counts.get('buses',0)}",
            f"T:{counts.get('trucks',0)} A:{counts.get('autos', 0)}",
        ]
        if entry_exit:
            lines.append(f"Entry:{entry_exit.get('entry',0)} Exit:{entry_exit.get('exit',0)}")

        for i, line in enumerate(lines):
            color = cong_color if i == 2 else (255, 255, 255)
            cv2.putText(out, line, (20, 35 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        score = congestion.get("score", 0)
        bar_w = int(200 * score)
        cv2.rectangle(out, (w - 220, 20), (w - 20, 40), (50, 50, 50), -1)
        cv2.rectangle(out, (w - 220, 20), (w - 220 + bar_w, 40), cong_color, -1)
        cv2.putText(out, "CONGESTION", (w - 215, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        return out
