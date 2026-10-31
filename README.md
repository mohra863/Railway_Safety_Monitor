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

## Hafnia Gateway Analysis

The **Hafnia Gateway Analysis** tab lets you query the Hafnia VLM through the local
Gateway API (`https://localhost:15443`) and display the returned video summary.

### Required configuration

The client reads credentials in this priority order:

| Priority | Source | How to set |
|----------|--------|-----------|
| 1 | Shell environment variable | `export HAFNIA_PASSWORD=…` |
| 2 | `.env` file in the project root | Copy `.env.example` → `.env` and fill in values |
| 3 | Streamlit `secrets.toml` | See [Streamlit secrets docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) |

Only **`HAFNIA_PASSWORD`** is mandatory. The URL and username already have safe defaults.

### One-time setup (recommended: `.env` file)

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Open .env in any editor and set your Windows password
#    (the password you use to log in to the machine running the gateway)
nano .env          # or: code .env, vim .env, …
```

`.env` is listed in `.gitignore` and will **never** be committed to Git.

### `.env` file format

```dotenv
# Required
HAFNIA_PASSWORD=your_windows_password_here

# Optional – defaults shown
HAFNIA_GATEWAY_URL=https://localhost:15443
HAFNIA_USERNAME=administrator
```

### Alternative: Streamlit secrets

Create `.streamlit/secrets.toml` (also git-ignored):

```toml
HAFNIA_PASSWORD = "your_windows_password_here"
# HAFNIA_GATEWAY_URL = "https://localhost:15443"
# HAFNIA_USERNAME = "administrator"
```

### Alternative: shell environment variable

```bash
# Linux / macOS
export HAFNIA_PASSWORD=your_windows_password_here
streamlit run app.py

# Windows PowerShell
$env:HAFNIA_PASSWORD = "your_windows_password_here"
streamlit run app.py
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the app

```bash
streamlit run app.py
```

Switch to the **Hafnia Gateway Analysis** tab, select a time range (≤ 30 seconds is
recommended to stay within the Gateway's 60-second VMS export timeout), enter a prompt,
and click **Run Hafnia analysis**.

## Tests

Run all tests:

```bash
python -m pytest tests/ -v
# or
python -m unittest discover -s tests
```

The Hafnia client tests mock all HTTP requests; no real Gateway connection or
`.env` file is required.
