# Railway Safety Monitor

A portable Streamlit MVP for recorded railway video analysis. It detects people with Ultralytics YOLO, tracks detections between frames, and creates an alert only on entry into a configurable polygonal danger zone. People outside the zone do not create intrusion alerts.

## Quick start

Python 3.10 or 3.11 is recommended. From this directory:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

The first analysis using the default `yolov8n.pt` may download the model through Ultralytics. Alternatively enter the path to an existing compatible `.pt` model. Keep videos in `data/videos` or upload them in the dashboard. Outputs are written under `outputs/`.

## Using the dashboard

1. Upload a supported video or choose one from `data/videos`.
2. Set a danger polygon with one normalized `x,y` point per line (`0` to `1`). Coordinates are measured relative to video width and height.
3. Set confidence and cooldown, then run analysis.
4. Review the annotated video, alert table, snapshots, and downloadable CSV. A JSON report is also saved alongside the CSV.

The bottom center polygon is only a demonstration default. Configure it for each camera view. The detector uses the person class, and the person's bounding-box bottom center is tested against the danger area. Risk labels are simple confidence tiers for demonstration; they are not a safety certification.

## GPU / Windows

Ultralytics selects an available compute device automatically. For NVIDIA acceleration on Windows 11, install a compatible NVIDIA driver and install the PyTorch build matching that driver from the official PyTorch selector before installing this project's requirements. CPU processing remains available. Do not package model weights or surveillance videos in the source archive.

## Hafnia VLM

`src/hafnia_client.py` is a deliberately disabled integration boundary. No URL, credential, or request schema is assumed. Enable implementation only after obtaining the actual Gateway API documentation and credentials.

## Tests

Run the core logic tests with `python -m unittest discover -s tests`. They cover polygon transitions, tracking association, and alert cooldown without downloading model weights.
