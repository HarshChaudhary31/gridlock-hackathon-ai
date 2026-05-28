"""Vehicle tracking utilities: speed, direction, entry/exit counting."""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.utils.constants import DIRECTION_VECTORS


class TrackState:
    """Maintains per-track history for speed and direction estimation."""

    def __init__(self, fps: float = 30.0, pixels_per_meter: float = 8.0) -> None:
        self.fps = fps
        self.pixels_per_meter = pixels_per_meter
        self.history: Dict[int, List[Tuple[float, float, int]]] = defaultdict(list)
        self.entry_count = 0
        self.exit_count = 0
        self.counted_ids: set = set()
        self.line_y: Optional[float] = None

    def set_counting_line(self, frame_height: int, ratio: float = 0.55) -> None:
        self.line_y = frame_height * ratio

    def update(
        self,
        track_id: int,
        bbox: List[float],
        frame_number: int,
    ) -> Dict[str, Optional[float]]:
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        hist = self.history[track_id]
        hist.append((cx, cy, frame_number))
        if len(hist) > 30:
            hist.pop(0)

        speed_kmh = None
        direction = None

        if len(hist) >= 2:
            x0, y0, f0 = hist[-2]
            x1, y1, f1 = hist[-1]
            df = max(f1 - f0, 1)
            dist_px = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            dist_m = dist_px / self.pixels_per_meter
            time_s = df / self.fps
            speed_mps = dist_m / max(time_s, 1e-6)
            speed_kmh = min(speed_mps * 3.6, 120.0)

            dx, dy = x1 - x0, y1 - y0
            if abs(dx) > abs(dy):
                direction = "east" if dx > 0 else "west"
            else:
                direction = "south" if dy > 0 else "north"

        # Entry/exit counting across virtual line
        if self.line_y is not None and track_id not in self.counted_ids and len(hist) >= 3:
            _, y_prev, _ = hist[-3]
            _, y_curr, _ = hist[-1]
            if y_prev < self.line_y <= y_curr:
                self.entry_count += 1
                self.counted_ids.add(track_id)
            elif y_prev > self.line_y >= y_curr:
                self.exit_count += 1
                self.counted_ids.add(track_id)

        return {"speed_kmh": speed_kmh, "direction": direction}

    def get_flow_stats(self) -> Dict[str, int]:
        directions: Dict[str, int] = defaultdict(int)
        for tid, hist in self.history.items():
            if len(hist) < 2:
                continue
            x0, y0, _ = hist[0]
            x1, y1, _ = hist[-1]
            dx, dy = x1 - x0, y1 - y0
            if abs(dx) > abs(dy):
                directions["east" if dx > 0 else "west"] += 1
            else:
                directions["south" if dy > 0 else "north"] += 1
        return dict(directions)
