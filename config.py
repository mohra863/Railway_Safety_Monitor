"""Portable application paths and defaults."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
VIDEO_DIR = DATA_DIR / "videos"
FRAME_DIR = DATA_DIR / "frames"
OUTPUT_DIR = ROOT_DIR / "outputs"
PROCESSED_DIR = OUTPUT_DIR / "processed_videos"
ALERT_DIR = OUTPUT_DIR / "alerts"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
MODEL_DIR = ROOT_DIR / "models"
DEFAULT_MODEL = "yolov8n.pt"
# Normalized x,y coordinates. This sample polygon covers a lower central track area.
DEFAULT_ZONE = [(0.25, 0.72), (0.75, 0.72), (0.95, 1.0), (0.05, 1.0)]
for directory in (VIDEO_DIR, FRAME_DIR, PROCESSED_DIR, ALERT_DIR, SCREENSHOT_DIR, MODEL_DIR):
    directory.mkdir(parents=True, exist_ok=True)
