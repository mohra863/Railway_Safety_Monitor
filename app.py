"""Streamlit dashboard for railway intrusion monitoring."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DEFAULT_MODEL, DEFAULT_ZONE, OUTPUT_DIR, VIDEO_DIR
from src.video_processor import VideoProcessor

st.set_page_config(page_title="Railway Safety Monitor", page_icon="🚆", layout="wide")
st.markdown("""
<style>
.stApp {background:#081426;color:#e7eef8}
[data-testid="stMetric"] {background:#101f35;border:1px solid #203653;padding:16px;border-radius:12px}
.block-container {padding-top:1.4rem}
</style>
""", unsafe_allow_html=True)

st.title("🚆 Railway Safety Monitor")
st.caption("AI-assisted trackside intrusion monitoring · Recorded video analysis")

with st.sidebar:
    st.header("Analysis settings")
    model_path = st.text_input("YOLO model", value=DEFAULT_MODEL, help="Ultralytics model name or local .pt path")
    confidence = st.slider("Detection confidence", 0.10, 0.95, 0.35, 0.05)
    cooldown = st.slider("Alert cooldown (seconds)", 1, 120, 15)
    st.markdown("**Danger zone polygon**")
    zone_text = st.text_area("Normalized points: x,y per line", value="\n".join(f"{x},{y}" for x,y in DEFAULT_ZONE), height=115)
    st.caption("Coordinates are normalized from 0 to 1. Set the polygon over the track area in the video.")

video_source = st.file_uploader("Choose recorded video", type=["mp4", "avi", "mov", "mkv"])
if video_source is None:
    candidates = sorted(p for p in VIDEO_DIR.glob("*") if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"})
    if candidates:
        video_path = st.selectbox("Or select a video in data/videos", candidates, format_func=lambda p: p.name)
    else:
        video_path = None
else:
    video_path = None

def parse_zone(raw: str):
    points = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        x, y = (float(v.strip()) for v in line.split(",", 1))
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Zone coordinates must be between 0 and 1.")
        points.append((x, y))
    if len(points) < 3:
        raise ValueError("Enter at least three polygon points.")
    return points

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if st.button("Analyze video", type="primary", disabled=video_source is None and video_path is None):
    try:
        polygon = parse_zone(zone_text)
        if video_source is not None:
            suffix = Path(video_source.name).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=OUTPUT_DIR) as tmp:
                tmp.write(video_source.getbuffer())
                input_path = Path(tmp.name)
            camera_name = video_source.name
        else:
            input_path = Path(video_path)
            camera_name = input_path.name
        progress = st.progress(0, text="Loading detector and video…")
        status = st.empty()
        result = VideoProcessor(model_path=model_path, confidence=confidence, cooldown_seconds=cooldown, danger_zone=polygon).process(
            input_path, progress_callback=lambda n, total: progress.progress(min(n / max(total, 1), 1.0), text=f"Processing frame {n}/{total}")
        )
        result["camera_name"] = camera_name
        st.session_state.analysis = result
        status.success(f"Analysis complete: {result['frames_processed']} frames")
    except Exception as exc:
        st.error(f"Could not analyze video: {exc}")

result = st.session_state.analysis
if result:
    alerts = result["alerts"]
    a, b, c, d = st.columns(4)
    a.metric("People observed", result["people_observed"])
    b.metric("Intrusion events", len(alerts))
    c.metric("High-risk alerts", sum(row["risk_level"] == "High" for row in alerts))
    d.metric("Frames processed", result["frames_processed"])
    st.caption(f"Status: {result['status']} · Report: {result['report_path']}")
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Processed video")
        if result.get("video_path") and Path(result["video_path"]).exists():
            st.video(result["video_path"])
        else:
            st.info("Processed preview was not created. Check the output directory and codec support.")
    with right:
        st.subheader("Recent alerts")
        if alerts:
            df = pd.DataFrame(alerts)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.success("No intrusion events were detected in this video.")
    report = Path(result["report_path"])
    if report.exists():
        st.download_button("Download event report (CSV)", report.read_bytes(), file_name=report.name, mime="text/csv")
    if alerts:
        st.subheader("Event snapshots")
        cols = st.columns(min(3, len(alerts)))
        for i, alert in enumerate(alerts[:9]):
            if alert.get("screenshot") and Path(alert["screenshot"]).exists():
                cols[i % len(cols)].image(alert["screenshot"], caption=f"{alert['timestamp']} · {alert['risk_level']}")
else:
    st.info("Upload a railway video or place one in data/videos, configure the danger polygon, then start analysis.")
