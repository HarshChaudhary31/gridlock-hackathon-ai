"""Predictive congestion forecasting (bonus feature)."""

from collections import deque
from typing import Deque, Dict, List, Optional

import numpy as np


class CongestionForecaster:
    """Simple linear trend forecast for next N frames."""

    def __init__(self, history_len: int = 30) -> None:
        self.scores: Deque[float] = deque(maxlen=history_len)

    def update(self, score: float) -> None:
        self.scores.append(score)

    def predict(self, horizon: int = 10) -> List[Dict]:
        if len(self.scores) < 5:
            return []
        y = np.array(list(self.scores))
        x = np.arange(len(y))
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs[0], coeffs[1]
        predictions = []
        for i in range(1, horizon + 1):
            future_x = len(y) + i
            pred_score = float(np.clip(slope * future_x + intercept, 0, 1))
            level = self._level_from_score(pred_score)
            predictions.append(
                {
                    "step": i,
                    "predicted_score": round(pred_score, 3),
                    "predicted_level": level,
                    "trend": "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable",
                }
            )
        return predictions

    def _level_from_score(self, score: float) -> str:
        if score >= 0.9:
            return "Gridlock"
        if score >= 0.75:
            return "Heavy Traffic"
        if score >= 0.5:
            return "Medium Traffic"
        return "Low Traffic"

    def signal_recommendation(self, current_level: str, predicted: List[Dict]) -> Optional[str]:
        if not predicted:
            return None
        next_score = predicted[0]["predicted_score"]
        if current_level in ("Heavy Traffic", "Gridlock") or next_score > 0.7:
            return "Extend green phase on arterial; restrict side-street inflow for 120s"
        if next_score > 0.5:
            return "Moderate signal cycle (+15s green on main corridor)"
        return "Maintain standard signal timing"
