"""Creates intrusion alerts with per-track cooldown handling."""
from datetime import datetime

class AlertManager:
    def __init__(self, cooldown_seconds=15):
        self.cooldown_seconds = cooldown_seconds
        self.last_alert: dict[int, float] = {}

    def create(self, track_id, confidence, camera_name, timestamp, now_seconds, screenshot=None):
        if now_seconds - self.last_alert.get(track_id, float("-inf")) < self.cooldown_seconds:
            return None
        self.last_alert[track_id] = now_seconds
        risk = "High" if confidence >= 0.75 else "Medium" if confidence >= 0.5 else "Low"
        return {
            "timestamp": timestamp or datetime.now().astimezone().isoformat(timespec="seconds"),
            "camera_name": camera_name,
            "event_type": "Person entered danger zone",
            "track_id": track_id,
            "confidence": round(float(confidence), 3),
            "risk_level": risk,
            "explanation": "A tracked person crossed into the configured railway danger zone.",
            "screenshot": str(screenshot) if screenshot else "",
        }
