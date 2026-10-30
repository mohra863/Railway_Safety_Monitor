"""CSV and JSON alert report writers."""
import csv, json
from pathlib import Path

FIELDS = ["timestamp", "camera_name", "event_type", "track_id", "confidence", "risk_level", "explanation", "screenshot"]

def save_csv(alerts, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader(); writer.writerows(alerts)
    return path

def save_json(alerts, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(alerts, indent=2), encoding="utf-8")
    return path
