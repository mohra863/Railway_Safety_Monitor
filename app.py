# Railway Safety Monitor with Hafnia Gateway integration
"""Streamlit dashboard for railway intrusion monitoring and Hafnia VLM analysis.

The application provides two tabs:
1️⃣ **YOLO Analysis** – the existing video‑object‑detection workflow.
2️⃣ **Hafnia Gateway Analysis** – submit a clip from an XProtect camera to the Hafnia
   Gateway API and display the returned summary.

Secrets for the Hafnia client are read from Streamlit secrets or environment variables:
- ``HAFNIA_GATEWAY_URL`` – e.g. ``https://localhost:15443``
- ``HAFNIA_USERNAME`` – default ``administrator``
- ``HAFNIA_PASSWORD`` – required password
"""

from __future__ import annotations

import html
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from config import DEFAULT_MODEL, DEFAULT_ZONE, OUTPUT_DIR, VIDEO_DIR
from src.video_processor import VideoProcessor
from src.hafnia_client import HafniaClient, build_xprotect_uri
from src.crossing_detection import classify_track_crossing


def _format_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _render_hafnia_analysis(analysis: dict) -> None:
    result = analysis.get("payload") or {}
    progress = result.get("Progress")
    if progress != "Completed":
        error = result.get("LastError", "Unknown error")
        st.error(f"❌ Summary failed: {error}")
        return

    response = result.get("Response") or "(no response)"
    camera_label = analysis.get("camera_name") or analysis.get("camera_id") or "Unknown camera"
    start_utc = analysis.get("start_utc")
    end_utc = analysis.get("end_utc")
    time_range = "Unknown"
    if isinstance(start_utc, datetime) and isinstance(end_utc, datetime):
        time_range = f"{_format_utc(start_utc)} – {_format_utc(end_utc)}"

    crossing = classify_track_crossing(response if isinstance(response, str) else str(response))
    st.success("✅ Summary completed")

    if crossing.is_crossing:
        st.markdown(
            f"""
            <div class="rsm-alert">
              <div class="rsm-alert-title">RAILWAY TRACK CROSSING DETECTED</div>
              <div class="rsm-alert-grid">
                <div class="rsm-alert-label">Risk Level</div>
                <div class="rsm-alert-value rsm-alert-risk">High</div>
                <div class="rsm-alert-label">Camera</div>
                <div class="rsm-alert-value">{html.escape(str(camera_label))}</div>
                <div class="rsm-alert-label">Event time (UTC)</div>
                <div class="rsm-alert-value">{html.escape(time_range)}</div>
                <div class="rsm-alert-label">Event Type</div>
                <div class="rsm-alert-value">Railway Track Crossing</div>
              </div>
              <div class="rsm-alert-desc">{html.escape(crossing.description)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Summary")
    st.markdown(
        f'<div class="rsm-summary">{html.escape(str(response))}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page configuration and common styling
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Railway Safety Monitor", page_icon="🚆", layout="wide")
st.markdown(
    """
    <style>
    .stApp {background:#081426;color:#e7eef8}
    [data-testid=\"stMetric\"] {background:#101f35;border:1px solid #203653;padding:16px;border-radius:12px}
    .block-container {padding-top:1.4rem}
    .rsm-alert {background:#1b1020;border:1px solid #e53935;border-left:6px solid #ff3b3b;border-radius:12px;padding:1.25rem 1.4rem 1.15rem;margin:0.35rem 0 1rem;box-shadow:0 0 24px rgba(229,57,53,.18)}
    .rsm-alert-title {color:#ff5252;font-size:1.42rem;font-weight:800;letter-spacing:.05em;margin:0 0 1rem 0}
    .rsm-alert-grid {display:grid;grid-template-columns:150px 1fr;gap:.4rem 1rem;margin-bottom:.85rem}
    .rsm-alert-label {color:#9eb0c8;font-size:.86rem}
    .rsm-alert-value {color:#e7eef8;font-weight:600}
    .rsm-alert-risk {color:#ff5252;font-weight:800;letter-spacing:.04em}
    .rsm-alert-desc {color:#d5deea;line-height:1.5;margin:.15rem 0 0}
    .rsm-summary {background:#101f35;border:1px solid #203653;border-radius:12px;padding:1rem 1.15rem;color:#e7eef8;line-height:1.55}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚆 Railway Safety Monitor")
st.caption("AI‑assisted trackside intrusion monitoring · Recorded video analysis")

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab_yolo, tab_hafnia = st.tabs(["YOLO Analysis", "Hafnia Gateway Analysis"])

# ---------------------------------------------------------------------------
# YOLO Analysis – original functionality (wrapped unchanged)
# ---------------------------------------------------------------------------
with tab_yolo:
    with st.sidebar:
        st.header("Analysis settings")
        model_path = st.text_input("YOLO model", value=DEFAULT_MODEL, help="Ultralytics model name or local .pt path")
        confidence = st.slider("Detection confidence", 0.10, 0.95, 0.35, 0.05)
        cooldown = st.slider("Alert cooldown (seconds)", 1, 120, 15)
        st.markdown("**Danger zone polygon**")
        zone_text = st.text_area(
            "Normalized points: x,y per line",
            value="\n".join(f"{x},{y}" for x, y in DEFAULT_ZONE),
            height=115,
        )
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
            result = VideoProcessor(
                model_path=model_path,
                confidence=confidence,
                cooldown_seconds=cooldown,
                danger_zone=polygon,
            ).process(
                input_path,
                progress_callback=lambda n, total: progress.progress(
                    min(n / max(total, 1), 1.0),
                    text=f"Processing frame {n}/{total}",
                ),
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
        c.metric("High‑risk alerts", sum(row["risk_level"] == "High" for row in alerts))
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

# ---------------------------------------------------------------------------
# Hafnia Gateway Analysis – new feature
# ---------------------------------------------------------------------------
with tab_hafnia:
    st.header("Hafnia Gateway Analysis")
    st.caption("Submit a clip from an XProtect camera to the Hafnia VLM via the local Gateway API.")

    camera_id = st.text_input("Camera ID", value="E0036434-54F2-4977-82D0-F86FCD47F977")
    camera_name = st.text_input("Camera name (optional)", value="person_on_railway_tracks")

    # -----------------------------------------------------------------------
    # Date / time inputs with second precision.
    #
    # st.datetime_input only exposes hours and minutes; st.time_input with
    # step=1 adds a seconds spinner, so we use a date picker + time_input pair
    # for each bound.  All displayed times are UTC.
    # -----------------------------------------------------------------------
    now_utc = datetime.now(tz=timezone.utc)
    default_end_dt   = now_utc.replace(microsecond=0) - timedelta(seconds=15)
    default_start_dt = default_end_dt - timedelta(seconds=30)

    st.markdown("**Start time (UTC)**")
    col_sd, col_st = st.columns(2)
    with col_sd:
        start_date = st.date_input(
            "Start date",
            value=default_start_dt.date(),
            label_visibility="collapsed",
        )
    with col_st:
        start_time_of_day = st.time_input(
            "Start time",
            value=default_start_dt.time(),
            step=1,              # 1-second step exposes the seconds spinner
            label_visibility="collapsed",
        )

    st.markdown("**End time (UTC)**")
    col_ed, col_et = st.columns(2)
    with col_ed:
        end_date = st.date_input(
            "End date",
            value=default_end_dt.date(),
            label_visibility="collapsed",
        )
    with col_et:
        end_time_of_day = st.time_input(
            "End time",
            value=default_end_dt.time(),
            step=1,
            label_visibility="collapsed",
        )

    # Combine date + time → UTC-aware datetime
    start_utc = datetime.combine(start_date, start_time_of_day, tzinfo=timezone.utc)
    end_utc   = datetime.combine(end_date,   end_time_of_day,   tzinfo=timezone.utc)

    # Show a live preview of the interval that will be requested
    duration_s = int((end_utc - start_utc).total_seconds())
    if duration_s > 0:
        st.caption(
            f"Interval: **{start_utc.strftime('%Y-%m-%d %H:%M:%S')} Z** → "
            f"**{end_utc.strftime('%Y-%m-%d %H:%M:%S')} Z** "
            f"({duration_s} s)"
        )
    else:
        st.warning("⚠️ End time must be strictly after start time.")

    prompt = st.text_area("Prompt", value="Describe what happens in this video.", height=100)

    if "hafnia_analysis" not in st.session_state:
        st.session_state.hafnia_analysis = None

    if st.button("Run Hafnia analysis"):
        # Validate before hitting the API
        if end_utc <= start_utc:
            st.error("End time must be strictly after start time.")
        else:
            try:
                client = HafniaClient(enabled=True)
                video_uri = build_xprotect_uri(camera_id, start_utc, end_utc)
                with st.spinner("Submitting request and waiting for answer…"):
                    result = client.run_summary_workflow(prompt, video_uri)
                st.session_state.hafnia_analysis = {
                    "payload": result,
                    "camera_id": camera_id,
                    "camera_name": (camera_name or "").strip() or camera_id,
                    "start_utc": start_utc,
                    "end_utc": end_utc,
                }
            except Exception as e:
                st.error(f"Error: {e}")

    analysis = st.session_state.hafnia_analysis
    if analysis:
        _render_hafnia_analysis(analysis)

