"""Vehicle class mappings and visualization constants."""

from typing import Dict, Set

# COCO class IDs used by YOLOv8
COCO_VEHICLE_IDS: Set[int] = {1, 2, 3, 5, 7}  # bicycle, car, motorcycle, bus, truck

VEHICLE_CLASS_MAP: Dict[int, str] = {
    1: "bike",
    2: "car",
    3: "bike",
    5: "bus",
    7: "truck",
}

DISPLAY_NAMES: Dict[str, str] = {
    "car": "Car",
    "bike": "Bike",
    "bus": "Bus",
    "truck": "Truck",
    "auto": "Auto",
    "person": "Person",
}

# BGR colors for bounding boxes
CLASS_COLORS: Dict[str, tuple] = {
    "car": (0, 165, 255),
    "bike": (0, 255, 0),
    "bus": (255, 0, 0),
    "truck": (128, 0, 128),
    "auto": (0, 255, 255),
    "person": (255, 255, 0),
    "no_helmet": (0, 0, 255),
    "helmet": (0, 200, 0),
}

CONGESTION_COLORS: Dict[str, tuple] = {
    "Low Traffic": (0, 200, 0),
    "Medium Traffic": (0, 200, 255),
    "Heavy Traffic": (0, 140, 255),
    "Gridlock": (0, 0, 255),
}

DIRECTION_VECTORS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
