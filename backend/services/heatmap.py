"""Traffic density heatmap generation."""

from typing import Tuple

import cv2
import numpy as np


class HeatmapGenerator:
    """Accumulates vehicle positions into a density heatmap."""

    def __init__(self, decay: float = 0.98) -> None:
        self.decay = decay
        self.accumulator: np.ndarray | None = None

    def reset(self, shape: Tuple[int, int]) -> None:
        h, w = shape[:2]
        self.accumulator = np.zeros((h, w), dtype=np.float32)

    def update(self, detections: list, frame_shape: Tuple[int, ...]) -> None:
        if self.accumulator is None:
            self.reset(frame_shape)

        self.accumulator *= self.decay
        h, w = self.accumulator.shape

        for det in detections:
            if det.get("class_name") == "person":
                continue
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            cx = np.clip(cx, 0, w - 1)
            cy = np.clip(cy, 0, h - 1)
            cv2.circle(self.accumulator, (cx, cy), 25, 1.0, -1)

    def render(self, base_frame: np.ndarray, alpha: float = 0.45) -> np.ndarray:
        if self.accumulator is None:
            return base_frame

        norm = self.accumulator.copy()
        if norm.max() > 0:
            norm = norm / norm.max()
        heat = (norm * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
        return cv2.addWeighted(base_frame, 1 - alpha, heat_color, alpha, 0)

    def get_hotspots(self, top_k: int = 5) -> list:
        if self.accumulator is None or self.accumulator.max() == 0:
            return []
        flat = self.accumulator.flatten()
        indices = np.argpartition(flat, -top_k)[-top_k:]
        h, w = self.accumulator.shape
        hotspots = []
        for idx in indices:
            y, x = divmod(int(idx), w)
            hotspots.append({"x": x, "y": y, "intensity": float(flat[idx])})
        return sorted(hotspots, key=lambda h: h["intensity"], reverse=True)
