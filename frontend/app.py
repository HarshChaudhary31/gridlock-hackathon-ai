"""
Smart Traffic Monitoring Dashboard - Streamlit Frontend
Traffic AI | Smart Traffic Monitoring
"""

import io
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from PIL import Image

# Page config
st.set_page_config(
    page_title=" Traffic AI",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _api_origin() -> str:
    """Backend origin only (no /api path). Streamlit uses BACKEND_URL; Vite-style env is also accepted."""
    raw = (
        os.getenv("VITE_API_BASE_URL")
        or os.getenv("API_BASE_URL")
        or os.getenv("BACKEND_URL")
        or "http://localhost:8000"
    )
    return raw.rstrip("/")


API_ORIGIN = _api_origin()
API_URL = f"{API_ORIGIN}/api/v1"

# Dark theme CSS
st.markdown(
    """
<style>
    .stApp { background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%); }
    h1, h2, h3 { color: #58a6ff !important; }
    .metric-card {
        background: #21262d;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .congestion-low { color: #3fb950; font-weight: bold; font-size: 1.4rem; }
    .congestion-medium { color: #d29922; font-weight: bold; font-size: 1.4rem; }
    .congestion-heavy { color: #f85149; font-weight: bold; font-size: 1.4rem; }
    .congestion-gridlock { color: #ff0000; font-weight: bold; font-size: 1.4rem; }
    .alert-box {
        background: #3d1f1f;
        border-left: 4px solid #f85149;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
    }
    div[data-testid="stSidebar"] { background: #161b22; }
</style>
""",
    unsafe_allow_html=True,
)


def _http_error_message(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        r = exc.response
        body = (r.text or "").strip()
        if len(body) > 800:
            body = body[:800] + "…"
        extra = f" — {body}" if body else ""
        if r.status_code == 502:
            return (
                f"HTTP 502 Bad Gateway from {r.url}. "
                "The backend proxy failed (timeout, crash, or out-of-memory during processing). "
                "Try a shorter clip and keep max_frames around 150. Do not treat this as empty detections."
                f"{extra}"
            )
        return f"HTTP {r.status_code} {r.reason} from {r.url}{extra}"
    if isinstance(exc, requests.Timeout):
        return f"Request timed out talking to {API_URL}. The backend may still be processing."
    return str(exc)


def api_get(path: str, timeout: int = 15, show_error: bool = True):
    try:
        r = requests.get(f"{API_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        if os.getenv("TRAFFIC_AI_DEBUG") or os.getenv("STREAMLIT_DEBUG"):
            st.exception(e)
        elif show_error:
            st.error(f"API Error: {_http_error_message(e)}")
        return None


def api_post(path: str, files=None, json=None, params=None, timeout: int = 120):
    try:
        r = requests.post(f"{API_URL}{path}", files=files, json=json, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {_http_error_message(e)}")
        return None


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def normalize_results(status: dict | None, live: dict | None = None) -> dict:
    """Map the real backend payload (nested result/latest + vehicles/speed/helmet) for the UI."""
    status = status or {}
    result = _as_dict(status.get("result"))
    latest = live or _as_dict(status.get("latest")) or _as_dict(result.get("latest"))

    vehicles = (
        _as_dict(status.get("vehicles"))
        or _as_dict(result.get("vehicles"))
        or _as_dict(latest.get("vehicles"))
        or _as_dict(latest.get("vehicle_counts"))
    )

    speed = _as_dict(status.get("speed")) or _as_dict(result.get("speed")) or _as_dict(latest.get("speed"))
    congestion = _as_dict(latest.get("congestion"))
    if not speed and congestion:
        speed = {
            "current": congestion.get("avg_speed"),
            "average": congestion.get("avg_speed"),
            "max": None,
            "violations": 0,
            "per_vehicle": [],
        }

    helmet = _as_dict(status.get("helmet")) or _as_dict(result.get("helmet")) or _as_dict(latest.get("helmet"))

    violation_counts = (
        _as_dict(status.get("violation_counts"))
        or _as_dict(result.get("violation_counts"))
        or _as_dict(latest.get("violation_counts"))
    )
    raw_violations = latest.get("violations")
    events = _as_list(status.get("violation_events")) or _as_list(result.get("violation_events")) or _as_list(
        latest.get("violation_events")
    )
    if isinstance(raw_violations, dict) and not violation_counts:
        violation_counts = raw_violations
    elif isinstance(raw_violations, list):
        events = events or raw_violations

    if not violation_counts and events:
        counts = {}
        for item in events:
            if isinstance(item, dict):
                key = item.get("type") or "other"
                counts[key] = counts.get(key, 0) + 1
        violation_counts = counts

    if not helmet and events:
        no_helmet = violation_counts.get("no_helmet", 0)
        helmet = {"riders_checked": None, "helmet": None, "no_helmet": no_helmet, "violations": no_helmet}

    output_video_url = status.get("output_video_url") or result.get("output_video_url")
    if not output_video_url and status.get("session_id"):
        if status.get("status") == "completed" or result.get("output_video") or latest.get("output_video"):
            output_video_url = f"/api/v1/video/output/{status['session_id']}"

    return {
        "status": status.get("status") or latest.get("status"),
        "error": status.get("error"),
        "session_id": status.get("session_id") or latest.get("session_id"),
        "progress": latest.get("progress"),
        "processed_frames": latest.get("processed_frames") or status.get("processed_frames") or result.get("processed_frames"),
        "total_frames": latest.get("total_frames"),
        "vehicles": vehicles,
        "vehicle_counts": _as_dict(latest.get("vehicle_counts")) or vehicles,
        "speed": speed,
        "helmet": helmet,
        "congestion": congestion,
        "violations": events,
        "violation_counts": violation_counts,
        "alerts": _as_list(latest.get("alerts")),
        "forecast": latest.get("forecast"),
        "signal_recommendation": latest.get("signal_recommendation"),
        "entry_exit": _as_dict(latest.get("entry_exit")),
        "flow": _as_dict(latest.get("flow")),
        "output_video_url": output_video_url,
        "peak_congestion": status.get("peak_congestion") or result.get("peak_congestion"),
    }


def _vehicle_label(key: str) -> str:
    labels = {
        "total": "Total",
        "cars": "Car",
        "car": "Car",
        "bikes": "Bike",
        "bike": "Bike",
        "autos": "Auto",
        "auto": "Auto",
        "trucks": "Truck",
        "truck": "Truck",
        "buses": "Bus",
        "bus": "Bus",
        "motorcycles": "Bike",
        "motorcycle": "Bike",
    }
    return labels.get(key, key.replace("_", " ").title())


def render_detection_dashboard(data: dict, session_id: str):
    vehicles = _as_dict(data.get("vehicles")) or _as_dict(data.get("vehicle_counts"))
    class_keys = [k for k in vehicles.keys() if k != "total"]
    total = vehicles.get("total")
    if total is None:
        total = sum(int(vehicles.get(k) or 0) for k in class_keys)

    st.subheader("🚗 Vehicles")
    cols = st.columns(min(max(len(class_keys) + 1, 1), 6))
    cols[0].metric("Total", int(total or 0))
    for i, key in enumerate(class_keys):
        cols[(i + 1) % len(cols)].metric(_vehicle_label(key), int(vehicles.get(key) or 0))

    if class_keys:
        chart_df = pd.DataFrame(
            {"Type": [_vehicle_label(k) for k in class_keys], "Count": [int(vehicles.get(k) or 0) for k in class_keys]}
        )
        fig = px.pie(chart_df, values="Count", names="Type", color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
        st.plotly_chart(fig, use_container_width=True)

    speed = _as_dict(data.get("speed"))
    st.subheader("🏎️ Speed")
    s1, s2, s3, s4 = st.columns(4)
    def _spd(val):
        return "—" if val is None else f"{float(val):.1f} km/h"

    s1.metric("Current", _spd(speed.get("current")))
    s2.metric("Average", _spd(speed.get("average")))
    s3.metric("Max", _spd(speed.get("max")))
    s4.metric("Speed violations", int(speed.get("violations") or 0))
    per_vehicle = _as_list(speed.get("per_vehicle"))
    if per_vehicle:
        st.caption("Per-vehicle speed (latest frame)")
        st.dataframe(pd.DataFrame(per_vehicle), use_container_width=True, hide_index=True)

    helmet = _as_dict(data.get("helmet"))
    st.subheader("🪖 Helmet")
    h1, h2, h3, h4 = st.columns(4)
    def _n(val):
        return "—" if val is None else int(val)

    h1.metric("Riders checked", _n(helmet.get("riders_checked")))
    h2.metric("Helmet", _n(helmet.get("helmet")))
    h3.metric("No helmet", _n(helmet.get("no_helmet")))
    h4.metric("Helmet violations", _n(helmet.get("violations") if helmet.get("violations") is not None else helmet.get("no_helmet")))

    st.subheader("⚠️ Violations")
    vcounts = _as_dict(data.get("violation_counts"))
    events = _as_list(data.get("violations"))
    if vcounts:
        vcols = st.columns(min(len(vcounts), 4) or 1)
        for i, (vtype, count) in enumerate(vcounts.items()):
            vcols[i % len(vcols)].metric(_vehicle_label(vtype), int(count or 0))
    elif not events:
        st.info("No violations reported for this session yet.")
    for v in events[:30]:
        if not isinstance(v, dict):
            continue
        st.markdown(
            f'<div class="alert-box">{str(v.get("type", "")).upper()}: {v.get("details", "")}</div>',
            unsafe_allow_html=True,
        )

    st.subheader("Processed video")
    frame_url = f"{API_URL}/video/frame/{session_id}?t={int(time.time())}"
    try:
        img_r = requests.get(frame_url, timeout=8)
        if img_r.status_code == 200:
            st.image(Image.open(io.BytesIO(img_r.content)), caption="Latest processed frame", use_container_width=True)
        else:
            st.caption("Latest processed frame not available yet.")
    except Exception:
        st.caption("Waiting for processed frames...")

    video_path = data.get("output_video_url")
    if video_path:
        video_url = video_path if str(video_path).startswith("http") else f"{API_ORIGIN}{video_path}"
        try:
            vid_r = requests.get(video_url, timeout=30)
            if vid_r.status_code == 200 and vid_r.content:
                st.video(vid_r.content)
            elif vid_r.status_code == 404:
                st.caption("Processed video file is not ready yet.")
            else:
                st.warning(f"Could not load processed video (HTTP {vid_r.status_code}).")
        except Exception as e:
            st.warning(f"Could not load processed video: {_http_error_message(e)}")


def congestion_class(level: str) -> str:
    m = {
        "Low Traffic": "congestion-low",
        "Medium Traffic": "congestion-medium",
        "Heavy Traffic": "congestion-heavy",
        "traffic ai ": "congestion-gridlock",
    }
    return m.get(level, "congestion-low")


# Sidebar
st.sidebar.title("🚦 Traffic Controls")
page = st.sidebar.radio(
    "Navigation",
    ["Live Dashboard", "Video Processing", "Analytics", "Alerts & Reports", "About"],
)

st.sidebar.markdown("---")

# Session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "history" not in st.session_state:
    st.session_state.history = []


# Header
st.title("🚦 Smart Traffic Monitoring & Mobility Intelligence")
st.caption("AI-Powered CCTV Analytics for Bengaluru Traffic | YOLOv8 + ByteTrack + Real-Time Analytics")

# LIVE DASHBOARD
if page == "Live Dashboard":
    col_sid, col_refresh = st.columns([3, 1])
    with col_sid:
        session_id = st.text_input("Session ID", value=st.session_state.session_id or "")
    with col_refresh:
        st.write("")
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    if session_id:
        st.session_state.session_id = session_id
        status = api_get(f"/video/status/{session_id}")
        live = None
        if status and (status.get("latest") or status.get("status") == "processing"):
            live = api_get(f"/analytics/live/{session_id}", show_error=False)

        if status:
            st.info(f"Status: **{status.get('status', 'unknown')}**")
            if status.get("status") == "failed":
                st.error(f"Processing failed: {status.get('error') or 'unknown error'}")

        data = normalize_results(status, live)
        if status and (data.get("vehicles") or data.get("congestion") or data.get("helmet") or live):
            c1, c2, c3, c4, c5 = st.columns(5)
            counts = data.get("vehicle_counts") or data.get("vehicles") or {}
            cong = data.get("congestion") or {}
            level = cong.get("level", "Low Traffic")

            c1.metric("Total Vehicles", counts.get("total", 0))
            c2.metric("Cars", counts.get("cars", counts.get("car", 0)))
            c3.metric("Bikes", counts.get("bikes", counts.get("bike", 0)))
            c4.metric("Buses", counts.get("buses", counts.get("bus", 0)))
            c5.metric("Autos", counts.get("autos", counts.get("auto", 0)))

            st.markdown(
                f'<p class="{congestion_class(level)}">Congestion: {level} — Score: {cong.get("score", 0):.2f}</p>',
                unsafe_allow_html=True,
            )

            speed = data.get("speed") or {}
            m1, m2, m3 = st.columns(3)
            avg = speed.get("average") if speed.get("average") is not None else cong.get("avg_speed", 0)
            m1.metric("Avg Speed", f"{float(avg or 0):.1f} km/h")
            m2.metric("Density", f"{cong.get('density', 0):.3f}")
            m3.metric("Occupancy", f"{cong.get('occupancy', 0):.3f}")

            render_detection_dashboard(data, session_id)

            # Congestion gauge
            st.subheader("Congestion Score")
            score = cong.get("score", 0)
            gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=score * 100,
                    title={"text": "Congestion %"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#f85149" if score > 0.75 else "#d29922" if score > 0.5 else "#3fb950"},
                        "steps": [
                            {"range": [0, 25], "color": "#1a472a"},
                            {"range": [25, 50], "color": "#3d2f00"},
                            {"range": [50, 75], "color": "#4a2020"},
                            {"range": [75, 100], "color": "#5c1010"},
                        ],
                    },
                )
            )
            gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#c9d1d9", height=250)
            st.plotly_chart(gauge, use_container_width=True)

            # Forecast
            if data.get("forecast"):
                st.subheader("🔮 Predictive Congestion Forecast")
                fc_df = pd.DataFrame(data["forecast"])
                fig_fc = px.line(fc_df, x="step", y="predicted_score", markers=True, title="Predicted Congestion Trend")
                fig_fc.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
                st.plotly_chart(fig_fc, use_container_width=True)
                if data.get("signal_recommendation"):
                    st.success(f"🚥 Signal Recommendation: {data['signal_recommendation']}")

            v1, v2 = st.columns(2)
            with v1:
                st.subheader("🔔 Alerts")
                for a in data.get("alerts", []):
                    st.warning(f"[{a.get('severity', '')}] {a.get('message', '')}")
            with v2:
                st.subheader("Movement Analysis")
                ee = data.get("entry_exit") or {}
                flow = data.get("flow") or {}
                f1, f2 = st.columns(2)
                f1.metric("Entries", ee.get("entry", 0))
                f2.metric("Exits", ee.get("exit", 0))
                if flow:
                    st.json(flow)

            if status and status.get("status") == "processing":
                time.sleep(2)
                st.rerun()
        else:
            st.warning("No live data yet. Start processing a video first.")
    else:
        st.info("Enter a session ID or process a video to view live metrics.")

# VIDEO PROCESSING
elif page == "Video Processing":
    st.header("📹 Video Processing")
    tab1, tab2, tab3 = st.tabs(["Upload Video", "Sample Data", "Webcam Info"])

    with tab1:
        uploaded = st.file_uploader("Upload traffic CCTV footage", type=["mp4", "avi", "mov", "mkv", "webm"])
        frame_skip = st.slider("Frame skip (performance)", 1, 5, 2)
        max_frames = st.number_input("Max frames (0 = all)", min_value=0, value=150)

        if uploaded and st.button("🚀 Start Processing", type="primary"):
            progress = st.empty()
            progress.info("Uploading video to backend…")
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "video/mp4")}
            params = {"frame_skip": frame_skip, "save_output": True}
            if max_frames > 0:
                params["max_frames"] = int(max_frames)
            try:
                r = requests.post(
                    f"{API_URL}/video/upload",
                    files=files,
                    params=params,
                    timeout=180,
                )
                if not r.ok:
                    raise requests.HTTPError(response=r)
                result = r.json()
                st.session_state.session_id = result["session_id"]
                st.success(f"Upload accepted. Session: **{result['session_id']}**")
                st.code(result["session_id"])
                st.session_state.await_processing = True
            except Exception as e:
                st.error(_http_error_message(e))
                st.session_state.await_processing = False

    with tab2:
        st.markdown("Generate and process synthetic Bengaluru traffic video for demo.")
        duration = st.slider("Duration (seconds)", 5, 30, 10)
        if st.button("Generate & Process Sample"):
            with st.spinner("Generating sample video..."):
                gen = api_post("/video/sample/generate", json=None)
                if gen:
                    st.info(f"Sample: {gen.get('path')}")
                proc = api_post(
                    "/video/sample/process",
                    params={"duration_sec": duration, "frame_skip": 2, "max_frames": 150},
                    timeout=60,
                )
                if proc:
                    st.session_state.session_id = proc["session_id"]
                    st.success(f"Session: {proc['session_id']}")
                    st.session_state.await_processing = True

    with tab3:
        st.markdown(
            """
            **Webcam / CCTV Integration**
            - Use RTSP URL with OpenCV: `cv2.VideoCapture('rtsp://...')`
            - Extend `VideoProcessor` for live stream ingestion
            - API endpoint: POST `/api/v1/video/process` with stream path
            """
        )

    if st.session_state.session_id:
        st.markdown(f"**Active Session:** `{st.session_state.session_id}`")
        sid = st.session_state.session_id
        status = api_get(f"/video/status/{sid}", timeout=20)
        if status:
            st.info(f"Status: **{status.get('status', 'unknown')}**")
            if status.get("status") == "failed":
                st.error(f"Processing failed: {status.get('error') or 'unknown error'}")
            elif status.get("status") == "processing":
                latest = status.get("latest") or {}
                pct = float(latest.get("progress") or 0) * 100
                st.progress(min(max(pct / 100.0, 0.0), 1.0), text=f"Processing video… {pct:.0f}%")
                st.caption("YOLO inference can take several minutes on CPU (including Render). Keep this page open.")
                time.sleep(2)
                st.rerun()
            elif status.get("status") == "completed":
                live = api_get(f"/analytics/live/{sid}", show_error=False)
                data = normalize_results(status, live)
                render_detection_dashboard(data, sid)

# ANALYTICS
elif page == "Analytics":
    st.header("📊 Traffic Analytics")
    sid = st.text_input("Session ID", value=st.session_state.session_id or "")

    if sid and st.button("Load Analytics"):
        summary = api_get(f"/analytics/summary/{sid}")
        history = api_get(f"/analytics/congestion/{sid}")

        if summary:
            st.subheader("Session Summary")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Frames", summary.get("total_frames", 0))
            s2.metric("Peak Congestion", summary.get("peak_congestion", "N/A"))
            s3.metric("Violations", summary.get("violations_count", 0))
            s4.metric("Alerts", summary.get("alerts_count", 0))

            vb = summary.get("vehicle_breakdown", {})
            if isinstance(vb, dict):
                chart_df = pd.DataFrame({"type": list(vb.keys()), "count": list(vb.values())})
                fig = px.bar(chart_df, x="type", y="count", color="type")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
                st.plotly_chart(fig, use_container_width=True)

        if history and history.get("history"):
            hdf = pd.DataFrame(history["history"])
            st.subheader("Congestion Timeline")
            fig2 = px.line(hdf, x="timestamp", y="score", color="level")
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
            st.plotly_chart(fig2, use_container_width=True)

            fig3 = px.area(hdf, x="timestamp", y="avg_speed", title="Average Speed Over Time")
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
            st.plotly_chart(fig3, use_container_width=True)

# ALERTS & REPORTS
elif page == "Alerts & Reports":
    st.header("🔔 Alerts & Reports")
    sid = st.text_input("Session ID", value=st.session_state.session_id or "")

    alerts = api_get("/analytics/alerts" + (f"?session_id={sid}" if sid else ""))
    if alerts:
        st.subheader("Recent Alerts")
        for a in alerts[:20]:
            icon = "🔴" if a.get("severity") == "high" else "🟡"
            st.markdown(f"{icon} **{a.get('alert_type')}** — {a.get('message')} _{a.get('timestamp')}_")

    if sid:
        st.subheader("Download Reports")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown(f"[📥 Traffic CSV]({API_URL}/reports/traffic/{sid})")
        with r2:
            st.markdown(f"[📥 Violations CSV]({API_URL}/reports/violations/{sid})")
        with r3:
            st.markdown(f"[📥 Summary Report]({API_URL}/reports/summary/{sid})")

# ABOUT
else:
    st.header("About Smart Traffic AI")
    st.markdown(
        """
        **Traffic AI** — AI-powered traffic monitoring and mobility intelligence platform.

        #### Architecture
        ```
        Video Input → Frame Extraction → YOLOv8 Detection → ByteTrack Tracking
        → Congestion Analysis → Helmet Detection → Analytics → Dashboard → Alerts
        ```

        #### Features
        - Real-time vehicle detection (cars, bikes, buses, trucks, autos)
        - Congestion classification (Low / Medium / Heavy / Gridlock)
        - Helmet violation & triple riding detection
        - Vehicle tracking with speed estimation
        - Heatmap visualization
        - Accident/anomaly detection
        - Predictive congestion forecasting
        - Dynamic signal timing recommendations
        - CSV & summary report generation

        #### Tech Stack
        Python | FastAPI | OpenCV | YOLOv8 | ByteTrack | Streamlit | SQLite | Docker
        """
    )
    health = api_get("/health")
    if health:
        st.success(f"Backend: {health.get('status')} | Models: {health.get('models_loaded')}")
