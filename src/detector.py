"""Ultralytics-backed person detector with lazy model initialization."""
from dataclasses import dataclass
from typing import Iterable

@dataclass
class Detection:
    box: tuple[int, int, int, int]
    confidence: float
    class_id: int = 0

class PersonDetector:
    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.35, device: str | None = None):
        self.model_path, self.confidence, self.device = model_path, confidence, device
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError("Ultralytics is missing. Install project dependencies with pip install -r requirements.txt") from exc
            self._model = YOLO(self.model_path)
        return self._model

    def detect(self, frame) -> list[Detection]:
        model = self._load()
        kwargs = {"conf": self.confidence, "classes": [0], "verbose": False}
        if self.device:
            kwargs["device"] = self.device
        result = model.predict(frame, **kwargs)[0]
        detections = []
        for box in result.boxes:
            coords = tuple(int(v) for v in box.xyxy[0].tolist())
            detections.append(Detection(coords, float(box.conf[0]), int(box.cls[0])))
        return detections
