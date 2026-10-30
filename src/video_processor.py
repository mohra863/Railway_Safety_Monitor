"""Frame-by-frame video analysis, annotated video, alert snapshots, and reports."""
from datetime import datetime, timezone
from pathlib import Path
import cv2

from config import ALERT_DIR, PROCESSED_DIR, SCREENSHOT_DIR
from .alert_manager import AlertManager
from .detector import PersonDetector
from .intrusion_detection import IntrusionDetector
from .report_generator import save_csv, save_json
from .tracker import IoUTracker

class VideoProcessor:
    def __init__(self, model_path="yolov8n.pt", confidence=0.35, cooldown_seconds=15, danger_zone=None, detector=None):
        self.detector = detector or PersonDetector(model_path, confidence)
        self.confidence = confidence
        self.cooldown_seconds = cooldown_seconds
        self.danger_zone = danger_zone or [(0.25,0.72),(0.75,0.72),(0.95,1.0),(0.05,1.0)]

    def process(self, video_path, progress_callback=None):
        video_path = Path(video_path)
        if not video_path.exists() or not video_path.is_file():
            raise FileNotFoundError(f"Video not found: {video_path}")
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Cannot open video: {video_path.name}")
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            capture.release(); raise ValueError("Video has invalid dimensions")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = PROCESSED_DIR / f"{video_path.stem}_{stamp}.mp4"
        writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            capture.release(); raise RuntimeError("Could not initialize output video writer")
        tracker, zone = IoUTracker(), IntrusionDetector(self.danger_zone)
        alerts, frame_no, people_observed = [], 0, 0
        alert_manager = AlertManager(self.cooldown_seconds)
        try:
            while True:
                ok, frame = capture.read()
                if not ok: break
                frame_no += 1
                detections = self.detector.detect(frame)
                tracks = tracker.update(detections)
                people_observed += len(detections)
                polygon_px = [(int(x*width), int(y*height)) for x,y in self.danger_zone]
                cv2.polylines(frame, [__import__("numpy").array(polygon_px, dtype="int32")], True, (0, 165, 255), 2)
                cv2.fillPoly(_overlay := frame.copy(), [__import__("numpy").array(polygon_px, dtype="int32")], (0, 100, 180))
                cv2.addWeighted(_overlay, 0.12, frame, 0.88, 0, frame)
                for track in tracks:
                    x1,y1,x2,y2 = track.box
                    entered, inside = zone.update(track.track_id, ((x1+x2)//2, y2), (width,height))
                    color = (0,0,255) if inside else (40,220,80)
                    cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
                    cv2.putText(frame, f"ID {track.track_id} {track.confidence:.2f}", (x1,max(20,y1-8)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
                    if entered:
                        shot = SCREENSHOT_DIR / f"{video_path.stem}_{stamp}_f{frame_no}_id{track.track_id}.jpg"
                        cv2.imwrite(str(shot), frame)
                        alert = alert_manager.create(track.track_id, track.confidence, video_path.name,
                            f"{frame_no / fps:.2f}s", frame_no / fps, shot)
                        if alert: alerts.append(alert)
                writer.write(frame)
                if progress_callback and (frame_no % 5 == 0 or frame_no == total):
                    progress_callback(frame_no, total or frame_no)
        finally:
            capture.release(); writer.release()
        report = save_csv(alerts, ALERT_DIR / f"{video_path.stem}_{stamp}.csv")
        save_json(alerts, ALERT_DIR / f"{video_path.stem}_{stamp}.json")
        return {"status":"Complete", "frames_processed":frame_no, "people_observed":people_observed,
                "alerts":alerts, "video_path":str(output_path), "report_path":str(report)}
