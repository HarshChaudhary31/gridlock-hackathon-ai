"""YOLOv8 vehicle and person detection service."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.config import get_settings
from backend.utils.constants import COCO_VEHICLE_IDS, VEHICLE_CLASS_MAP
from backend.utils.logger import logger

settings = get_settings()


class VehicleDetector:
    """Wraps Ultralytics YOLO for vehicle/person detection."""

    def __init__(self) -> None:
        self.model = None
        self.helmet_model = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from ultralytics import YOLO

            vehicle_path = settings.WEIGHTS_DIR / Path(settings.YOLO_VEHICLE_MODEL).name
            if not vehicle_path.exists():
                vehicle_path = settings.YOLO_VEHICLE_MODEL

            self.model = YOLO(str(vehicle_path))
            self.model.to(settings.DEVICE)

            helmet_path = settings.WEIGHTS_DIR / Path(settings.YOLO_HELMET_MODEL).name
            if helmet_path.exists():
                self.helmet_model = YOLO(str(helmet_path))
                self.helmet_model.to(settings.DEVICE)

            self._loaded = True
            logger.info("YOLO models loaded on %s", settings.DEVICE)
        except Exception as e:
            logger.error("Failed to load YOLO: %s", e)
            raise

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def detect(
        self,
        frame: np.ndarray,
        track: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Optional[Any]]:
        """Run detection/tracking on a frame."""
        if not self._loaded:
            self.load()

        results = self.model.track(
            frame,
            persist=True,
            conf=settings.CONFIDENCE_THRESHOLD,
            iou=settings.IOU_THRESHOLD,
            classes=list(COCO_VEHICLE_IDS) + [0],  # person for helmet heuristic
            tracker="bytetrack.yaml",
            verbose=False,
        )

        detections: List[Dict[str, Any]] = []
        result = results[0] if results else None

        if result is None or result.boxes is None:
            return detections, result

        boxes = result.boxes
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy().tolist()
            track_id = None
            if boxes.id is not None:
                track_id = int(boxes.id[i].item())

            if cls_id == 0:
                class_name = "person"
            elif cls_id in COCO_VEHICLE_IDS:
                class_name = VEHICLE_CLASS_MAP.get(cls_id, "car")
                # Heuristic: small car bbox may be auto-rickshaw in Indian traffic
                w = xyxy[2] - xyxy[0]
                h = xyxy[3] - xyxy[1]
                area = w * h
                frame_area = frame.shape[0] * frame.shape[1]
                if cls_id == 2 and area / frame_area < 0.02 and w / max(h, 1) < 1.2:
                    class_name = "auto"
            else:
                continue

            detections.append(
                {
                    "track_id": track_id,
                    "class_id": cls_id,
                    "class_name": class_name,
                    "confidence": conf,
                    "bbox": xyxy,
                }
            )

        return detections, result

    def detect_helmets(
        self,
        frame: np.ndarray,
        bike_detections: List[Dict[str, Any]],
        person_detections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect helmet violations using proximity heuristics and optional helmet model."""
        violations: List[Dict[str, Any]] = []

        for bike in bike_detections:
            if bike["class_name"] not in ("bike",):
                continue
            bx1, by1, bx2, by2 = bike["bbox"]
            bike_cx = (bx1 + bx2) / 2
            riders_near = 0
            helmet_near = False

            for person in person_detections:
                px1, py1, px2, py2 = person["bbox"]
                pcx = (px1 + px2) / 2
                # Person overlapping or near motorcycle bbox
                overlap_x = max(0, min(bx2, px2) - max(bx1, px1))
                overlap_y = max(0, min(by2, py2) - max(by1, py1))
                if overlap_x > 0 and overlap_y > 0:
                    riders_near += 1
                elif abs(pcx - bike_cx) < (bx2 - bx1) * 0.8 and py2 > by1:
                    riders_near += 1

            # Triple riding
            if riders_near >= 3:
                violations.append(
                    {
                        "type": "triple_riding",
                        "track_id": bike.get("track_id"),
                        "confidence": 0.75,
                        "bbox": bike["bbox"],
                        "details": f"{riders_near} riders detected on vehicle",
                    }
                )

            # No helmet: rider present but head region heuristic (no helmet class model)
            if riders_near >= 1 and not helmet_near:
                head_region_empty = True
                for person in person_detections:
                    px1, py1, px2, py2 = person["bbox"]
                    head_y = py1 + (py2 - py1) * 0.15
                    if bx1 <= (px1 + px2) / 2 <= bx2 and by1 <= head_y <= by1 + (by2 - by1) * 0.4:
                        # Small bright region proxy - flag as potential no-helmet
                        head_region_empty = False
                        break
                if head_region_empty and riders_near >= 1:
                    violations.append(
                        {
                            "type": "no_helmet",
                            "track_id": bike.get("track_id"),
                            "confidence": 0.65,
                            "bbox": bike["bbox"],
                            "details": "Rider detected without visible helmet",
                        }
                    )

        return violations


_detector: Optional[VehicleDetector] = None


def get_detector() -> VehicleDetector:
    global _detector
    if _detector is None:
        _detector = VehicleDetector()
    return _detector
