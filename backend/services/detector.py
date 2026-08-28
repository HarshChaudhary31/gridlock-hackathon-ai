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

    @staticmethod
    def _helmet_class_kind(name: str) -> Optional[str]:
        n = name.lower().replace("-", "_").replace(" ", "_")
        if any(tok in n for tok in ("no_helmet", "without_helmet", "nohelmet", "not_wearing")):
            return "no_helmet"
        if "without" in n and "helmet" in n:
            return "no_helmet"
        if n in {"head", "bare_head", "no_hat"}:
            return "no_helmet"
        if "helmet" in n:
            return "helmet"
        return None

    def _helmet_model_boxes(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run the existing helmet YOLO weights when they actually have helmet classes."""
        if not self.helmet_model:
            return []
        names = getattr(self.helmet_model, "names", {}) or {}
        kind_by_id = {int(i): self._helmet_class_kind(str(n)) for i, n in names.items()}
        if not any(kind_by_id.values()):
            return []

        results = self.helmet_model.predict(
            frame,
            conf=settings.CONFIDENCE_THRESHOLD,
            iou=settings.IOU_THRESHOLD,
            verbose=False,
        )
        boxes: List[Dict[str, Any]] = []
        result = results[0] if results else None
        if result is None or result.boxes is None:
            return boxes
        for i in range(len(result.boxes)):
            cls_id = int(result.boxes.cls[i].item())
            kind = kind_by_id.get(cls_id)
            if not kind:
                continue
            boxes.append(
                {
                    "kind": kind,
                    "confidence": float(result.boxes.conf[i].item()),
                    "bbox": result.boxes.xyxy[i].cpu().numpy().tolist(),
                }
            )
        return boxes

    def detect_helmets(
        self,
        frame: np.ndarray,
        bike_detections: List[Dict[str, Any]],
        person_detections: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Detect helmet / no-helmet using the helmet model when available, else rider heuristics."""
        violations: List[Dict[str, Any]] = []
        stats = {
            "riders_checked": 0,
            "helmet": 0,
            "no_helmet": 0,
            "helmet_track_ids": [],
            "no_helmet_track_ids": [],
        }
        helmet_boxes = self._helmet_model_boxes(frame)

        for bike in bike_detections:
            if bike["class_name"] not in ("bike",):
                continue
            bx1, by1, bx2, by2 = bike["bbox"]
            bike_cx = (bx1 + bx2) / 2
            riders_near = 0
            helmet_near = False
            no_helmet_model = False
            model_conf = 0.0

            for person in person_detections:
                px1, py1, px2, py2 = person["bbox"]
                pcx = (px1 + px2) / 2
                overlap_x = max(0, min(bx2, px2) - max(bx1, px1))
                overlap_y = max(0, min(by2, py2) - max(by1, py1))
                if overlap_x > 0 and overlap_y > 0:
                    riders_near += 1
                elif abs(pcx - bike_cx) < (bx2 - bx1) * 0.8 and py2 > by1:
                    riders_near += 1

            for hb in helmet_boxes:
                hx1, hy1, hx2, hy2 = hb["bbox"]
                overlap_x = max(0, min(bx2, hx2) - max(bx1, hx1))
                overlap_y = max(0, min(by2, hy2) - max(by1, hy1))
                if overlap_x <= 0 or overlap_y <= 0:
                    continue
                if hb["kind"] == "helmet":
                    helmet_near = True
                    model_conf = max(model_conf, hb["confidence"])
                elif hb["kind"] == "no_helmet":
                    no_helmet_model = True
                    model_conf = max(model_conf, hb["confidence"])

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

            if riders_near >= 1:
                stats["riders_checked"] += 1
                no_helmet = False
                if no_helmet_model and not helmet_near:
                    no_helmet = True
                elif not helmet_boxes:
                    head_region_empty = True
                    for person in person_detections:
                        px1, py1, px2, py2 = person["bbox"]
                        head_y = py1 + (py2 - py1) * 0.15
                        if bx1 <= (px1 + px2) / 2 <= bx2 and by1 <= head_y <= by1 + (by2 - by1) * 0.4:
                            head_region_empty = False
                            break
                    no_helmet = head_region_empty

                if no_helmet:
                    stats["no_helmet"] += 1
                    if bike.get("track_id") is not None:
                        stats["no_helmet_track_ids"].append(bike["track_id"])
                    violations.append(
                        {
                            "type": "no_helmet",
                            "track_id": bike.get("track_id"),
                            "confidence": model_conf or 0.65,
                            "bbox": bike["bbox"],
                            "details": "Rider detected without visible helmet",
                        }
                    )
                else:
                    stats["helmet"] += 1
                    if bike.get("track_id") is not None:
                        stats["helmet_track_ids"].append(bike["track_id"])

        return violations, stats


_detector: Optional[VehicleDetector] = None


def get_detector() -> VehicleDetector:
    global _detector
    if _detector is None:
        _detector = VehicleDetector()
    return _detector
